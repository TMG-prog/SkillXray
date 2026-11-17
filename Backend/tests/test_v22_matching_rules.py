import pytest

from app.matching_rules import coverage_decision, has_explicit_tool_mention, is_certificate_text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Excelled at quarterly planning", False),
        ("Used Excel to prepare quarterly reports", True),
    ],
)
def test_tool_guard_requires_an_explicit_capitalized_ambiguous_tool(text, expected):
    assert has_explicit_tool_mention("Excel", text, {"excel"}, tool_guard=True) is expected


def test_exact_coverage_precedes_semantic_threshold_and_tool_guard():
    assert coverage_decision(
        exact=True,
        inherited_reason=None,
        umbrella_term=None,
        score=0.0,
        threshold=0.81,
        tool_mention_allowed=False,
    ) == ("exact ESCO skill", True)


def test_semantic_coverage_requires_threshold_and_tool_guard():
    args = {
        "exact": False,
        "inherited_reason": None,
        "umbrella_term": None,
        "threshold": 0.81,
        "tool_mention_allowed": False,
    }

    assert coverage_decision(**args, score=0.9) == ("gap", False)
    assert coverage_decision(**{**args, "tool_mention_allowed": True}, score=0.80) == ("gap", False)
    assert coverage_decision(**{**args, "tool_mention_allowed": True}, score=0.81) == ("match", True)


def test_certificate_text_detection_uses_notebook_terms():
    assert is_certificate_text("Bachelor of Science in accounting")
    assert not is_certificate_text("Built an accounting workflow")
