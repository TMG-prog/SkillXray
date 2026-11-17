import json
import re
import zlib

import numpy as np
import pandas as pd
import pytest


class FakeEncoder:
    """Hashed bag-of-words embeddings: similar wording -> high cosine. Stands in for SBERT in tests."""
    def encode(self, texts, batch_size=32, normalize_embeddings=False, convert_to_numpy=True, show_progress_bar=False):
        out = np.zeros((len(texts), 64), np.float32)
        for i, t in enumerate(texts):
            for tok in re.findall(r"[a-z0-9+#]+", str(t).lower()):
                out[i, zlib.crc32(tok.encode()) % 64] += 1
        if normalize_embeddings:
            out /= np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)
        return out


class FakeSpanExtractor:
    """Marks a fixed vocabulary as skills, like a perfectly tuned JobBERT would."""
    VOCAB = {"python", "sql", "docker", "teamwork", "budgets"}

    def predict_words(self, texts, batch_size=32):
        res = []
        for t in texts:
            words = []
            for m in re.finditer(r"\S+", t):
                w = m.group().strip(".,;:")
                s = m.start()
                e = s + len(w)
                words.append((s, e, 0.95 if w.lower() in self.VOCAB else 0.01, True))
            res.append(words)
        return res


@pytest.fixture()
def artifacts(tmp_path):
    skills = pd.DataFrame({
        "conceptUri": [f"s{i}" for i in range(1, 9)],
        "preferredLabel": ["Python (computer programming)", "SQL", "Docker", "teamwork principles",
                           "manage budgets", "use spreadsheets", "write reports", "operate forklifts"],
        "altLabels": ["python\npython programming", "structured query language", "docker containers", "teamwork",
                      "budgets", "", "", ""],
    })
    skills.to_csv(tmp_path / "skills_en.csv", index=False)
    pd.DataFrame({"role": ["software"] * 3, "esco_uri": ["s1", "s2", "s3"],
                  "esco_label": ["Python (computer programming)", "SQL", "Docker"], "in_esco": True,
                  "n_docs": [8, 6, 5], "freq": [0.8, 0.6, 0.5], "weight": [0.4, 0.3, 0.3],
                  "n_postings": 10}).to_parquet(tmp_path / "role_profiles.parquet", index=False)
    pd.DataFrame({"conceptUri": ["o1"], "preferredLabel": ["data wrangler"]}).to_csv(
        tmp_path / "occupations_en.csv", index=False)
    pd.DataFrame({"occupationUri": ["o1"] * 3, "relationType": ["essential", "essential", "optional"],
                  "skillUri": ["s1", "s2", "s5"]}).to_csv(tmp_path / "occupationSkillRelations_en.csv", index=False)
    pd.DataFrame({"originalSkillUri": ["s1"], "relatedSkillUri": ["s2"]}).to_csv(
        tmp_path / "skillSkillRelations_en.csv", index=False)
    pd.DataFrame({"conceptUri": ["s3"], "broaderUri": ["s1"]}).to_csv(
        tmp_path / "broaderRelationsSkillPillar_en.csv", index=False)
    (tmp_path / "role_aliases.json").write_text(json.dumps({"software developer": "software"}))
    results = tmp_path / "results"
    results.mkdir()
    (results / "skill_prerequisites.json").write_text(json.dumps({"s3": ["s2"]}))
    (tmp_path / "extraction_config.json").write_text(json.dumps({"config": {
        "models": ["knowledge"], "tau": {"knowledge": 0.3, "skill": 0.7}, "min_score": 0.0,
        "pos_filter": False, "max_words": 8, "gazetteer": True}}))
    return tmp_path


@pytest.fixture()
def pipeline(artifacts):
    from app.pipeline import Pipeline
    return Pipeline.load(artifacts, encoder=FakeEncoder(), span_extractors={"knowledge": FakeSpanExtractor()})
