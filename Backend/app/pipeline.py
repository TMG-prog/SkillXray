"""resume text + target role -> readiness index, covered skills, gaps (notebook run_gap_pipeline)."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import pandas as pd

from . import config as C
from .engine import DEFAULT_EXTRA_TERMS, TOOLS, Extractor, SpanExtractor, build_gazetteer
from .linker import COLLAPSED_COLS, EscoLinker, collapse_to_skills, load_overrides
from .matching import EscoRoles, Matcher, load_aliases, load_esco_graph, load_prerequisites

log = logging.getLogger("skillxray")

SPAN_COLS = ["doc_id", "skill_text", "score", "src", "unit"]


class RoleNotFound(LookupError):
    pass


class Pipeline:
    def __init__(self, extractor: Extractor, linker: EscoLinker, matcher: Matcher):
        self.extractor, self.linker, self.matcher = extractor, linker, matcher

    @classmethod
    def load(cls, artifacts: Path | None = None, encoder=None, span_extractors: dict | None = None) -> "Pipeline":
        art = Path(artifacts or C.ARTIFACTS)
        def artifact(*candidates: str, required: bool = True) -> Path:
            for candidate in candidates:
                path = art / candidate
                if path.exists():
                    return path
            if required:
                expected = ", ".join(str(art / candidate) for candidate in candidates)
                raise FileNotFoundError(f"Required pipeline artifact not found. Checked: {expected}")
            return art / candidates[0]

        t0 = time.time()
        extraction_cfg = artifact("results/extraction_config.json", "extraction_config.json", required=False)
        cfg = C.load_extraction_cfg(extraction_cfg)
        log.info("extraction config: %s", cfg)
        linker_cfg_file = artifact("models/linker/linker_config.json", "linker_config.json", required=False)
        sbert_name, thr, margin = C.load_linker_settings(linker_cfg_file)
        embedding_file = C.linker_embeddings_path(sbert_name, art / "models" / "sbert")
        if sbert_name != C.SBERT_NAME and not embedding_file.is_file():
            raise FileNotFoundError(
                f"Configured linker model {sbert_name!r} requires its precomputed ESCO index: {embedding_file}"
            )

        if encoder is None:
            import torch
            from sentence_transformers import SentenceTransformer
            torch.set_num_threads(os.cpu_count() or 2)
            encoder = SentenceTransformer(sbert_name, device="cpu")
        if span_extractors is None:
            span_extractors = {m: SpanExtractor(C.JOBBERT_REPOS[m], quantize=C.QUANTIZE, max_tokens=C.MAX_TOKENS)
                               for m in cfg["models"]}

        skills_file = artifact("data/esco/skills_en.csv", "skills_en.csv")
        extra_file = artifact("data/esco/extra_terms.txt", "extra_terms.txt", required=False)
        overrides_file = artifact("data/esco/link_overrides.csv", "link_overrides.csv", required=False)
        profiles_file = artifact(
            "data/processed/extracted/role_profiles.parquet",
            "role_profiles.parquet",
        )
        graph_relations_file = artifact(
            "data/esco/skillSkillRelations_en.csv",
            "skillSkillRelations_en.csv",
            required=False,
        )
        graph_broader_file = artifact(
            "data/esco/broaderRelationsSkillPillar_en.csv",
            "broaderRelationsSkillPillar_en.csv",
            required=False,
        )
        aliases_file = artifact("results/role_aliases.json", "role_aliases.json", required=False)
        prerequisites_file = artifact("results/skill_prerequisites.json", required=False)
        occupations_file = artifact("data/esco/occupations_en.csv", "occupations_en.csv", required=False)
        occupation_relations_file = artifact(
            "data/esco/occupationSkillRelations_en.csv",
            "occupationSkillRelations_en.csv",
            required=False,
        )

        skills = pd.read_csv(skills_file)
        if extra_file.exists():
            extra = []
            for line in extra_file.read_text(encoding="utf-8").splitlines():
                term = line.strip()
                if term and not term.startswith("#"):
                    extra.append(term)
        else:
            extra = list(DEFAULT_EXTRA_TERMS)
        gaz = build_gazetteer(skills, TOOLS, extra)
        extractor = Extractor(span_extractors, cfg, gaz)

        linker = EscoLinker(skills, encoder, extra, load_overrides(overrides_file), thr, margin,
                            emb_path=embedding_file)

        profiles = pd.read_parquet(profiles_file)
        graph = load_esco_graph(graph_relations_file, graph_broader_file)

        esco_roles = None
        if occupations_file.exists():
            esco_roles = EscoRoles(
                pd.read_csv(occupations_file),
                pd.read_csv(occupation_relations_file, dtype=str) if occupation_relations_file.exists() else None,
                skills,
            )
            if not esco_roles.enabled:
                log.warning("occupationSkillRelations_en.csv missing: roles without a posting-based profile are unsupported.")
        matcher = Matcher(encoder, profiles, graph, esco_roles, load_aliases(aliases_file),
                          load_prerequisites(prerequisites_file))
        log.info("pipeline ready in %.1fs | posting roles: %s | method: %s | ESCO fallback: %s",
                 time.time() - t0, matcher.posting_roles(), matcher.method, bool(esco_roles and esco_roles.enabled))
        return cls(extractor, linker, matcher)

    def roles(self) -> dict:
        er = self.matcher.esco_roles
        return {"posting_roles": self.matcher.posting_roles(), "esco_fallback": bool(er and er.enabled)}

    def analyze(self, text: str, role: str, role_id: str | None = None) -> dict:
        resolved = self.matcher.resolve(role, role_id)
        if resolved is None:
            raise RoleNotFound(role)
        prof, role_name, source = resolved

        t0 = time.time()
        text = text[:C.MAX_TEXT_CHARS]
        spans = self.extractor.extract(text)
        t1 = time.time()
        if spans:
            df = pd.DataFrame(spans).assign(doc_id="live")[SPAN_COLS]
            cand = collapse_to_skills(self.linker.standardise(df))
        else:
            cand = pd.DataFrame(columns=COLLAPSED_COLS)
        t2 = time.time()
        res = self.matcher.analyse(cand, prof)
        t3 = time.time()

        warnings = []
        if len(cand) < 5:
            warnings.append("Very few skills were found in this resume. If it is a scanned or image-heavy PDF, "
                            "try a text-based PDF or DOCX.")
        if source == "esco":
            warnings.append("This role has no posting-based profile; requirements come from ESCO's occupation "
                            "definition, so the readiness score is not comparable with the other roles.")
        return {
            "role": role_name, "profile_source": source, "method": self.matcher.method, **res,
            "extracted_skills": [{"skill": r.esco_label, "uri": r.esco_uri, "in_esco": bool(r.in_esco),
                                  "mentions": int(r.mentions)} for r in cand.itertuples()],
            "warnings": warnings,
            "timings_ms": {"extract": int((t1 - t0) * 1000), "link": int((t2 - t1) * 1000),
                           "match": int((t3 - t2) * 1000)},
        }
