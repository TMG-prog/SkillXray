import io
import json
import shutil

import numpy as np
import pandas as pd
import pytest

from app.engine import decode_words, split_units
from app.linker import EscoLinker
from app.matching import Matcher
from app.pipeline import Pipeline, RoleNotFound

RESUME = ("Software engineer.\n• Built services in Python and SQL for reporting.\n"
          "• Strong teamwork across squads.\nEducation: State University")


def test_split_units_bullets_and_sentences():
    units = split_units(RESUME)
    assert "Built services in Python and SQL for reporting." in units
    assert len(units) >= 3


def test_split_units_filters_posting_benefit_and_fraud_boilerplate():
    posting = (
        "Build backend services with Python.\n"
        "Pay and Benefits\n"
        "Pay and benefits are fundamental to any career decision. Employment benefits include "
        "competitive compensation, health and wellness programs, paid leave and retirement.\n"
        "If you believe you are the victim of a scam, contact your local law enforcement and "
        "report the incident to the U.S. Federal Trade Commission.\n"
        "Employee Benefits: Regular employees are offered health, dental, and vision insurance, "
        "health savings accounts, and a 401(k) savings plan.\n"
        "Use Python and SQL to build reliable services."
    )

    units = split_units(posting)

    assert "Build backend services with Python." in units
    assert "Use Python and SQL to build reliable services." in units
    assert not any("local law enforcement" in unit.lower() for unit in units)
    assert not any("health savings accounts" in unit.lower() for unit in units)
    assert not any("compensation" in unit.lower() for unit in units)


def test_decode_words_merges_adjacent_skill_words():
    text = "machine learning rocks"
    words = [(0, 7, .9, True), (8, 16, .9, False), (17, 22, .0, False)]
    spans = decode_words(text, words, 0.5)
    assert [s["text"] for s in spans] == ["machine learning"]


def test_linker_recomputes_cached_embeddings_with_wrong_dimension(tmp_path):
    class Encoder:
        def encode(self, texts, **kwargs):
            return np.ones((len(texts), 2), dtype=np.float32)

        def get_sentence_embedding_dimension(self):
            return 2

    skills = pd.DataFrame({
        "conceptUri": ["s1"],
        "preferredLabel": ["Python"],
        "altLabels": [None],
    })
    embedding_path = tmp_path / "esco_term_embeddings.npy"
    np.save(embedding_path, np.ones((1, 3), dtype=np.float32))

    linker = EscoLinker(skills, Encoder(), [], {}, 0.82, 0.0, emb_path=embedding_path)

    assert linker.E.shape == (1, 2)


def test_pipeline_requires_the_configured_model_index(tmp_path):
    config_dir = tmp_path / "models" / "linker"
    config_dir.mkdir(parents=True)
    (config_dir / "linker_config.json").write_text(json.dumps({
        "link_mode": "sbert",
        "sbert_model": "BAAI/bge-large-en-v1.5",
        "link_threshold": 0.82,
        "link_margin": 0.0,
    }))

    with pytest.raises(FileNotFoundError, match="esco_term_embeddings_BAAI_bge-large-en-v1.5.npy"):
        Pipeline.load(tmp_path, encoder=object(), span_extractors={})


def test_analyze_posting_role(pipeline):
    r = pipeline.analyze(RESUME, "software")
    assert r["profile_source"] == "postings"
    covered = {c["skill"] for c in r["covered"]}
    gaps = {g["skill"] for g in r["gaps"]}
    assert "Python (computer programming)" in covered and "SQL" in covered
    assert gaps == {"Docker"}
    assert r["readiness"] == pytest.approx(70.0, abs=0.1)     # 0.4 + 0.3 of weight covered
    assert r["gaps"][0]["frequency"] == 0.5
    assert r["covered"][0]["frequency"] == 0.8
    assert {"source": "SQL", "target": "Docker", "type": "prerequisite"} in r["skill_relationships"]
    assert {"source": "Python (computer programming)", "target": "Docker", "type": "broader"} in r["skill_relationships"]
    assert {"source": "Python (computer programming)", "target": "SQL", "type": "related"} in r["skill_relationships"]
    assert {"source": "SQL", "target": "Docker", "type": "related"} not in r["skill_relationships"]
    assert "University" not in str(r["extracted_skills"])      # non-skill words rejected


def test_alias_maps_esco_title_to_profile(pipeline):
    assert pipeline.analyze(RESUME, "Software Developer")["role"] == "software"


def test_notebook_role_query_alias_maps_to_profile_without_exported_alias_file(pipeline):
    profiles = pd.concat(pipeline.matcher.profile_of.values(), ignore_index=True)
    matcher = Matcher(pipeline.matcher.encoder, profiles, pipeline.matcher.graph)

    resolved = matcher.resolve("Software Developer")

    assert resolved is not None
    assert resolved[1] == "software"


def test_esco_fallback_role(pipeline):
    r = pipeline.analyze(RESUME, "data wrangler")
    assert r["profile_source"] == "esco"
    assert {c["skill"] for c in r["covered"]} >= {"Python (computer programming)", "SQL"}
    assert any("not comparable" in w for w in r["warnings"])
    assert all(g["frequency"] is None for g in r["gaps"])


def test_unknown_role(pipeline):
    with pytest.raises(RoleNotFound):
        pipeline.analyze(RESUME, "astronaut")


def test_loads_notebook_export_layout(artifacts, pipeline, tmp_path):
    exported = tmp_path / "exported"
    files = {
        "extraction_config.json": "results/extraction_config.json",
        "skills_en.csv": "data/esco/skills_en.csv",
        "role_profiles.parquet": "data/processed/extracted/role_profiles.parquet",
        "occupations_en.csv": "data/esco/occupations_en.csv",
        "occupationSkillRelations_en.csv": "data/esco/occupationSkillRelations_en.csv",
    }
    for source_name, target_name in files.items():
        target = exported / target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifacts / source_name, target)

    loaded = Pipeline.load(
        exported,
        encoder=pipeline.matcher.encoder,
        span_extractors=pipeline.extractor.models,
    )

    assert loaded.roles()["posting_roles"] == ["software"]
    assert loaded.analyze(RESUME, "software")["readiness"] == pytest.approx(70.0, abs=0.1)


def test_pipeline_load_ignores_comment_lines_in_extra_terms(artifacts, pipeline):
    extra_file = artifacts / "data" / "esco" / "extra_terms.txt"
    extra_file.parent.mkdir(parents=True)
    extra_file.write_text("# full-line comment\n   # indented comment\ncustom term\n", encoding="utf-8")

    loaded = Pipeline.load(
        artifacts,
        encoder=pipeline.matcher.encoder,
        span_extractors=pipeline.extractor.models,
    )

    assert ("custom", "term") in loaded.extractor.gaz
    assert ("full", "line", "comment") not in loaded.extractor.gaz
    assert ("indented", "comment") not in loaded.extractor.gaz


def test_resume_with_no_skills(pipeline):
    r = pipeline.analyze("Lorem ipsum dolor sit amet consectetur adipiscing elit.", "software")
    assert r["readiness"] == 0.0 and len(r["gaps"]) == 3
    assert r["warnings"]
