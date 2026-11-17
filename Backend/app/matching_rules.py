import re


_CERT_TEXT_RE = re.compile(r"\b(cert|diploma|degree|bachelor|master|education)\b")


def has_explicit_tool_mention(
    label: str,
    text: str,
    cap_required: set[str],
    tool_guard: bool,
) -> bool:
    low = label.strip().lower()
    if low not in cap_required:
        return True
    pattern = r"(?<![A-Za-z0-9])" + re.escape(low) + r"(?![A-Za-z0-9])"
    hits = [match.group() for match in re.finditer(pattern, text, re.I)]
    return any(hit[:1].isupper() for hit in hits) if tool_guard else bool(hits)


def is_certificate_text(text: str) -> bool:
    return bool(_CERT_TEXT_RE.search(str(text).lower()))


def coverage_decision(
    *,
    exact: bool,
    inherited_reason: str | None,
    umbrella_term: str | None,
    score: float,
    threshold: float,
    tool_mention_allowed: bool,
) -> tuple[str, bool]:
    if exact:
        return "exact ESCO skill", True
    if inherited_reason is not None:
        return inherited_reason, True
    if umbrella_term is not None:
        return f"umbrella term '{umbrella_term}'", True
    if score >= threshold and tool_mention_allowed:
        return "match", True
    return "gap", False
