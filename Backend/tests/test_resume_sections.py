import pandas as pd

from app.resume_sections import apply_section_credit, parse_resume_sections, section_for_text


def test_resume_sections_recognize_common_heading_variants():
    sections = parse_resume_sections(
        "Professional Summary\nBuilds software.\n"
        "EDUCATION: BSc Computer Science; studied Python.\n"
        "Selected Projects\nBuilt a Docker deployment.\n"
        "Work Experience\nUsed Python to automate reports."
    )

    assert section_for_text("studied Python", sections) == "education"
    assert section_for_text("Built a Docker deployment", sections) == "projects"
    assert section_for_text("Used Python to automate reports", sections) == "experience"


def test_unrecognized_resume_headings_preserve_full_credit():
    assert parse_resume_sections("Builds software with Python.") == []

    table = pd.DataFrame({
        "esco_uri": ["python"],
        "covered": [True],
        "reason": ["exact match"],
        "cv_evidence": ["Builds software with Python."],
    })
    result = apply_section_credit(table, pd.DataFrame(), None, [])

    assert result.loc[0, "credit"] == 1.0
    assert result.loc[0, "evidence_section"] is None


def test_education_evidence_gets_full_credit_and_section_provenance():
    sections = parse_resume_sections(
        "Education\nStudied Java, Python, and Docker.\n"
        "Projects\nBuilt a deployment with Docker.\n"
        "Experience\nUsed Python to automate reports."
    )
    table = pd.DataFrame({
        "esco_uri": ["java", "python", "docker", "kubernetes"],
        "covered": [True, True, True, False],
        "reason": ["exact match", "exact match", "exact match", "gap"],
        "cv_evidence": [
            "Studied Java.",
            "Studied Python.",
            "Built a deployment with Docker.",
            "",
        ],
    })
    candidates = pd.DataFrame({
        "esco_uri": ["java", "python", "docker"],
        "esco_label": ["Java", "Python", "Docker"],
    })
    spans = pd.DataFrame({
        "status": ["accepted", "accepted", "accepted", "accepted", "accepted"],
        "esco_uri": ["java", "python", "python", "docker", "docker"],
        "resume_section": [
            "education", "education", "experience", "education", "projects",
        ],
    })

    result = apply_section_credit(table, candidates, spans, sections)

    assert result["credit"].tolist() == [1.0, 1.0, 1.0, 0.0]
    assert result["covered"].tolist() == [True, True, True, False]
    assert result["evidence_section"].tolist() == [
        "education", "experience", "projects", None,
    ]
