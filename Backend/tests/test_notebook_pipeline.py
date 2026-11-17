import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.market_intelligence import CORE_MARKET_SKILL, SkillMarketMetrics
from app.notebook_pipeline import NotebookPipeline, RoleNotFound
from app import auth, main


class FakeNotebookEngine:
    ESCO_GRAPH = {
        "parents": {"child": {"parent"}},
        "related": {"child": {"parent"}, "parent": {"child"}},
    }

    @staticmethod
    def available_roles():
        return ["software"]

    @staticmethod
    def get_profile(role):
        profile = pd.DataFrame({
            "esco_uri": ["parent", "child", "rare"],
            "esco_label": ["Programming", "Python", "Kubernetes"],
            "freq": [0.8, 0.6, 0.2],
        })
        return profile, {"source": "static", "reason": "no frozen release for this role yet"}

    @staticmethod
    def score_cv(text, role):
        table = pd.DataFrame({
            "esco_uri": ["parent", "child", "rare"],
            "esco_label": ["Programming", "Python", "Kubernetes"],
            "weight": [0.5, 0.3, 0.2],
            "covered": [True, False, False],
            "reason": ["exact ESCO skill", "gap", "gap"],
            "closest_evidence": ["programming", "", ""],
            "cv_evidence": ["Built programming tools for the team.", "", ""],
            "cv_highlight": ["programming", "", ""],
            "gap_confidence": [0.1, 0.8, 0.9],
        })
        return {
            "table": table,
            "readiness": 0.5,
            "profile": {"source": "static", "reason": "no frozen release for this role yet"},
            "extracted_skills": [
                {"skill": "Programming", "uri": "parent", "in_esco": True, "mentions": 1},
            ],
            "timings_ms": {"extract": 100, "link": 20, "match": 30},
        }


def test_analyze_adapts_notebook_result_to_mobile_contract():
    pipeline = NotebookPipeline(FakeNotebookEngine(), {"child": ["parent"]})

    result = pipeline.analyze("Built programming tools for the team.", "Software")

    assert result["readiness"] == 50.0
    assert result["method"] == "v22_match_v2"
    assert result["n_required"] == 3
    assert result["n_covered"] == 1
    assert result["covered"][0]["credit"] == 1.0
    assert result["covered"][0]["cv_evidence"] == "Built programming tools for the team."
    assert result["covered"][0]["cv_highlight"] == "programming"
    assert result["gaps"][0]["credit"] == 0.0
    assert result["gaps"][0]["gap_confidence"] == 0.8
    assert result["timings_ms"] == {"extract": 100, "link": 20, "match": 30}
    assert result["skill_relationships"][0] == {
        "source": "Programming",
        "target": "Python",
        "type": "prerequisite",
    }
    assert [step["skill"] for step in result["learning_plan"]] == ["Python", "Kubernetes"]
    assert result["learning_plan"][0]["marginal_gain_pp"] == 30.0
    assert "Programming" in result["learning_plan"][0]["cluster_skills"]
    assert all(step["resource"]["url"] for step in result["learning_plan"])
    assert result["market_delta"]["high_roi_gaps"] == [
        {
            "skill": "Python",
            "frequency": 0.6,
            "readiness_gain_pp": 30.0,
            "evidence": "",
            "hiring_evidence": None,
        },
        {
            "skill": "Kubernetes",
            "frequency": 0.2,
            "readiness_gain_pp": 20.0,
            "evidence": "",
            "hiring_evidence": None,
        },
    ]
    assert "marginal CRI gain" in result["market_delta"]["high_roi_note"]
    assert result["market_delta"]["emerging"] is None
    assert result["market_emergence"] is None


def test_analyze_unknown_role_raises_role_not_found():
    pipeline = NotebookPipeline(FakeNotebookEngine())

    with pytest.raises(RoleNotFound):
        pipeline.analyze("resume text", "astronaut")


def test_analysis_uses_configured_learning_catalog(monkeypatch):
    monkeypatch.setattr("app.notebook_pipeline.published_resources", lambda: (
        (("python",), "Custom Python", "Example", "https://example.com/python"),
    ))
    result = NotebookPipeline(FakeNotebookEngine()).analyze("resume", "software")
    assert result["learning_plan"][0]["resource"] == {
        "title": "Custom Python", "provider": "Example", "url": "https://example.com/python",
    }


def test_career_paths_use_available_role_profiles():
    paths = NotebookPipeline(FakeNotebookEngine()).career_paths()

    assert paths == [{
        "role": "software",
        "requirements": [
            {"skill": "Programming", "uri": "parent", "frequency": 0.8},
            {"skill": "Python", "uri": "child", "frequency": 0.6},
            {"skill": "Kubernetes", "uri": "rare", "frequency": 0.2},
        ],
    }]


def test_analyze_resolves_notebook_role_alias():
    pipeline = NotebookPipeline(FakeNotebookEngine())

    result = pipeline.analyze("resume text", "Software Developer")

    assert result["role"] == "software"


def test_market_delta_ranks_gaps_by_marginal_cri_gain_without_frequency_cutoff():
    class LowFrequencyEngine(FakeNotebookEngine):
        @staticmethod
        def get_profile(role):
            profile, info = FakeNotebookEngine.get_profile(role)
            profile["freq"] = [0.4, 0.3, 0.2]
            return profile, info

    result = NotebookPipeline(LowFrequencyEngine()).analyze("resume text", "software")

    assert [gap["skill"] for gap in result["market_delta"]["high_roi_gaps"]] == ["Python", "Kubernetes"]
    assert "marginal CRI gain" in result["market_delta"]["high_roi_note"]


def test_learning_plan_counts_covered_ancestor_skills_once():
    class DescendantEngine(FakeNotebookEngine):
        DESC = {"parent": {"child"}}

    pipeline = NotebookPipeline(DescendantEngine())
    profile, _ = DescendantEngine.get_profile("software")
    requirements = [
        {"skill": "Programming", "uri": "parent", "weight": 0.5, "credit": 0},
        {"skill": "Python", "uri": "child", "weight": 0.3, "credit": 0},
        {"skill": "Kubernetes", "uri": "rare", "weight": 0.2, "credit": 0},
    ]

    plan = pipeline._learning_plan(profile, requirements, [], {})

    assert [step["skill"] for step in plan] == ["Python", "Kubernetes", "Programming"]
    assert [step["marginal_gain_pp"] for step in plan] == [80.0, 20.0, 0.0]
    assert plan[0]["cluster_gain_pp"] == 80.0
    assert plan[2]["covered_by"] == "Python"


def test_learning_plan_obeys_prerequisites_before_impact_order():
    class DependencyEngine(FakeNotebookEngine):
        @staticmethod
        def get_profile(role):
            profile, info = FakeNotebookEngine.get_profile(role)
            profile["freq"] = [0.8, 0.6, 0.5]
            profile["weight"] = [0.1, 0.2, 0.7]
            return profile, info

        @staticmethod
        def score_cv(text, role):
            result = FakeNotebookEngine.score_cv(text, role)
            result["table"]["weight"] = [0.1, 0.2, 0.7]
            return result

    result = NotebookPipeline(
        DependencyEngine(),
        prerequisites={"rare": ["child"]},
    ).analyze("resume text", "software")

    assert [step["skill"] for step in result["learning_plan"]] == ["Python", "Kubernetes"]
    assert result["learning_plan"][1]["prerequisites"] == ["Python"]


def test_analysis_includes_market_intelligence_from_profile_provider():
    class MarketProvider:
        @staticmethod
        def market_metrics_for_role(role):
            assert role == "software"
            return {
                "parent": SkillMarketMetrics(
                    esco_uri="parent",
                    skill_name="Different label",
                    posting_count=10,
                    role_count=2,
                    frequency=0.8,
                    role_penetration=1.0,
                    growth_rate=0.2,
                    recency_score=0.8,
                    demand_percentile=100.0,
                    commonness_score=80.0,
                    classification=CORE_MARKET_SKILL,
                    confidence="low",
                ),
                "new-core": SkillMarketMetrics(
                    esco_uri="new-core",
                    skill_name="Unowned core skill",
                    posting_count=9,
                    role_count=2,
                    frequency=0.7,
                    role_penetration=1.0,
                    growth_rate=0.2,
                    recency_score=0.8,
                    demand_percentile=100.0,
                    commonness_score=75.0,
                    classification=CORE_MARKET_SKILL,
                    confidence="low",
                ),
            }

        @staticmethod
        def market_emergence_for_role(role):
            assert role == "software"
            return {
                "role": role,
                "period_days": 30,
                "current_postings": 10,
                "previous_postings": 8,
                "skills": [{
                    "esco_uri": "uri:python",
                    "skill": "Python",
                    "history": [10.0, 15.0, 20.0, 40.0],
                    "previous_frequency": 20.0,
                    "current_frequency": 40.0,
                    "delta_pp": 20.0,
                    "emergence_score": 8.0,
                    "status": "rising",
                }],
            }

    class MarketEngine(FakeNotebookEngine):
        _PROFILE_PROVIDER = MarketProvider()

    result = NotebookPipeline(MarketEngine()).analyze("resume text", "software")

    assert [skill["esco_uri"] for skill in result["market_intelligence"]["missing_core"]] == ["new-core"]
    assert result["market_intelligence"]["market_alignment_score"] > 0
    assert result["market_emergence"]["skills"][0]["delta_pp"] == 20.0


def test_notebook_analysis_is_serialized_by_api(monkeypatch):
    monkeypatch.setenv("SKIP_LOAD", "1")
    monkeypatch.setattr(auth, "REQUIRE_AUTH", False)
    auth._hits.clear()
    main.STATE.update(pipeline=NotebookPipeline(FakeNotebookEngine(), {"child": ["parent"]}), error=None)

    try:
        with TestClient(main.app) as client:
            response = client.post("/analyze", data={"role": "software", "text": "resume text"})
            paths_response = client.get("/career-paths")
        assert response.status_code == 200
        assert response.json()["market_delta"]["high_roi_gaps"][0]["skill"] == "Python"
        assert "marginal CRI gain" in response.json()["market_delta"]["high_roi_note"]
        assert response.json()["market_emergence"] is None
        assert response.json()["learning_plan"]
        assert paths_response.status_code == 200
        assert paths_response.json()[0]["role"] == "software"
    finally:
        main.STATE.update(pipeline=None, error=None)
