from datetime import datetime, timedelta, timezone
import pandas as pd
import pytest

from app.ict_analysis import IctFilter, analyze_ict_postings


@pytest.fixture
def esco_dir(tmp_path):
    pd.DataFrame([
        ("ict", "2512", "software developer", "developer\nshared title"),
        ("other", "2221", "nurse", "shared title"),
        ("technician", "3512", "ICT technician", ""),
    ], columns=["conceptUri", "iscoGroup", "preferredLabel", "altLabels"]).to_csv(
        tmp_path / "occupations_en.csv", index=False,
    )
    pd.DataFrame([
        ("ict", "essential", "soft"),
        ("ict", "optional", "optional"),
        ("other", "essential", "other"),
    ], columns=["occupationUri", "relationType", "skillUri"]).to_csv(
        tmp_path / "occupationSkillRelations_en.csv", index=False,
    )
    pd.DataFrame([
        ("S", "S5", "s-root"), ("K", "06", "k-root"),
    ], columns=["Level 0 code", "Level 1 code", "Level 1 URI"]).to_csv(
        tmp_path / "skillsHierarchy_en.csv", index=False,
    )
    pd.DataFrame([
        ("s-child", "s-root"), ("digital", "s-child"),
        ("knowledge", "k-root"), ("s-root", "s-child"),
    ], columns=["conceptUri", "broaderUri"]).to_csv(
        tmp_path / "broaderRelationsSkillPillar_en.csv", index=False,
    )
    pd.DataFrame({"conceptUri": ["soft", "optional", "other", "digital", "knowledge"]}).to_csv(
        tmp_path / "skills_en.csv", index=False,
    )
    return tmp_path


def test_ict_filter_uses_union_and_rejects_ambiguous_titles(esco_dir):
    ict_filter = IctFilter(esco_dir)
    assert ict_filter.skill_uris == {"soft", "digital", "knowledge"}
    assert ict_filter.classify_title("  DEVELOPER  ") == "ict"
    assert ict_filter.classify_title("ICT technician") == "ict"
    assert ict_filter.classify_title("nurse") == "non_ict"
    assert ict_filter.classify_title("shared title") == "ambiguous"
    assert ict_filter.classify_title("senior developer") == "unmatched"


def test_ict_analysis_counts_only_selected_postings_and_deduplicates_skills(esco_dir):
    now = datetime(2026, 11, 26, tzinfo=timezone.utc)

    def posting(index, title, days=1):
        return {
            "id": str(index), "title": title, "description": "skills", "role_key": "software",
            "posted_at": (now - timedelta(days=days)).isoformat(), "country": "us",
        }

    class Engine:
        EXTRACTION_CFG = {}

        def extract_docs(self, texts, ids, config):
            assert ids == ["1", "2"]
            return pd.DataFrame([
                ("1", "digital", "Digital"), ("1", "digital", "Digital"),
                ("1", "optional", "Optional"), ("2", "soft", "Soft"),
            ], columns=["doc_id", "esco_uri", "esco_label"])

        def standardise_spans(self, spans):
            return spans

        def collapse_to_skills(self, spans):
            return spans

    postings = [
        posting(1, "developer"), posting(2, "software developer"),
        posting(3, "nurse"), posting(4, "shared title"), posting(5, "senior developer"),
        posting(6, "developer", 120),
    ]
    report = analyze_ict_postings(Engine(), postings, IctFilter(esco_dir), now, "us")
    assert report["posting_counts"] == {"ict": 2, "non_ict": 1, "unmatched": 1, "ambiguous": 1}
    assert report["excluded_titles"]["ambiguous"] == [{"title": "shared title", "count": 1}]
    metrics = {row["esco_uri"]: row for row in report["skills"]}
    assert set(metrics) == {"digital", "soft"}
    assert metrics["digital"]["posting_count"] == 1
    assert metrics["digital"]["frequency"] == 0.5


def test_ict_filter_reports_missing_files(esco_dir):
    (esco_dir / "skillsHierarchy_en.csv").unlink()
    with pytest.raises(FileNotFoundError):
        IctFilter(esco_dir)


def test_ict_analysis_with_no_matched_postings_does_not_extract(esco_dir):
    now = datetime(2026, 11, 26, tzinfo=timezone.utc)
    postings = [{
        "id": "1", "title": "senior developer", "description": "skills",
        "posted_at": now.isoformat(),
    }]
    report = analyze_ict_postings(None, postings, IctFilter(esco_dir), now, None)
    assert report["posting_counts"]["unmatched"] == 1
    assert report["skills"] == []
