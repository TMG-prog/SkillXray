import json

import pytest

from app.config import (
    ARTIFACTS,
    SBERT_NAME,
    linker_embeddings_path,
    load_extraction_cfg,
    load_linker_settings,
)


def test_linker_settings_load_model_and_thresholds(tmp_path):
    config = tmp_path / "linker_config.json"
    config.write_text(json.dumps({
        "link_mode": "sbert",
        "sbert_model": "BAAI/bge-large-en-v1.5",
        "link_threshold": 0.82,
        "link_margin": 0.0,
    }))

    assert load_linker_settings(config) == ("BAAI/bge-large-en-v1.5", 0.82, 0.0)


def test_linker_settings_reject_unsupported_mode(tmp_path):
    config = tmp_path / "linker_config.json"
    config.write_text(json.dumps({
        "link_mode": "tfidf",
        "link_threshold": 0.82,
        "link_margin": 0.0,
    }))

    with pytest.raises(ValueError, match="Unsupported linker mode"):
        load_linker_settings(config)


def test_embedding_path_is_model_specific(tmp_path):
    assert linker_embeddings_path("BAAI/bge-large-en-v1.5", tmp_path) == (
        tmp_path / "esco_term_embeddings_BAAI_bge-large-en-v1.5.npy"
    )
    assert linker_embeddings_path(SBERT_NAME, tmp_path) == tmp_path / "esco_term_embeddings.npy"


def test_extraction_config_matches_v22_runtime_settings():
    config = load_extraction_cfg(ARTIFACTS / "results" / "extraction_config.json")

    assert config["models"] == ("knowledge",)
    assert config["tau"]["knowledge"] == 0.5
    assert config["max_words"] == 6
    assert config["ner_filter"] is True
    assert config["tool_guard"] is True
