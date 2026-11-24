"""Section detection and evidence weighting for plain-text resumes."""
from __future__ import annotations

import re

import pandas as pd

_HEADINGS = {
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "work history",
        "career history",
        "relevant experience",
        "volunteer experience",
    ),
    "projects": (
        "projects",
        "project experience",
        "selected projects",
        "personal projects",
        "academic projects",
        "portfolio",
    ),
    "education": (
        "education",
        "educational background",
        "academic background",
        "academic qualifications",
        "education and qualifications",
        "qualifications",
        "relevant coursework",
    ),
    "skills": (
        "skills",
        "technical skills",
        "skills summary",
        "core competencies",
        "areas of expertise",
    ),
    "certifications": (
        "certifications",
        "certifications and licenses",
        "professional certifications",
        "licenses",
    ),
    "other": (
        "summary",
        "professional summary",
        "profile",
        "objective",
        "awards",
        "awards and honors",
        "publications",
        "languages",
        "additional information",
        "interests",
        "references",
    ),
}
_HEADING_LOOKUP = {
    re.sub(r"[^a-z0-9]+", " ", heading.casefold()).strip(): section
    for section, headings in _HEADINGS.items()
    for heading in headings
}
_SECTION_PRIORITY = {
    "education": 1,
    "skills": 2,
    "certifications": 2,
    "other": 2,
    "experience": 3,
    "projects": 3,
}
_INHERITED_REASON = re.compile(r"inherited from '([^']+)'")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _normalize_heading(text: str) -> str:
    text = re.sub(r"^\s*(?:[•●▪◦*-]\s*|\d+[.)]\s*)+", "", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _heading(line: str) -> tuple[str, str] | None:
    cleaned = re.sub(r"^\s*(?:[•●▪◦*-]\s*|\d+[.)]\s*)+", "", line).strip()
    normalized = _normalize_heading(cleaned)
    if normalized in _HEADING_LOOKUP:
        return _HEADING_LOOKUP[normalized], ""

    for delimiter in (":", "|", "—", "–", "-"):
        heading, separator, remainder = cleaned.partition(delimiter)
        if separator:
            category = _HEADING_LOOKUP.get(_normalize_heading(heading))
            if category:
                return category, remainder.strip()
    return None


def parse_resume_sections(text: str) -> list[tuple[str, str]]:
    """Split text at recognized headings; return [] when no known heading is found."""
    sections: list[tuple[str, str]] = []
    current_category = "other"
    lines: list[str] = []
    found_heading = False

    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        parsed_heading = _heading(line)
        if parsed_heading is None:
            lines.append(line)
            continue
        if lines:
            content = "\n".join(lines).strip()
            if content:
                sections.append((current_category, content))
        current_category, remainder = parsed_heading
        lines = [remainder] if remainder else []
        found_heading = True

    if lines:
        content = "\n".join(lines).strip()
        if content:
            sections.append((current_category, content))
    return sections if found_heading else []


def section_for_text(text: str, sections: list[tuple[str, str]]) -> str | None:
    """Return the strongest detected section containing this evidence snippet."""
    needle = _normalize_text(text)
    if not needle:
        return None
    pattern = re.compile(
        r"(?<![a-z0-9])" + re.escape(needle).replace(r"\ ", r"\s+") + r"(?![a-z0-9])",
        re.IGNORECASE,
    )
    matching = [
        category
        for category, content in sections
        if pattern.search(_normalize_text(content))
    ]
    return max(matching, key=lambda section: _SECTION_PRIORITY.get(section, 0), default=None)


def apply_section_credit(
    table: pd.DataFrame,
    candidates: pd.DataFrame,
    spans: pd.DataFrame | None,
    sections: list[tuple[str, str]],
    *,
    education_credit: float = 0.5,
) -> pd.DataFrame:
    """Apply partial readiness credit when the only supporting evidence is in Education."""
    if not 0 <= education_credit <= 1:
        raise ValueError("education_credit must be between 0 and 1.")

    result = table.copy()
    credits: list[float] = []
    evidence_sections: list[str | None] = []

    for row in result.itertuples(index=False):
        if not bool(row.covered):
            credits.append(0.0)
            evidence_sections.append(None)
            continue

        matched_sections: list[str] = []
        if spans is not None and not spans.empty and "resume_section" in spans.columns:
            candidate_uris = {str(row.esco_uri)}
            inherited_match = _INHERITED_REASON.search(str(getattr(row, "reason", "")))
            if inherited_match and not candidates.empty:
                inherited_uris = candidates.loc[
                    candidates["esco_label"].astype(str) == inherited_match.group(1),
                    "esco_uri",
                ]
                candidate_uris.update(inherited_uris.astype(str))
            evidence_rows = spans.loc[
                spans["status"].eq("accepted")
                & spans["esco_uri"].astype(str).isin(candidate_uris)
            ]
            matched_sections.extend(
                evidence_rows["resume_section"].dropna().astype(str).tolist()
            )

        evidence_section = section_for_text(str(getattr(row, "cv_evidence", "")), sections)
        if evidence_section:
            matched_sections.append(evidence_section)
        strongest_section = max(
            matched_sections,
            key=lambda section: _SECTION_PRIORITY.get(section, 0),
            default=None,
        )
        credits.append(education_credit if strongest_section == "education" else 1.0)
        evidence_sections.append(strongest_section)

    result["credit"] = credits
    result["covered"] = result["credit"] >= 1.0
    result["evidence_section"] = pd.Series(evidence_sections, index=result.index, dtype="object")
    return result
