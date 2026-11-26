"""Opt-in ICT occupation and digital skill analysis using ESCO."""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
import unicodedata

import pandas as pd

from .market_intelligence import RECENCY_DAYS, compute_skill_metrics


def _read_csv(directory: Path, filename: str, columns: set[str]) -> pd.DataFrame:
    path = directory / filename
    data = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = columns - set(data.columns)
    if missing:
        raise ValueError(f"{path} is missing required columns: {', '.join(sorted(missing))}")
    return data


def _title_key(title: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", title).casefold().split())


class IctFilter:
    def __init__(self, directory: Path):
        occupations = _read_csv(directory, "occupations_en.csv", {
            "conceptUri", "iscoGroup", "preferredLabel", "altLabels",
        })
        relations = _read_csv(directory, "occupationSkillRelations_en.csv", {
            "occupationUri", "skillUri", "relationType",
        })
        hierarchy = _read_csv(directory, "skillsHierarchy_en.csv", {
            "Level 0 code", "Level 1 code", "Level 1 URI",
        })
        broader = _read_csv(directory, "broaderRelationsSkillPillar_en.csv", {
            "conceptUri", "broaderUri",
        })
        skills = _read_csv(directory, "skills_en.csv", {"conceptUri"})

        self.titles: dict[str, set[str]] = defaultdict(set)
        self.ict_occupations: set[str] = set()
        for row in occupations.itertuples(index=False):
            uri = row.conceptUri.strip()
            if not uri:
                continue
            if row.iscoGroup.strip().startswith(("25", "35")):
                self.ict_occupations.add(uri)
            for label in [row.preferredLabel, *row.altLabels.splitlines()]:
                key = _title_key(label)
                if key:
                    self.titles[key].add(uri)
        if not self.ict_occupations:
            raise ValueError("ESCO occupations contain no ISCO 25 or 35 occupations")

        essential = set(relations.loc[
            relations["occupationUri"].isin(self.ict_occupations)
            & relations["relationType"].str.strip().str.casefold().eq("essential"),
            "skillUri",
        ])
        roots = set()
        for root, code in (("S", "S5"), ("K", "06")):
            found = set(hierarchy.loc[
                hierarchy["Level 0 code"].eq(root) & hierarchy["Level 1 code"].eq(code),
                "Level 1 URI",
            ]) - {""}
            if len(found) != 1:
                raise ValueError(f"Expected exactly one ESCO hierarchy root for {root}/{code}, found {len(found)}")
            roots.update(found)
        children: dict[str, set[str]] = defaultdict(set)
        for child, parent in zip(broader["conceptUri"], broader["broaderUri"]):
            children[parent].add(child)
        descendants = set(roots)
        pending = deque(roots)
        while pending:
            for child in children[pending.popleft()] - descendants:
                descendants.add(child)
                pending.append(child)
        skill_uris = set(skills["conceptUri"]) - {""}
        self.skill_uris = (essential | descendants) & skill_uris
        if not essential or not (descendants & skill_uris) or not self.skill_uris:
            raise ValueError("ESCO ICT essential skills or hierarchy descendants are empty")

    def classify_title(self, title: str) -> str:
        matches = self.titles.get(_title_key(title), set())
        if not matches:
            return "unmatched"
        if len(matches) != 1:
            return "ambiguous"
        return "ict" if next(iter(matches)) in self.ict_occupations else "non_ict"


def analyze_ict_postings(engine, postings: list[dict], ict_filter: IctFilter,
                         now: datetime, country: str | None) -> dict:
    """Compute posting demand after conservative ESCO occupation and skill filtering."""
    cutoff = now - timedelta(days=RECENCY_DAYS)
    counts: Counter[str] = Counter()
    rejected_titles: dict[str, Counter[str]] = {
        "unmatched": Counter(), "ambiguous": Counter(),
    }
    selected = []
    for posting in postings:
        posted_at = datetime.fromisoformat(str(posting["posted_at"]).replace("Z", "+00:00"))
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=now.tzinfo)
        if not cutoff < posted_at <= now:
            continue
        title = str(posting.get("title") or "").strip()
        category = ict_filter.classify_title(title)
        counts[category] += 1
        if category in rejected_titles:
            rejected_titles[category][title or "(empty title)"] += 1
        if category == "ict":
            selected.append(posting)

    skills_by_job: dict[str, dict[str, str]] = {}
    if selected:
        ids = [str(posting["id"]) for posting in selected]
        texts = [str(posting["description"]) for posting in selected]
        spans = engine.extract_docs(texts, ids, engine.EXTRACTION_CFG)
        if spans is not None and len(spans):
            linked = engine.collapse_to_skills(engine.standardise_spans(spans))
            if linked is not None:
                for row in linked.itertuples(index=False):
                    uri = str(row.esco_uri)
                    if uri in ict_filter.skill_uris:
                        skills_by_job.setdefault(str(row.doc_id), {})[uri] = str(row.esco_label)

    market_postings = [{
        "job_id": str(posting["id"]),
        "posted_date": posting["posted_at"],
        "role_family": str(posting.get("role_key") or ""),
        "region": posting.get("country"),
        "esco_skills": [
            {"esco_uri": uri, "label": label}
            for uri, label in sorted(skills_by_job.get(str(posting["id"]), {}).items())
        ],
    } for posting in selected]
    metrics = compute_skill_metrics(market_postings, now, region=country)
    return {
        "window_days": RECENCY_DAYS,
        "window_start": cutoff.isoformat(),
        "window_end": now.isoformat(),
        "country": country,
        "posting_counts": {category: counts[category] for category in ("ict", "non_ict", "unmatched", "ambiguous")},
        "excluded_titles": {
            category: [{"title": title, "count": count} for title, count in sorted(
                title_counts.items(), key=lambda item: (-item[1], item[0])
            )[:20]]
            for category, title_counts in rejected_titles.items()
        },
        "skills": [asdict(metric) for metric in sorted(
            metrics.values(), key=lambda metric: (-metric.posting_count, metric.skill_name, metric.esco_uri)
        )],
    }
