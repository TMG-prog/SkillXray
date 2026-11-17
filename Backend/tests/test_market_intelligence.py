from datetime import date, timedelta

from app.market_intelligence import (
    COMMON_SKILL,
    CORE_MARKET_SKILL,
    DECLINING_SKILL,
    EMERGING_SKILL,
    NICHE_SKILL,
    STABLE_SKILL,
    SkillMarketMetrics,
    calculate_commonness_score,
    classify_skill,
    canonicalize_unmapped_term,
    compute_emergence_table,
    compute_skill_metrics,
    detect_skill_gaps,
)

REFERENCE = date(2026, 6, 1)


def _metrics(**overrides) -> SkillMarketMetrics:
    values = {
        "esco_uri": "uri:skill",
        "skill_name": "Display label",
        "posting_count": 10,
        "role_count": 3,
        "frequency": 0.6,
        "role_penetration": 0.5,
        "growth_rate": 0.0,
        "recency_score": 0.8,
        "demand_percentile": 95.0,
        "commonness_score": 70.0,
        "classification": STABLE_SKILL,
        "confidence": "low",
    }
    return SkillMarketMetrics(**(values | overrides))


def _posting(job_id: str, posted_date: date, role: str, *skills: tuple[str, str]) -> dict:
    return {
        "job_id": job_id,
        "posted_date": posted_date,
        "role_family": role,
        "country": "us",
        "esco_skills": [
            {"esco_uri": uri, "label": label}
            for uri, label in skills
        ],
    }


def test_core_skill_classification():
    assert classify_skill(_metrics(classification="")) == CORE_MARKET_SKILL


def test_common_skill_classification():
    assert classify_skill(_metrics(demand_percentile=75, frequency=0.2)) == COMMON_SKILL


def test_emerging_skill_classification():
    assert classify_skill(_metrics(
        demand_percentile=40,
        frequency=0.05,
        role_penetration=0.25,
        growth_rate=0.35,
        recency_score=0.9,
    )) == EMERGING_SKILL


def test_niche_skill_classification():
    assert classify_skill(_metrics(
        demand_percentile=20,
        frequency=0.05,
        role_penetration=0.1,
        growth_rate=0.0,
    )) == NICHE_SKILL


def test_declining_skill_requires_multiple_negative_periods():
    assert classify_skill(_metrics(
        demand_percentile=40,
        frequency=0.3,
        role_penetration=0.3,
        growth_rate=-0.3,
        negative_periods=2,
    )) == DECLINING_SKILL
    assert classify_skill(_metrics(
        demand_percentile=40,
        frequency=0.3,
        role_penetration=0.3,
        growth_rate=-0.3,
        negative_periods=1,
    )) == STABLE_SKILL


def test_empty_dataset_returns_no_metrics():
    assert compute_skill_metrics([], REFERENCE) == {}
    assert calculate_commonness_score(0, 0, 0, None) == 10.0


def test_single_posting_is_supported_with_low_confidence_and_zero_baseline_growth():
    metrics = compute_skill_metrics(
        [_posting("job-1", REFERENCE, "software", ("uri:python", "Python"))],
        REFERENCE,
    )

    skill = metrics["uri:python"]
    assert skill.posting_count == 1
    assert skill.frequency == 1.0
    assert skill.role_count == 1
    assert skill.role_penetration == 1.0
    assert skill.growth_rate is None
    assert skill.confidence == "low"
    assert skill.classification == CORE_MARKET_SKILL


def test_growth_handles_zero_previous_demand():
    postings = [
        _posting("current", REFERENCE, "software", ("uri:python", "Python")),
        _posting("previous", REFERENCE - timedelta(days=35), "software"),
    ]

    assert compute_skill_metrics(postings, REFERENCE)["uri:python"].growth_rate == 1.0


def test_metrics_use_uri_identity_and_support_region_scope():
    postings = [
        _posting("1", REFERENCE, "software", ("uri:python", "Python")),
        _posting("2", REFERENCE - timedelta(days=35), "data", ("uri:python", "Python 3")),
        _posting("3", REFERENCE - timedelta(days=10), "software", ("uri:sql", "SQL")),
        {
            **_posting("4", REFERENCE, "health", ("uri:python", "Python")),
            "region": "eu",
        },
    ]

    metrics = compute_skill_metrics(postings, REFERENCE, region="us")

    assert metrics["uri:python"].posting_count == 2
    assert metrics["uri:python"].role_count == 2
    assert metrics["uri:python"].role_penetration == 1.0
    assert metrics["uri:python"].frequency == 2 / 3
    assert metrics["uri:python"].growth_rate == -0.5
    assert metrics["uri:python"].skill_name == "Python"
    assert metrics["uri:sql"].posting_count == 1


def test_gap_analysis_matches_only_by_uri():
    metrics = {
        "uri:core": _metrics(
            esco_uri="uri:core",
            classification=CORE_MARKET_SKILL,
            commonness_score=90,
        ),
        "uri:common": _metrics(
            esco_uri="uri:common",
            classification=COMMON_SKILL,
            commonness_score=70,
        ),
        "uri:emerging": _metrics(
            esco_uri="uri:emerging",
            classification=EMERGING_SKILL,
            commonness_score=50,
        ),
        "uri:declining": _metrics(
            esco_uri="uri:declining",
            classification=DECLINING_SKILL,
            commonness_score=30,
        ),
    }

    report = detect_skill_gaps(
        [
            {"esco_uri": "uri:common", "label": "a totally different display label"},
            {"esco_uri": "uri:declining", "label": "Old skill"},
        ],
        metrics,
    )

    assert [skill["esco_uri"] for skill in report["missing_core"]] == ["uri:core"]
    assert report["missing_common"] == []
    assert [skill["esco_uri"] for skill in report["missing_emerging"]] == ["uri:emerging"]
    assert [skill["esco_uri"] for skill in report["declining_owned_skills"]] == ["uri:declining"]
    assert report["market_alignment_score"] == 41.67


def test_empty_market_gap_analysis_has_zero_alignment():
    assert detect_skill_gaps([], {}) == {
        "missing_core": [],
        "missing_common": [],
        "missing_emerging": [],
        "declining_owned_skills": [],
        "market_alignment_score": 0.0,
    }


def test_declining_classification_is_computed_from_multiple_periods():
    postings = []
    period_start_days = (100, 70, 40, 10)
    skill_counts = (4, 3, 2, 1)
    for period, (age, count) in enumerate(zip(period_start_days, skill_counts)):
        for index in range(4):
            skills = (("uri:popular", "Popular skill"),)
            if index < count:
                skills += (("uri:decline", "Declining skill"),)
            postings.append(_posting(
                f"{period}-{index}",
                REFERENCE - timedelta(days=age),
                "software",
                *skills,
            ))

    metric = compute_skill_metrics(postings, REFERENCE)["uri:decline"]

    assert metric.growth_rate == -0.5
    assert metric.negative_periods == 3
    assert metric.classification == DECLINING_SKILL


def test_emergence_table_compares_smoothed_90_day_window_to_nine_month_baseline():
    postings = []
    for index in range(30):
        skills = [("uri:core", "Core skill")]
        if index < 25:
            skills.append(("uri:common", "Common skill"))
        if index < 12:
            skills.append(("uri:stable", "Stable skill"))
        if index < 6:
            skills.append(("uri:rising", "Rising skill"))
        if index < 15:
            skills.append(("uri:declining", "Declining skill"))
        postings.append(_posting(
            f"baseline-{index}",
            REFERENCE - timedelta(days=100),
            "software",
            *skills,
        ))

    variants = ("GenAI", "generative AI", "LLM apps", "generative artificial intelligence")
    for index in range(20):
        skills = [("uri:core", "Core skill")]
        if index < 18:
            skills.append(("uri:common", "Common skill"))
        if index < 8:
            skills.extend((("uri:stable", "Stable skill"), ("uri:rising", "Rising skill")))
        if index == 0:
            skills.append(("uri:declining", "Declining skill"))
        posting = _posting(
            f"recent-{index}",
            REFERENCE - timedelta(days=10),
            "software",
            *skills,
        )
        posting["title"] = f"Software Engineer {index}"
        if index < 6:
            posting["unmapped_skills"] = [variants[index % len(variants)]]
        if index < 4:
            posting["unmapped_skills"].append("rare experimental term")
        postings.append(posting)

    postings.append({
        **_posting("outside-region", REFERENCE - timedelta(days=10), "software", ("uri:outside", "Other region skill")),
        "country": "ca",
    })
    postings.append(
        _posting("other-role", REFERENCE - timedelta(days=10), "data", ("uri:other", "Other role skill"))
    )
    report = compute_emergence_table(postings, "software", REFERENCE, region="us", limit=20)

    assert report["role"] == "software"
    assert report["country"] == "us"
    assert report["recent_window_days"] == 90
    assert report["baseline_window_days"] == 275
    assert report["minimum_skill_support"] == 5
    assert report["minimum_recent_postings"] == 10
    assert report["minimum_baseline_postings"] == 20
    assert report["current_postings"] == 20
    assert report["previous_postings"] == 30
    assert report["data_sufficient"] is True
    skills = {skill["skill_id"]: skill for skill in report["skills"]}

    rising = skills["esco:uri:rising"]
    assert rising["status"] == "rising"
    assert rising["baseline_count"] == 6
    assert rising["recent_count"] == 8
    assert rising["history"][1] > rising["history"][0]
    assert rising["sample_postings"][0]["title"] == "Software Engineer 7"
    assert "8/20 recent postings" in rising["evidence"]
    assert skills["esco:uri:core"]["status"] == "core"
    assert skills["esco:uri:declining"]["status"] == "declining"
    assert skills["esco:uri:stable"]["status"] == "stable"

    generative_ai = skills["term:generative-ai-llm-applications"]
    assert generative_ai["is_esco"] is False
    assert generative_ai["skill"] == "Generative AI / LLM Applications"
    assert generative_ai["status"] == "rising"
    assert generative_ai["recent_count"] == 6
    assert "term:rare-experimental-term" not in skills
    assert canonicalize_unmapped_term("large language model applications") == generative_ai["skill"]


def test_emergence_table_returns_no_trends_without_two_comparable_periods():
    report = compute_emergence_table(
        [_posting("current", REFERENCE, "software", ("uri:python", "Python"))],
        "software",
        REFERENCE,
    )

    assert report["current_postings"] == 1
    assert report["previous_postings"] == 0
    assert report["skills"] == []


def test_emergence_table_includes_window_start_boundaries_and_excludes_out_of_range_dates():
    postings = [
        _posting("recent-start", REFERENCE - timedelta(days=90), "software"),
        _posting("baseline-start", REFERENCE - timedelta(days=365), "software"),
        _posting("before-history", REFERENCE - timedelta(days=366), "software"),
        _posting("future", REFERENCE + timedelta(days=1), "software"),
    ]

    report = compute_emergence_table(postings, "software", REFERENCE, region="us")

    assert report["recent_window_start"] == (REFERENCE - timedelta(days=90)).isoformat()
    assert report["recent_window_end"] == REFERENCE.isoformat()
    assert report["baseline_window_start"] == (REFERENCE - timedelta(days=365)).isoformat()
    assert report["baseline_window_end"] == (REFERENCE - timedelta(days=90)).isoformat()
    assert report["current_postings"] == 1
    assert report["previous_postings"] == 1
