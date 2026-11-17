"""ESCO standardisation: extracted spans -> ESCO skills (or rejected).

Ported from notebook section 9b. Same rules, same order. The only change is that the nearest-term search uses
numpy instead of torch (same cosine ranking, no torch needed here).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .engine import TOOLS

log = logging.getLogger("skillxray")

STOP_WORDS = {"a", "an", "and", "or", "the", "of", "in", "on", "at", "to", "for", "with", "by", "from", "as", "is", "are",
              "was", "be", "been", "this", "that", "these", "those", "it", "its", "their", "our", "your", "we", "you",
              "they", "he", "she", "i", "not", "no", "yes", "making", "using", "used", "use", "work", "working", "worked",
              "etc", "including", "such", "also", "well", "new", "good", "strong"}
ALLOW_SHORT = {"c", "r", "go", "ai", "ml", "ui", "ux", "qa", "hr", "it", "bi", "c#", "c++", ".net", "sql", "aws", "gcp",
               "css", "php"}
NON_SKILL_RE = re.compile(C.NON_SKILL_PATTERN, re.I)

COLLAPSED_COLS = ["doc_id", "esco_uri", "esco_label", "in_esco", "similarity", "exact", "mentions", "surface_forms"]


def _norm_key(s):
    """Lower case, punctuation removed, light plural stripping ("lesson plans" == "lesson plan")."""
    words = re.sub(r"[^a-z0-9+#]+", " ", str(s).lower()).split()
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words)


def is_junk(span):
    low = span.lower().strip()
    if not re.search(r"[A-Za-z]", span):
        return True
    if low in STOP_WORDS and span.strip() != "IT":
        return True
    if len(low) < 3 and low not in ALLOW_SHORT:
        return True
    if low in ALLOW_SHORT:
        return "$" in span
    letters = sum(ch.isalpha() for ch in span)
    return "$" in span or letters < 0.5 * len(span)


def load_overrides(path: Path):
    if not path.exists():
        return {}
    ov = pd.read_csv(path, dtype=str).fillna("")
    ov.columns = [c.strip().lower() for c in ov.columns]
    return {_norm_key(r.span): (r.action.strip().upper(), r.esco_label.strip()) for r in ov.itertuples() if r.span.strip()}


class EscoLinker:
    def __init__(self, skills_df: pd.DataFrame, encoder, extra_terms, overrides: dict,
                 threshold: float, margin: float, emb_path: Path | None = None):
        self.encoder = encoder
        self.threshold, self.margin = threshold, margin
        self.overrides = overrides

        alts = skills_df["altLabels"] if "altLabels" in skills_df.columns else pd.Series([None] * len(skills_df))
        terms = []
        for uri, pref, alt in zip(skills_df["conceptUri"], skills_df["preferredLabel"], alts):
            if not isinstance(pref, str):
                continue
            terms.append((pref, uri, pref))
            if isinstance(alt, str):
                terms += [(a.strip(), uri, pref) for a in alt.split("\n") if a.strip()]
        self.terms = (pd.DataFrame(terms, columns=["term", "conceptUri", "preferredLabel"])
                      .drop_duplicates(subset=["term"]).reset_index(drop=True))
        self.exact = {}
        for i, t in enumerate(self.terms["term"].values):
            self.exact.setdefault(_norm_key(t), i)
        self.uri_of_label = dict(zip(skills_df["preferredLabel"], skills_df["conceptUri"]))
        self.curated = {_norm_key(t): t for t in list(TOOLS) + list(extra_terms)}
        self._uri = self.terms["conceptUri"].to_numpy(dtype=object)
        self._lab = self.terms["preferredLabel"].to_numpy(dtype=object)

        E = None
        if emb_path is not None and emb_path.exists():
            cached = np.load(emb_path, mmap_mode="r")
            dimension = getattr(encoder, "get_sentence_embedding_dimension", lambda: None)()
            shape_matches = (cached.ndim == 2 and cached.shape[0] == len(self.terms)
                             and (dimension is None or cached.shape[1] == dimension))
            if shape_matches:
                E = np.load(emb_path).astype(np.float32)
                log.info("loaded cached ESCO embeddings %s", E.shape)
            else:
                log.warning("cached ESCO embeddings have shape %s; expected %d terms%s - recomputing.",
                            cached.shape, len(self.terms),
                            f" and dimension {dimension}" if dimension is not None else "")
        if E is None:
            expected_file = emb_path.name if emb_path is not None else "a compatible ESCO embedding index"
            log.warning("computing ESCO term embeddings (%d terms)... provide %s to avoid this.",
                        len(self.terms), expected_file)
            E = encoder.encode(self.terms["term"].tolist(), batch_size=128, show_progress_bar=False,
                               convert_to_numpy=True).astype(np.float32)
            if emb_path is not None:
                try:
                    np.save(emb_path, E)
                except OSError:
                    pass
        self.E = E / np.maximum(np.linalg.norm(E, axis=1, keepdims=True), 1e-9)

    # nearest ESCO labels (cosine) for each text -> scores, indices of shape (n, k)
    def topk(self, texts, k=5, chunk=256):
        texts = [str(t) for t in texts]
        uniq = list(dict.fromkeys(texts))
        q = self.encoder.encode(uniq, batch_size=128, normalize_embeddings=True, convert_to_numpy=True,
                                show_progress_bar=False).astype(np.float32)
        k = min(k, len(self.E))
        sc, ix = np.zeros((len(uniq), k), np.float32), np.zeros((len(uniq), k), np.int64)
        for i in range(0, len(q), chunk):
            s = q[i:i + chunk] @ self.E.T
            if k < s.shape[1]:
                part = np.argpartition(-s, k - 1, axis=1)[:, :k]
            else:
                part = np.tile(np.arange(s.shape[1]), (s.shape[0], 1))
            ps = np.take_along_axis(s, part, 1)
            order = np.argsort(-ps, axis=1)
            ix[i:i + chunk] = np.take_along_axis(part, order, 1)
            sc[i:i + chunk] = np.take_along_axis(ps, order, 1)
        pos = {t: n for n, t in enumerate(uniq)}
        back = np.fromiter((pos[t] for t in texts), dtype=np.int64, count=len(texts))
        return sc[back], ix[back]

    def standardise(self, df: pd.DataFrame) -> pd.DataFrame:
        """df needs 'skill_text'. Adds status, reason, esco_uri, esco_label, similarity, margin, exact, in_esco."""
        df = df.reset_index(drop=True).copy()
        texts = df["skill_text"].astype(str).tolist()
        n = len(texts)
        status, reason = np.array(["rejected"] * n, dtype=object), np.array([""] * n, dtype=object)
        uri, label = np.array([None] * n, dtype=object), np.array([None] * n, dtype=object)
        sim, margin = np.zeros(n), np.zeros(n)
        exact, in_esco = np.zeros(n, bool), np.zeros(n, bool)

        junk = np.array([is_junk(t) for t in texts], dtype=bool)
        reason[junk] = "junk"
        todo = np.where(~junk)[0]
        if len(todo):
            sc, ix = self.topk([texts[i] for i in todo], k=5)
            for r, i in enumerate(todo):
                t, key = texts[i], _norm_key(texts[i])
                ov = self.overrides.get(key)
                if ov and ov[0] == "DROP":
                    reason[i] = "override_drop"
                    continue
                if ov and ov[0] == "MAP" and ov[1] in self.uri_of_label:
                    status[i], uri[i], label[i], sim[i], margin[i], exact[i], in_esco[i] = \
                        "accepted", self.uri_of_label[ov[1]], ov[1], 1.0, 1.0, True, True
                    continue
                j = self.exact.get(key)
                if j is not None:
                    status[i], uri[i], label[i], sim[i], margin[i], exact[i], in_esco[i] = \
                        "accepted", self._uri[j], self._lab[j], 1.0, 1.0, True, True
                    continue
                top = self._uri[ix[r]]
                diff = np.nonzero(top != top[0])[0]
                m = float(sc[r, 0] - sc[r, diff[0]]) if len(diff) else 1.0
                sim[i], margin[i] = float(sc[r, 0]), m
                if NON_SKILL_RE.search(t):
                    reason[i] = "not_skill_words"
                    continue
                if sc[r, 0] >= self.threshold and m >= self.margin:
                    status[i], uri[i], label[i], in_esco[i] = "accepted", top[0], self._lab[ix[r, 0]], True
                elif C.KEEP_CURATED_NON_ESCO and key in self.curated:
                    canon = self.curated[key]
                    status[i], uri[i], label[i], in_esco[i] = \
                        "accepted", "curated:" + re.sub(r"[^a-z0-9]+", "-", canon.lower()).strip("-"), canon, False
                else:
                    reason[i] = "below_threshold" if sc[r, 0] < self.threshold else "ambiguous"
        df["status"], df["reason"], df["esco_uri"], df["esco_label"] = status, reason, uri, label
        df["similarity"], df["margin"], df["exact"], df["in_esco"] = sim, margin, exact, in_esco
        return df


def collapse_to_skills(spans: pd.DataFrame) -> pd.DataFrame:
    """Accepted spans -> one row per document and ESCO skill."""
    acc = spans[spans["status"] == "accepted"].sort_values("similarity", ascending=False)
    if acc.empty:
        return pd.DataFrame(columns=COLLAPSED_COLS)
    return (acc.groupby(["doc_id", "esco_uri"], as_index=False, sort=False)
               .agg(esco_label=("esco_label", "first"), in_esco=("in_esco", "max"), similarity=("similarity", "max"),
                    exact=("exact", "max"), mentions=("skill_text", "size"),
                    surface_forms=("skill_text", lambda s: sorted(set(s))[:5])))
