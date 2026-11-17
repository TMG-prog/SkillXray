"""Helpers for presenting resume evidence with its source context."""
from __future__ import annotations

import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|[\r\n]+")


def contextualize_evidence(text: str, evidence: str, *, max_chars: int = 300) -> str:
    """Expand a matched resume phrase to its sentence, retaining source wording."""
    phrase = evidence.strip()
    if not phrase or not text:
        return evidence

    match = re.search(re.escape(phrase), text, re.IGNORECASE)
    if match is None:
        return evidence

    start, end = match.span()
    boundaries = [0]
    boundaries.extend(
        boundary.end()
        for boundary in _SENTENCE_BOUNDARY.finditer(text)
    )
    boundaries.append(len(text))
    sentence_start = max(boundary for boundary in boundaries if boundary <= start)
    sentence_end = min(boundary for boundary in boundaries if boundary >= end)
    snippet_start, snippet_end = sentence_start, sentence_end

    # A bare skill-list item is not useful evidence; include nearby CV text.
    if (
        len(phrase) < 32
        and sentence_end - sentence_start < min(max_chars, len(phrase) + 32)
    ):
        snippet_start = max(0, sentence_start - max_chars // 2)
        snippet_end = min(len(text), sentence_end + max_chars // 2)

    snippet = text[snippet_start:snippet_end].strip(" \t\r\n•▪◦‣*-")
    if len(snippet) <= max_chars:
        return snippet

    phrase_start = match.start() - snippet_start
    left = max(0, phrase_start - (max_chars - len(phrase)) // 2)
    left = min(left, len(snippet) - max_chars)
    return snippet[left:left + max_chars].strip()
