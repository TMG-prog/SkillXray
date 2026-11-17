"""Role profiles, ESCO graph and the Career Readiness Index.

Ported from notebook sections 10 (loading profiles) and 13 (credit, CRI, gaps). Methods kept: 'sbert' and
'sbert_graph' (the final method). 'exact' and 'tfidf' were evaluation baselines and are not served.

Added (not in the notebook): EscoRoles, a fallback that builds a role profile from ESCO's own
occupation -> skill relations, so a role that has no posting-based profile can still be analysed.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C

log = logging.getLogger("skillxray")

NOTEBOOK_ROLE_ALIASES = {
    "business development manager": "business development",
    "it support specialist": "it support",
    "software developer": "software",
    "marketing specialist": "marketing",
    "customer service representative": "customer service",
    "sales representative": "sales",
    "supply chain analyst": "supply chain",
    "legal officer": "legal",
    "communications officer": "communications",
    "management consultant": "consultant",
    "programme officer": "program officer",
    "monitoring and evaluation officer": "monitoring and evaluation",
}


def _col(df, *keys):
    return next((c for c in df.columns if all(k in c.lower() for k in keys)), None)


def load_esco_graph(rel_path: Path, broader_path: Path):
    if not (rel_path.exists() and broader_path.exists()):
        log.warning("ESCO graph files missing - 'sbert_graph' falls back to 'sbert'.")
        return None
    rel, br = pd.read_csv(rel_path, dtype=str), pd.read_csv(broader_path, dtype=str)
    a, b = _col(rel, "original"), _col(rel, "related")
    child, parent = _col(br, "concepturi"), _col(br, "broaderuri")
    if None in (a, b, child, parent):
        log.warning("ESCO graph files have unexpected columns %s %s - graph skipped.", list(rel.columns), list(br.columns))
        return None
    related, parents, children = defaultdict(set), defaultdict(set), defaultdict(set)
    for u, v in zip(rel[a], rel[b]):
        related[u].add(v)
        related[v].add(u)
    for c, p in zip(br[child], br[parent]):
        parents[c].add(p)
        children[p].add(c)
    log.info("ESCO graph: %d skills with related links, %d with a parent group", len(related), len(parents))
    return {"related": related, "parents": parents, "children": children}


def graph_credit(uri, cand_uris, graph):
    if graph is None:
        return 0.0
    if uri in cand_uris:
        return 1.0
    if graph["related"].get(uri, set()) & cand_uris:
        return C.ESCO_GRAPH_CREDIT["related"]
    if any((graph["children"].get(p, set()) - {uri}) & cand_uris for p in graph["parents"].get(uri, ())):
        return C.ESCO_GRAPH_CREDIT["sibling"]
    return 0.0


class EscoRoles:
    """Fallback role profiles from ESCO occupation -> skill relations (essential = 1.0, optional = ESCO_OPTIONAL_WEIGHT)."""

    def __init__(self, occupations: pd.DataFrame, relations: pd.DataFrame | None, skills: pd.DataFrame):
        self.occ_title = dict(zip(occupations["conceptUri"], occupations["preferredLabel"]))
        self.by_title = {}
        for uri, t in self.occ_title.items():
            self.by_title.setdefault(str(t).strip().lower(), uri)
        self.skill_label = dict(zip(skills["conceptUri"], skills["preferredLabel"]))
        self.rel_by_occ = {}
        if relations is not None:
            o, s = _col(relations, "occupation", "uri"), _col(relations, "skill", "uri")
            t = _col(relations, "relationtype")
            if None in (o, s, t):
                log.warning("occupationSkillRelations has unexpected columns %s - ESCO fallback disabled.",
                            list(relations.columns))
            else:
                for occ, grp in relations.groupby(o):
                    self.rel_by_occ[occ] = list(zip(grp[s], grp[t].str.lower()))

    @property
    def enabled(self):
        return bool(self.rel_by_occ)

    def find(self, uri: str | None, title: str | None):
        if uri and uri in self.occ_title:
            return uri
        if title:
            return self.by_title.get(title.strip().lower())
        return None

    def profile(self, occ_uri: str):
        rows = []
        for skill_uri, rtype in self.rel_by_occ.get(occ_uri, []):
            label = self.skill_label.get(skill_uri)
            if label is None:
                continue
            w = 1.0 if rtype == "essential" else C.ESCO_OPTIONAL_WEIGHT
            rows.append((skill_uri, label, w))
        if not rows:
            return None
        df = (pd.DataFrame(rows, columns=["esco_uri", "esco_label", "raw_weight"])
                .drop_duplicates("esco_uri")
                .sort_values("raw_weight", ascending=False, kind="stable").head(C.MAX_ROLE_SKILLS)
                .reset_index(drop=True))
        df["weight"] = df["raw_weight"] / df["raw_weight"].sum()
        df["freq"] = np.nan          # not derived from postings
        df["in_esco"] = True
        df["role"] = self.occ_title[occ_uri]
        return df[["role", "esco_uri", "esco_label", "in_esco", "freq", "weight"]]


class Matcher:
    def __init__(self, encoder, profiles: pd.DataFrame, graph, esco_roles: EscoRoles | None = None,
                 aliases: dict | None = None, prerequisites: dict[str, list[str]] | None = None):
        self.encoder = encoder
        self.graph = graph
        self.esco_roles = esco_roles
        self.prerequisites = prerequisites or {}
        self.aliases = {**NOTEBOOK_ROLE_ALIASES, **(aliases or {})}
        self.aliases = {k.strip().lower(): v.strip().lower() for k, v in self.aliases.items()}
        self.profile_of = {str(r).strip().lower(): df.reset_index(drop=True) for r, df in profiles.groupby("role")}
        self.method = "sbert_graph" if graph is not None else "sbert"
        self._label_emb = {}

    # ---------------------------------------------------------------- roles
    def posting_roles(self):
        return sorted(self.profile_of)

    def resolve(self, role: str, role_id: str | None = None):
        """-> (profile DataFrame, display name, source) or None."""
        key = (role or "").strip().lower()
        if key in self.profile_of:
            return self.profile_of[key], key, "postings"
        alias = self.aliases.get(key)
        if alias and alias.strip().lower() in self.profile_of:
            a = alias.strip().lower()
            return self.profile_of[a], a, "postings"
        if self.esco_roles is not None and self.esco_roles.enabled:
            uri = self.esco_roles.find(role_id, role)
            if uri:
                prof = self.esco_roles.profile(uri)
                if prof is not None:
                    return prof, self.esco_roles.occ_title[uri], "esco"
        return None

    # ---------------------------------------------------------------- credit and index
    def _embed(self, labels):
        new = [l for l in dict.fromkeys(labels) if l not in self._label_emb]
        if new:
            vecs = self.encoder.encode(new, batch_size=128, normalize_embeddings=True, convert_to_numpy=True,
                                       show_progress_bar=False).astype(np.float32)
            self._label_emb.update(zip(new, vecs))
        return np.vstack([self._label_emb[l] for l in labels])

    def _credit(self, cand: pd.DataFrame, prof: pd.DataFrame):
        req_uris, req_labels = prof["esco_uri"].tolist(), prof["esco_label"].astype(str).tolist()
        cand_uris, cand_labels = set(cand["esco_uri"]), cand["esco_label"].astype(str).tolist()
        credit = np.array([1.0 if u in cand_uris else 0.0 for u in req_uris])
        if not cand_labels or not req_labels:
            return credit
        sims = (self._embed(req_labels) @ self._embed(cand_labels).T).max(axis=1)
        credit = np.maximum(credit, np.where(sims >= C.SBERT_MATCH, sims, 0.0))
        if self.method == "sbert_graph":
            credit = np.maximum(credit, [graph_credit(u, cand_uris, self.graph) for u in req_uris])
        return np.clip(credit, 0.0, 1.0)

    def _skill_relationships(self, prof: pd.DataFrame):
        labels = dict(zip(prof["esco_uri"], prof["esco_label"].astype(str)))
        uris = set(labels)
        edges = {}

        for skill_uri, required_uris in self.prerequisites.items():
            if skill_uri in uris:
                for prerequisite_uri in required_uris:
                    if prerequisite_uri in uris and prerequisite_uri != skill_uri:
                        edges[(prerequisite_uri, skill_uri)] = "prerequisite"

        if self.graph is not None:
            for child_uri in uris:
                for parent_uri in self.graph["parents"].get(child_uri, ()):
                    if parent_uri in uris and parent_uri != child_uri:
                        edges.setdefault((parent_uri, child_uri), "broader")
            for skill_uri in uris:
                for related_uri in self.graph["related"].get(skill_uri, ()):
                    if related_uri in uris and skill_uri < related_uri:
                        edges.setdefault((skill_uri, related_uri), "related")

        priority = {"prerequisite": 0, "broader": 1, "related": 2}
        return [
            {"source": labels[source], "target": labels[target], "type": relationship}
            for (source, target), relationship in sorted(
                edges.items(), key=lambda item: (priority[item[1]], labels[item[0][0]], labels[item[0][1]])
            )[:40]
        ]

    def analyse(self, cand: pd.DataFrame, prof: pd.DataFrame):
        credit = self._credit(cand, prof)
        p = prof.assign(credit=credit, covered=credit >= C.GAP_CUTOFF)
        cri = float(100 * np.dot(p["credit"], p["weight"]) / p["weight"].sum())

        def rows(df):
            out = []
            for r in df.sort_values("weight", ascending=False, kind="stable").itertuples():
                d = {"skill": r.esco_label, "uri": r.esco_uri, "weight": round(float(r.weight), 4),
                     "credit": round(float(r.credit), 3),
                     "frequency": None if pd.isna(r.freq) else round(float(r.freq), 3)}
                out.append(d)
            return out

        return {"readiness": round(cri, 1), "n_required": int(len(p)), "n_covered": int(p["covered"].sum()),
                "covered": rows(p[p["covered"]]), "gaps": rows(p[~p["covered"]]),
                "skill_relationships": self._skill_relationships(prof)}


def load_aliases(path: Path):
    return json.loads(path.read_text()) if path.exists() else {}


def load_prerequisites(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or any(
        not isinstance(skill, str)
        or not isinstance(prerequisites, list)
        or any(not isinstance(prerequisite, str) for prerequisite in prerequisites)
        for skill, prerequisites in data.items()
    ):
        raise ValueError(f"Invalid prerequisite mapping in {path}; expected a JSON object of skill URIs to URI lists.")
    return data
