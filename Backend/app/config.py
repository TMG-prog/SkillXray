"""Settings. Values marked 'notebook' are copied from the Colab notebook and must stay in sync with it,
because the accuracy you measured there only holds if the same settings are used here."""
import json
import logging
import os
from pathlib import Path

log = logging.getLogger("skillxray")

ARTIFACTS = Path(os.getenv("ARTIFACTS_DIR", Path(__file__).resolve().parent.parent))

# ---- notebook section 2 / 3
JOBBERT_REPOS = {"skill": "jjzha/jobbert_skill_extraction", "knowledge": "jjzha/jobbert_knowledge_extraction"}
QUANTIZE = os.getenv("QUANTIZE", "0" if os.name == "nt" else "1") == "1"
MAX_UNIT_WORDS = 70
MAX_TOKENS = 160
MAX_SKILL_WORDS = 8
DEFAULT_CFG = {"models": ("knowledge",), "tau": {"knowledge": 0.3, "skill": 0.7}, "min_score": 0.0,
               "pos_filter": False, "max_words": MAX_SKILL_WORDS, "gazetteer": True}

# ---- notebook section 9b
SBERT_NAME = "all-MiniLM-L6-v2"
LINK_THRESHOLD_FALLBACK, LINK_MARGIN_FALLBACK = 0.70, 0.03
KEEP_CURATED_NON_ESCO = True
NON_SKILL_PATTERN = (r"\b(university|college|institute|school|academy|inc|llc|ltd|corp|corporation|company|"
                     r"certificate|diploma|bachelor|master|associate degree)\b")

# ---- notebook section 13a
SBERT_MATCH = 0.75
GAP_CUTOFF = 0.50
ESCO_GRAPH_CREDIT = {"related": 0.45, "sibling": 0.30}

# ---- not from the notebook: fallback profiles for roles that have no posting-based profile
ESCO_OPTIONAL_WEIGHT = float(os.getenv("ESCO_OPTIONAL_WEIGHT", "0.5"))   # essential skills weigh 1.0
MAX_ROLE_SKILLS = 40                                                      # same cap as notebook section 10

# ---- API limits
MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "5"))
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "40000"))
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "6"))


def load_extraction_cfg(path: Path | None = None) -> dict:
    """The configuration selected by notebook section 7 (results/extraction_config.json)."""
    path = path or ARTIFACTS / "extraction_config.json"
    if path.exists():
        cfg = json.loads(path.read_text())["config"]
        cfg["models"] = tuple(cfg["models"])
        return cfg
    log.warning("extraction_config.json not found in %s - using DEFAULT_CFG. Copy results/extraction_config.json "
                "from Drive so the API matches the configuration you evaluated.", path.parent)
    return dict(DEFAULT_CFG)


def load_linker_settings(path: Path | None = None) -> tuple[str, float, float]:
    path = path or ARTIFACTS / "linker_config.json"
    if path.exists():
        d = json.loads(path.read_text())
        mode = d.get("link_mode", "sbert")
        if mode != "sbert":
            raise ValueError(f"Unsupported linker mode in {path}: {mode!r}")
        return (str(d.get("sbert_model", SBERT_NAME)),
                float(d["link_threshold"]), float(d["link_margin"]))
    log.warning("linker_config.json not found - using fallback SBERT model and link threshold/margin (%.2f/%.2f).",
                LINK_THRESHOLD_FALLBACK, LINK_MARGIN_FALLBACK)
    return SBERT_NAME, LINK_THRESHOLD_FALLBACK, LINK_MARGIN_FALLBACK


def load_linker_cfg(path: Path | None = None) -> tuple[float, float]:
    _, threshold, margin = load_linker_settings(path)
    return threshold, margin


def linker_embeddings_path(model_name: str, directory: Path) -> Path:
    filename = ("esco_term_embeddings.npy" if model_name == SBERT_NAME
                else f"esco_term_embeddings_{model_name.replace('/', '_')}.npy")
    return directory / filename
