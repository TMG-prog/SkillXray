from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from app.posting_profiles import DatabaseProfileProvider, build_database_profile

COMMON_SKILLS = [
    "python", "communication", "planning", "analysis", "teamwork",
    "reporting", "research", "documentation", "leadership",
]


class FakeEngine:
    EXTRACTION_CFG = {}

    def __init__(self):
        self.extraction_calls = 0

    def extract_docs(self, texts, ids, _cfg):
        self.extraction_calls += 1
        rows = []
        for doc_id, text in zip(ids, texts):
            for label in text.split("|"):
                label = label.strip()
                if label in COMMON_SKILLS or label in {"sql", "borderline", "rare"}:
                    rows.append({
                        "doc_id": doc_id,
                        "esco_uri": f"uri:{label}",
                        "esco_label": label.title(),
                        "in_esco": True,
                        "status": "accepted",
                    })
                elif label.startswith("raw:"):
                    rows.append({
                        "doc_id": doc_id,
                        "skill_text": label.removeprefix("raw:"),
                        "status": "rejected",
                        "reason": "below_threshold",
                    })
        return pd.DataFrame(rows)

    @staticmethod
    def standardise_spans(spans):
        return spans

    @staticmethod
    def collapse_to_skills(spans):
        if "status" in spans.columns:
            spans = spans[spans["status"].eq("accepted")]
        return spans.drop_duplicates(["doc_id", "esco_uri"])

    @staticmethod
    def _apply_blocklist(profile):
        return profile


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.start = None
        self.country = None
        self.offset = 0
        self.end = 999

    def select(self, _columns):
        return self

    def gte(self, column, value):
        assert column == "posted_at"
        self.start = datetime.fromisoformat(value)
        return self

    def eq(self, column, value):
        assert column == "country"
        self.country = value
        return self

    def order(self, _column, desc=False):
        self.rows = sorted(self.rows, key=lambda row: row["fetched_at"], reverse=desc)
        return self

    def range(self, start, end):
        self.offset, self.end = start, end
        return self

    def execute(self):
        rows = [
            row for row in self.rows
            if datetime.fromisoformat(row["posted_at"]) >= self.start
            and (self.country is None or row["country"] == self.country)
        ]
        return SimpleNamespace(data=rows[self.offset:self.end + 1])


class FakeSupabase:
    def __init__(self, rows):
        self.rows = rows

    def table(self, _name):
        return FakeQuery(self.rows)


def _posting(index, now, *, role="software", country="us", posted_at=None):
    skills = list(COMMON_SKILLS)
    if index < 6:
        skills.append("sql")
    if index < 5:
        skills.append("borderline")
    if index < 2:
        skills.append("rare")
    description = "|".join(skills) + "|" + ("long description " * 40)
    return {
        "id": str(index),
        "role_key": role,
        "description": description,
        "title": f"Software Engineer {index}",
        "posted_at": posted_at or (now - timedelta(days=2)).isoformat(),
        "fetched_at": (now - timedelta(days=1)).isoformat(),
        "country": country,
    }


def test_build_database_profile_matches_notebook_frequency_rules():
    now = datetime.now(timezone.utc)
    postings = [_posting(index, now) for index in range(30)]
    profile, info = build_database_profile(FakeEngine(), "software", postings)

    assert info["source"] == "database"
    assert info["n_postings"] == 30
    assert not info["reason"]
    assert "uri:rare" not in set(profile["esco_uri"])
    assert "uri:borderline" not in set(profile["esco_uri"])
    assert profile.loc[profile["esco_uri"] == "uri:sql", "freq"].item() == 6 / 30
    assert profile["weight"].sum() == pytest.approx(1.0)
    assert profile["n_postings"].eq(30).all()


def test_provider_loads_recent_market_rows_and_builds_profiles_lazily():
    now = datetime.now(timezone.utc)
    rows = [_posting(index, now) for index in range(30)]
    rows.extend([
        _posting(31, now, country="ke"),
        _posting(
            32,
            now,
            posted_at=(now - timedelta(days=31)).isoformat(),
        ),
    ])
    engine = FakeEngine()
    provider = DatabaseProfileProvider(
        FakeSupabase(rows), engine, now=now, country="us"
    )

    assert provider.available_roles() == ["software"]
    assert engine.extraction_calls == 0
    profile, info = provider.get_profile("software")
    assert info["source"] == "database"
    assert len(profile) == 10
    assert engine.extraction_calls == 1


def test_provider_reports_short_role_as_fallback_not_database_profile():
    now = datetime.now(timezone.utc)
    provider = DatabaseProfileProvider(
        FakeSupabase([_posting(index, now) for index in range(5)]),
        FakeEngine(),
        now=now,
    )

    assert provider.available_roles() == []
    assert provider.get_profile("software") is None
    assert provider.fallback_reason("software") == "only 5 recent JSearch postings (< 30)"


def test_provider_computes_market_metrics_from_120_day_history():
    now = datetime.now(timezone.utc)
    rows = [_posting(index, now) for index in range(30)]
    rows.append(_posting(
        31,
        now,
        posted_at=(now - timedelta(days=35)).isoformat(),
    ))
    engine = FakeEngine()
    provider = DatabaseProfileProvider(FakeSupabase(rows), engine, now=now)

    metrics = provider.market_metrics_for_role("software")

    assert "uri:python" in metrics
    assert metrics["uri:python"].posting_count == 31
    assert metrics["uri:python"].role_count == 1
    assert metrics["uri:rare"].posting_count == 2
    assert engine.extraction_calls == 1


def test_provider_exposes_cached_role_specific_market_emergence():
    now = datetime.now(timezone.utc)
    rows = []
    for age, sql_count, prefix, count in (
        (100, 2, "baseline", 30),
        (5, 8, "recent", 10),
    ):
        for index in range(count):
            posting = _posting(index, now, posted_at=(now - timedelta(days=age)).isoformat())
            posting["id"] = f"{prefix}-{index}"
            posting["title"] = f"{prefix.title()} Software Engineer {index}"
            skills = ["python"] + (["sql"] if index < sql_count else [])
            posting["description"] = "|".join(skills) + "|" + ("long description " * 40)
            rows.append(posting)
    rows.extend(_posting(index + 100, now, role="data") for index in range(10))
    engine = FakeEngine()
    provider = DatabaseProfileProvider(FakeSupabase(rows), engine, now=now)

    report = provider.market_emergence_for_role("software")

    assert report["current_postings"] == 10
    assert report["previous_postings"] == 30
    sql = next(skill for skill in report["skills"] if skill["esco_uri"] == "uri:sql")
    assert sql["recent_count"] == 8
    assert sql["baseline_count"] == 2
    assert sql["history"][1] > sql["history"][0]
    assert all(skill["esco_uri"] != "uri:other" for skill in report["skills"])
    assert engine.extraction_calls == 1


def test_provider_deduplicates_reposts_but_keeps_country_scoped_copies():
    now = datetime.now(timezone.utc)
    original = _posting(1, now, posted_at=(now - timedelta(days=200)).isoformat())
    repost = {
        **original,
        "id": "repost",
        "posted_at": (now - timedelta(days=20)).isoformat(),
    }
    other_country = {
        **original,
        "id": "other-country",
        "country": "ke",
    }
    provider = DatabaseProfileProvider(
        FakeSupabase([original, repost, other_country]),
        FakeEngine(),
        now=now,
    )

    postings = provider.market_postings["software"]

    assert len(postings) == 2
    assert {posting["id"] for posting in postings} == {"repost", "other-country"}


def test_provider_includes_unmapped_terms_in_trend_signals():
    now = datetime.now(timezone.utc)
    rows = []
    aliases = ("GenAI", "generative AI", "LLM apps", "generative artificial intelligence")
    for age, prefix, count in ((100, "baseline", 30), (5, "recent", 10)):
        for index in range(count):
            posting = _posting(index, now, posted_at=(now - timedelta(days=age)).isoformat())
            posting["id"] = f"{prefix}-{index}"
            posting["title"] = f"{prefix.title()} Software Engineer {index}"
            text = "python|" + ("raw:" + aliases[index % len(aliases)] if prefix == "recent" and index < 6 else "")
            posting["description"] = text + "|" + ("long description " * 40)
            rows.append(posting)
    provider = DatabaseProfileProvider(FakeSupabase(rows), FakeEngine(), now=now)

    report = provider.market_emergence_for_role("software")
    genai = next(skill for skill in report["skills"] if skill["skill_id"] == "term:generative-ai-llm-applications")

    assert genai["is_esco"] is False
    assert genai["first_seen"] is True
    assert genai["status"] == "core"
    assert genai["recent_count"] == 6
    assert len(genai["sample_postings"]) == 3


def test_provider_reports_skill_cooccurrence_with_resume_skills_and_role_baseline():
    now = datetime.now(timezone.utc)
    rows = []
    for index in range(30):
        skills = COMMON_SKILLS[1:]
        if index < 5:
            skills += ["python"]
        if index < 3:
            skills += ["sql"]
        rows.append({
            **_posting(index, now),
            "description": "|".join(skills) + "|" + ("long description " * 40),
        })
    provider = DatabaseProfileProvider(FakeSupabase(rows), FakeEngine(), now=now)

    evidence = provider.skill_cooccurrence_for_role(
        "software",
        {"uri:python"},
        {"uri:sql"},
    )["uri:sql"]

    assert evidence == {
        "sample_size": 5,
        "posting_count": 3,
        "frequency": 0.6,
        "baseline_frequency": 0.1,
        "personalized": True,
        "evidence": (
            "3 of 5 role postings that also list at least one skill from your resume (60%) "
            "also list this skill; the role-wide rate is 10% (3 of 30 postings)."
        ),
    }
