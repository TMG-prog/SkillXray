from app.evidence import contextualize_evidence


def test_contextualize_evidence_expands_skill_to_source_sentence():
    resume = "Built Python services for data analysis and automated reporting."

    assert contextualize_evidence(resume, "Python") == resume


def test_contextualize_evidence_adds_neighboring_context_for_bare_skill_list():
    resume = "Skills: Python, SQL, and Docker\nLed migration of reporting services."

    result = contextualize_evidence(resume, "Python")

    assert "Python" in result
    assert "Skills:" in result
    assert len(result) > len("Python")


def test_contextualize_evidence_preserves_existing_sentence_context():
    resume = "Designed secure APIs. Mentored engineers and reviewed code."
    evidence = "Mentored engineers and reviewed code."

    assert contextualize_evidence(resume, evidence) == evidence


def test_contextualize_evidence_keeps_unmatched_evidence_unchanged():
    assert contextualize_evidence("Built APIs with Python.", "SQL") == "SQL"


def test_contextualize_evidence_bounds_long_sentences_and_keeps_phrase():
    resume = f"{'Designed scalable software systems ' * 20}using Python for production services."

    result = contextualize_evidence(resume, "Python", max_chars=120)

    assert len(result) <= 120
    assert "Python" in result
