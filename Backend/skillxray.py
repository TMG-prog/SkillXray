# ==============================================================================
# 0. Paths and imports (new)
# ==============================================================================
"""SkillXray scoring pipeline, extracted from 01_extraction_with_esco_v17 (cells noted in each section).

Import this module once (it loads the JobBERT extractor(s), SBERT and the ESCO data), then call:

    from skillxray import score_cv, available_roles, read_resume_file
    res = score_cv(read_resume_file("cv.pdf"), "it support")

Everything is read from SKILLXRAY_DIR (default: the folder this file is in). See README.md for the layout.
Nothing here calls a job API: profiles come from the frozen release shipped in data/processed/live_profiles/.

Revision notes (parity with the notebook's final matcher):
  * inherited_cover only inherits from confidently linked skills (exact, or similarity >= INHERIT_MIN_SIM)
  * match_v2 is phrase-aware (posting wording is compared with the CV spans, notebook 14f)
  * the NER filter is switched on and the "vs code" MAP override is registered, both in memory only
  * run_v2's docstring is now a real docstring
"""
import os, re, json, time, glob, warnings
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from tqdm.auto import tqdm

warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
torch.set_num_threads(os.cpu_count() or 2)

BASE_DIR      = os.environ.get("SKILLXRAY_DIR", os.path.dirname(os.path.abspath(__file__)))
ESCO_DIR      = os.path.join(BASE_DIR, 'data/esco')
PROCESSED_DIR = os.path.join(BASE_DIR, 'data/processed')
EXTRACT_DIR   = os.path.join(PROCESSED_DIR, 'extracted')
LIVE_DIR      = os.path.join(PROCESSED_DIR, 'live_profiles')
RESULTS_DIR   = os.path.join(BASE_DIR, 'results')
SBERT_DIR     = os.path.join(BASE_DIR, 'models/sbert')

def display(x):          # the notebook helper, so any leftover display() call is harmless
    print(x)

# ==============================================================================
# 1. Extraction settings (notebook cells 6 and 28)
# ==============================================================================
JOBBERT_REPOS = {'skill': 'jjzha/jobbert_skill_extraction', 'knowledge': 'jjzha/jobbert_knowledge_extraction'}
QUANTIZE       = os.getenv("QUANTIZE", "1") != "0"  # int8 dynamic quantisation, CPU only.
MAX_UNIT_WORDS = 70      # long run-on text (resumes) is cut into chunks of at most this many words
MAX_TOKENS     = 160     # model input limit per chunk
MAX_SKILL_WORDS = 8      # spans longer than this are duties, not skills

# Starting configuration, replaced by the best one found on the development part of your gold set (section 7a).
# tau[model] = a word counts as part of a skill when P(not 'outside') >= tau. Lower tau = more recall.
DEFAULT_CFG = {'models': ('knowledge',), 'tau': {'knowledge': 0.3, 'skill': 0.7}, 'min_score': 0.0,
               'pos_filter': False, 'max_words': MAX_SKILL_WORDS, 'gazetteer': True,
               'rule_filter': False, 'ner_filter': False, 'tool_guard': False}     # v17 components, switched on only when section 7a shows they help
EXTRACTION_CFG = dict(DEFAULT_CFG)
_cfg_file = os.path.join(RESULTS_DIR, 'extraction_config.json')      # cell 28: the configuration selected in section 7
if os.path.exists(_cfg_file):
    EXTRACTION_CFG = json.load(open(_cfg_file))['config']
    EXTRACTION_CFG['models'] = tuple(EXTRACTION_CFG['models'])
else:
    print('[!] results/extraction_config.json not found: using DEFAULT_CFG (scores will differ from the notebook)')

# ==============================================================================
# 2. spaCy sentence splitter (cell 8)
# ==============================================================================
import spacy

SENT_NLP = spacy.blank("en")                    # fast rule-based sentence splitter, no model needed
SENT_NLP.add_pipe("sentencizer")

_NLP_POS = None
def get_nlp_pos():
    """spaCy tagger + lemmatiser, loaded only when the POS filter is actually used."""
    global _NLP_POS
    if _NLP_POS is None:
        _NLP_POS = spacy.load("en_core_web_sm", disable=["parser", "ner"])
    return _NLP_POS

_NLP_NER = None
def get_nlp_ner():
    """spaCy named-entity recogniser (v17, used by cfg['ner_filter'] to drop names of people, places, organisations and dates)."""
    global _NLP_NER
    if _NLP_NER is None:
        _NLP_NER = spacy.load("en_core_web_sm", disable=["tagger", "parser", "attribute_ruler", "lemmatizer"])
    return _NLP_NER
print("spaCy ready")

# ==============================================================================
# 3. JobBERT span extractors (cell 9)
# ==============================================================================
from collections import Counter
from transformers import AutoTokenizer, AutoModelForTokenClassification

# ------------------------------------------------------------------ device / precision
# v17: the model now runs on the GPU when there is one (fp16), and only falls back to int8 CPU quantisation when there is not.
# (v16 quantised for CPU and never moved the model to CUDA, even when Colab reported CUDA: True.)
DEVICE        = 'cuda' if torch.cuda.is_available() else 'cpu'
USE_FP16      = (DEVICE == 'cuda')
STRIDE_TOKENS = 32          # a text longer than MAX_TOKENS is scored in overlapping windows instead of being cut off

def resolve_bio_ids(id2label):
    """Return (B_id, I_id, O_id). Handles 'B'/'I'/'O' and 'B-XYZ'/'I-XYZ'; falls back to 0/1/2."""
    m = {}
    for k, v in id2label.items():
        tag = str(v).upper().split('-')[0]
        if tag in ('B', 'I', 'O'):
            m[tag] = int(k)
    if set(m) != {'B', 'I', 'O'}:
        m = {'B': 0, 'I': 1, 'O': 2}
    return m['B'], m['I'], m['O']

def decode_words(text, words, tau):
    """words: [(start, end, p_skill, is_begin), ...] in text order -> spans.
    A word belongs to a span when p_skill >= tau; a new span starts at a 'begin' word or after a gap."""
    spans, cur = [], None
    for s, e, ps, is_b in words:
        if ps >= tau:
            if cur is None or is_b:
                if cur is not None:
                    spans.append(cur)
                cur = {'start': s, 'end': e, 'ps': [ps]}
            else:
                cur['end'] = e; cur['ps'].append(ps)
        elif cur is not None:
            spans.append(cur); cur = None
    if cur is not None:
        spans.append(cur)
    return [{'start': c['start'], 'end': c['end'], 'score': float(np.mean(c['ps'])),
             'text': text[c['start']:c['end']].strip()} for c in spans]

def snap_spans(text, spans):
    """Expand each span to whole whitespace-delimited words ("s license" -> "driver's license", "co" -> "co-workers")."""
    out = []
    for sp in spans:
        s, e = sp['start'], sp['end']
        while s > 0 and not text[s - 1].isspace():
            s -= 1
        while e < len(text) and not text[e].isspace():
            e += 1
        out.append({**sp, 'start': s, 'end': e, 'text': text[s:e].strip()})
    return out

class SpanExtractor:
    def __init__(self, repo, quantize=True, max_tokens=160, stride=STRIDE_TOKENS, device=None, fp16=None):
        self.repo, self.max_tokens, self.stride = repo, max_tokens, stride
        self.device = device or DEVICE
        self.fp16 = (self.device == 'cuda') if fp16 is None else (fp16 and self.device == 'cuda')
        self.tok = AutoTokenizer.from_pretrained(repo)
        model = AutoModelForTokenClassification.from_pretrained(repo).eval()
        self.b_id, self.i_id, self.o_id = resolve_bio_ids(model.config.id2label)
        if self.device == 'cpu' and quantize:
            try:
                from torch.ao.quantization import quantize_dynamic
                model = quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
            except Exception as e:
                print("  quantisation skipped:", e)
        else:
            model = model.to(self.device)
            if self.fp16:
                model = model.half()
        self.model = model
        self.stats = {'texts': 0, 'windowed_texts': 0, 'windows': 0}

    # -------------------------------------------------------------- one forward pass over a list of windows
    def _forward(self, enc, lo, hi):
        feed = {k: torch.from_numpy(np.ascontiguousarray(v[lo:hi])).to(self.device) for k, v in enc.items()
                if k in ('input_ids', 'attention_mask', 'token_type_ids')}
        with torch.inference_mode():
            logits = self.model(**feed).logits.float()            # softmax in fp32 even when the model runs in fp16
            return torch.softmax(logits, dim=-1).cpu().numpy()

    def predict_word_scores(self, texts, batch_size=32):
        """texts -> aligned list of word lists [(start, end, pB, pI, pO)].
        The label of a word is the label of its first sub-token. A text longer than max_tokens is split into windows that
        overlap by `stride` tokens; every word takes its probabilities from the window in which it sits furthest from an edge,
        so no word is dropped (v16 silently truncated everything after max_tokens)."""
        out = [None] * len(texts)
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))      # similar lengths -> less padding
        for b in range(0, len(order), batch_size):
            idx = order[b:b + batch_size]
            batch = [texts[i] for i in idx]
            enc = self.tok(batch, truncation=True, max_length=self.max_tokens, stride=self.stride,
                           return_overflowing_tokens=True, padding=True, return_tensors='np', return_offsets_mapping=True)
            owner = [int(x) for x in enc['overflow_to_sample_mapping']]          # window -> position in `batch`
            n_win = len(owner)
            probs = np.concatenate([self._forward(enc, lo, min(lo + batch_size, n_win))
                                    for lo in range(0, n_win, batch_size)], axis=0)
            offs = np.asarray(enc['offset_mapping'])
            self.stats['texts'] += len(batch); self.stats['windows'] += n_win
            self.stats['windowed_texts'] += sum(1 for c in Counter(owner).values() if c > 1)

            cand = [dict() for _ in batch]     # per text: word_id -> list of (is_first_subtoken, edge_distance, s, e, pB, pI, pO)
            for k in range(n_win):
                real = [(t, w) for t, w in enumerate(enc.word_ids(k)) if w is not None and offs[k][t][1] > offs[k][t][0]]
                if not real:
                    continue
                t_first, t_last = real[0][0], real[-1][0]
                seen = {}
                for t, w in real:
                    s, e = int(offs[k][t][0]), int(offs[k][t][1])
                    if w not in seen:
                        seen[w] = [s, e, t]
                    else:
                        seen[w][1] = max(seen[w][1], e)
                for w, (s, e, t) in seen.items():
                    p = probs[k][t]
                    cand[owner[k]].setdefault(w, []).append((s, e, min(t - t_first, t_last - t), float(p[self.b_id]), float(p[self.i_id]), float(p[self.o_id])))

            for j, i in enumerate(idx):
                res = []
                for w in sorted(cand[j]):
                    opts = cand[j][w]
                    true_start = min(o[0] for o in opts)                  # the window that holds the word's real first sub-token wins ...
                    best = max(opts, key=lambda o: (o[0] == true_start, o[2]))   # ... then the one furthest from a window edge
                    s = true_start; e = max(o[1] for o in opts)
                    res.append((s, e, best[3], best[4], best[5]))
                out[i] = res
        return out

    def predict_words(self, texts, batch_size=32):
        """texts -> aligned list of word lists [(start, end, p_skill, is_begin)],
        with p_skill = 1 - P(outside) and is_begin = P(B) >= P(I)."""
        return [[(s, e, 1.0 - po, pb >= pi) for s, e, pb, pi, po in words]
                for words in self.predict_word_scores(texts, batch_size)]

EXTRACTORS = {}
for _name, _repo in JOBBERT_REPOS.items():
    if _name not in EXTRACTION_CFG['models']:        # only load what the selected configuration uses (saves memory)
        continue
    try:
        EXTRACTORS[_name] = SpanExtractor(_repo, quantize=QUANTIZE, max_tokens=MAX_TOKENS)
        print(f"loaded {_name:9s} <- {_repo} | device={EXTRACTORS[_name].device}"
              f"{' fp16' if EXTRACTORS[_name].fp16 else (' int8' if QUANTIZE and DEVICE == 'cpu' else ' fp32')}")
    except Exception as e:
        print(f"[!] could not load '{_name}' model ({_repo}): {e}")
assert EXTRACTORS, "no JobBERT model could be loaded"

# ==============================================================================
# 4. Extraction engine (cell 16)
# ==============================================================================
import re
import os
import json
import time
import hashlib
import numpy as np
import pandas as pd
from tqdm.auto import tqdm
from app.matching_rules import coverage_decision, has_explicit_tool_mention, is_certificate_text
from app.resume_sections import apply_section_credit, parse_resume_sections, section_for_text

# ================================================================
# 1. CONFIGURATION
# ================================================================
# These must already exist: JOBBERT_REPOS, EXTRACTORS, SENT_NLP, MAX_UNIT_WORDS, MAX_TOKENS, PROCESSED_DIR, ESCO_DIR,
# get_nlp_pos(), get_nlp_ner(), decode_words(), snap_spans().

ENGINE_VERSION = 'v8'    # part of every cache key. Bump it whenever the cleaning, splitting, decoding or filtering code below changes,
                         # otherwise spans cached with the old code are silently reused (v16 keyed the cache on the config only).
CHUNK_OVERLAP = 2

FILLER_WORDS = {
    "ensure", "ensures", "ensuring", "ensured",
    "complete", "completes", "completing", "completed",
    "maintain", "maintains", "maintaining", "maintained",
    "review", "reviews", "reviewing", "reviewed",
    "follow", "follows", "following", "followed",
    "require", "requires", "requiring", "required",
    "include", "includes", "including", "included",
    "assist", "assists", "assisting", "assisted",
    "perform", "performs", "performing", "performed",
    "conduct", "conducts", "conducting", "conducted",
    "provide", "provides", "providing", "provided",
    "achieve", "achieves", "achieving", "achieved",
    "meet", "meets", "meeting", "met",
    "handle", "handles", "handling", "handled",
}

SOFT_SKILL_VERB_LEMMAS = {
    "lead", "manage", "mentor", "coordinate", "organize",
    "spearhead", "direct", "supervise", "initiate", "negotiate",
    "facilitate", "chair", "delegate", "motivate", "orchestrate",
    "collaborate", "communicate", "present", "train", "coach",
    "influence", "develop", "plan", "solve", "adapt", "analyze",
    "research", "design", "implement", "create", "inspire",
    "evaluate", "assess", "demonstrate", "contribute", "build",
    "drive", "innovate", "streamline", "optimize",
}

# Remove function words only at span boundaries.
_EDGE = r"(?:for|in|with|to|of|on|at|by|the|a|an|and|or|as|from)"

_SALARY_NUM = re.compile(r"\$\s?\d")
_SALARY_WORD = re.compile(r"\b(min|max|mid|salary|pay|per\s+(year|hour)|range)\b", re.I)
_EEO = re.compile(
    r"equal\s+(employment\s+)?opportunit|affirmative\s+action|protected\s+(veteran|class)"
    r"|sexual\s+orientation|gender\s+identity|national\s+origin|genetic\s+information"
    r"|\brace\b.{0,60}\b(religion|color|colour|sex|gender|pregnancy)\b"
    r"|\b(religion|color|colour)\b.{0,60}\bpregnancy\b", re.I | re.S)
_POSTING_BOILERPLATE = re.compile(
    r"\b(?:pay\s+and\s+benefits|employee\s+benefits|employment\s+benefits|"
    r"(?:company|mastercard)\s+benefits|benefits?\s+(?:(?:generally\s+)?include|including)|"
    r"compensation\s+packages?|employee\s+assistance\s+program|legal\s+plan|"
    r"medical\s*,\s*dental\s*,?\s*(?:and\s+)?vision\s+insurance|"
    r"health\s+savings\s+accounts?|401\s*\(?k\)?|paid\s+(?:time\s+off|parental\s+leave)|"
    r"retirement\s+plan|life\s+and\s+accident\s+insurance|"
    r"victim\s+of\s+(?:a\s+)?scam|contact\s+(?:your\s+)?local\s+law\s+enforcement|"
    r"report\s+(?:the\s+)?incident\s+to\s+(?:the\s+)?(?:u\.s\.\s*)?"
    r"(?:federal\s+trade\s+commission|ftc))\b", re.I | re.S)

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9+#.]+")
GAZ = globals().get('GAZ', {})       # v17: re-running this cell no longer wipes a dictionary built in section 6b


# ================================================================
# 2. SPAN CLEANING AND NOISE FILTERING
# ================================================================

def clean_skill_span(text):
    """Clean punctuation and dangling function words at span edges.
    Keeps the original case ('IT', 'Go', 'React' must survive) and keeps brackets:
    the span splitter in clean_document_text has already turned brackets into separators."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", str(text)).strip()
    for _ in range(3):
        text = re.sub(r"^[,;:\-\u2013\u2014/&*]+\s*", "", text)
        text = re.sub(r"\s*[,;:\-\u2013\u2014/&.*]+$", "", text)
        text = re.sub(r"^" + _EDGE + r"\s+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+" + _EDGE + r"$", "", text, flags=re.IGNORECASE)
    return text.strip()


def clean_document_text(text):
    """Document-level clean-up before splitting into units.
    Brackets are turned into commas, NOT deleted: in postings the tools live inside them,
    e.g. 'containerisation (Docker)' or 'frameworks (React, Vue, Angular)'."""
    if not isinstance(text, str):
        return ""

    # 'Job Description:' style header labels only (not the word anywhere in a sentence)
    text = re.sub(r"(?i)\b(job\s+)?description\s*:", " ", text)

    # 'Where you'll be working ...' boilerplate, up to the end of that line or sentence only
    text = re.sub(r"(?i)\bwhere\s+you'?ll\s+be\s+wor[^\n.]*[.\n]?", " ", text)

    # audit-style tags such as skill(s), (Proof)
    text = re.sub(r"\(\s*(?:s|es|proof)\s*\)", "", text, flags=re.I)

    # keep bracket contents as separate items
    text = re.sub(r"\s*[()]\s*", ", ", text)

    # collapse repeated separators left behind, then whitespace
    text = re.sub(r"(?:\s*,){2,}", ",", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def is_noise_unit(text):
    """Filter compensation, benefits, fraud-warning and equal-opportunity boilerplate."""
    if _SALARY_NUM.search(text) and _SALARY_WORD.search(text):
        return True
    return bool(_EEO.search(text) or _POSTING_BOILERPLATE.search(text))


def is_noise_span(text):
    """Reject obvious non-skill noise, not ordinary short skills."""
    text = str(text).strip()
    if not text or "$" in text:
        return True
    letters = sum(ch.isalpha() for ch in text)
    if letters < 2:
        return True
    if letters < 0.5 * len(text):          # punctuation-heavy strings
        return True
    return False


def normalize_skill(text):
    """Normalize a phrase into tokens for safe comparison."""
    return tuple(token.lower().strip(".") for token in TOKEN_PATTERN.findall(str(text)))


def contains_token_sequence(container, phrase):
    """True when phrase occurs as a complete token sequence."""
    if not phrase or len(phrase) > len(container):
        return False
    return any(container[i:i + len(phrase)] == phrase
               for i in range(len(container) - len(phrase) + 1))


# ---- v17: rule-based removal of dates, contact details and "school + year" fragments (cfg['rule_filter'])
_MONTH = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_YEAR = r"(?:19|20)\d{2}"
_DATE_PATTERNS = [
    re.compile(rf"\b{_MONTH}\.?,?\s+{_YEAR}\b", re.I),                              # "May 2015"
    re.compile(rf"\b{_YEAR}\s*(?:-|\u2013|\u2014|to)\s*(?:{_YEAR}|present|current|now)\b", re.I),   # "2013 - 2015", "2013 to Present"
    re.compile(r"\b\d{1,2}\s*/\s*(?:\d{1,2}\s*/\s*)?\d{2,4}\b"),                    # "09/2013", "9/1/13"
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),                                          # e-mail
    re.compile(r"\b(?:https?://|www\.)\S+", re.I),                                   # URL
    re.compile(r"\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b"),                              # phone number
]
_ORG_EDU_WORDS = re.compile(r"\b(university|college|institute|school|academy|inc|llc|ltd|corp|corporation|company)\b", re.I)
_YEAR_RE = re.compile(rf"\b{_YEAR}\b")

def is_non_skill_rule(text):
    """Dates, e-mail addresses, URLs, phone numbers, and 'University of X 2013' style fragments are never skills.
    A tool plus a version ('Windows 2000', 'SQL Server 2012') is kept: a bare year alone does not trigger this."""
    t = str(text)
    if any(p.search(t) for p in _DATE_PATTERNS):
        return True
    return bool(_YEAR_RE.search(t) and _ORG_EDU_WORDS.search(t))


# ---- v17: protection list + NER filter (cfg['ner_filter'])
def _gaz_key(text):
    """The normalisation gazetteer_spans uses for a phrase: lower-case tokens without edge dots."""
    return tuple(re.sub(r"^\.+|\.+$", "", t.lower()) or t.lower() for t in TOKEN_PATTERN.findall(str(text)))

def _load_protected_from_overrides():
    """Spans the user curated as real skills (KEEP / MAP rows in link_overrides.csv) must never be removed by a statistical filter."""
    path = os.path.join(ESCO_DIR, 'link_overrides.csv')
    keys = set()
    if os.path.exists(path):
        try:
            ov = pd.read_csv(path, dtype=str).fillna('')
            ov.columns = [c.strip().lower() for c in ov.columns]
            for sp, act in zip(ov['span'], ov['action']):
                if act.strip().upper() in ('KEEP', 'MAP') and sp.strip():
                    keys.add(_gaz_key(sp))
        except Exception as e:
            print("  could not read link_overrides.csv for the protection list:", e)
    return keys

PROTECTED_EXTRA = globals().get('PROTECTED_EXTRA') or _load_protected_from_overrides()

def is_protected_term(text):
    """A dictionary phrase (ESCO label, tool, curated term) or a curated KEEP/MAP override: never removed by the NER filter.
    This is what stops the tagger from deleting 'Java' (a place), 'Excel' (a company) or 'Jenkins' (a surname)."""
    k = _gaz_key(text)
    return bool(k) and (k in GAZ or k in PROTECTED_EXTRA)

NER_REJECT_LABELS = {'PERSON', 'GPE', 'LOC', 'FAC', 'ORG', 'NORP', 'DATE', 'TIME', 'MONEY', 'PERCENT', 'QUANTITY', 'ORDINAL'}

def ner_rejects(span_text, start, end, ner_doc, min_cover=0.6):
    """True when a named entity covers most of the span and the span is not a protected dictionary term."""
    if ner_doc is None or end <= start or is_protected_term(span_text):
        return False
    for ent in ner_doc.ents:
        if ent.label_ not in NER_REJECT_LABELS:
            continue
        overlap = min(end, ent.end_char) - max(start, ent.start_char)
        if overlap > 0 and overlap >= min_cover * (end - start):
            return True
    return False


# ================================================================
# 3. OPTIONAL POS FILTER (kept for old configs; keep_span never rejects, so it is not in the tuning grid any more)
# ================================================================

def keep_span(tokens):
    """Conservative POS filter. Currently accepts every span (see the note above)."""
    return True


# ================================================================
# 4. SPLIT DOCUMENTS INTO UNITS
# ================================================================

def split_units(text, max_words=None, overlap=CHUNK_OVERLAP):
    """
    Split into bullets/sentences and then overlapping word chunks.
    Pre-cleans document headers and metadata to prevent boundary pollution.
    """
    max_words = max_words or MAX_UNIT_WORDS

    if not isinstance(text, str):
        return []

    # Pre-clean document-level artifacts and headers
    text = clean_document_text(text)

    parts = re.split(
        r"[\r\n]+|[\u2022\u25AA\u2023\u25CF\u25E6\u00B7]",
        text
    )

    parts = [p.strip() for p in parts if len(p.strip()) >= 3]
    units = []
    seen = set()

    for doc in SENT_NLP.pipe(parts, batch_size=256):
        for sent in doc.sents:
            sentence = sent.text.strip()

            if (
                len(sentence) < 3
                or not re.search(r"[A-Za-z]", sentence)
                or is_noise_unit(sentence)
            ):
                continue

            words = sentence.split()

            if len(words) <= max_words:
                chunks = [sentence]
            else:
                step = max(1, max_words - overlap)
                chunks = []

                for start in range(0, len(words), step):
                    chunk = " ".join(words[start:start + max_words])

                    if len(chunk) >= 3:
                        chunks.append(chunk)

                    if start + max_words >= len(words):
                        break

            for chunk in chunks:
                key = chunk.casefold()

                if key not in seen:
                    seen.add(key)
                    units.append(chunk)

    return units


# ================================================================
# 5. CACHE RAW MODEL PREDICTIONS
# ================================================================

# Each model caches raw per-word predictions by exact unit text.
_RAW = {name: {} for name in JOBBERT_REPOS}


def predict_cached(name, texts, batch_size=None, show=False):
    """
    Cache predictions to avoid repeating inference during tuning.

    Invalidate this cache if model weights, tokenization, or
    prediction preprocessing changes.
    """
    if name not in EXTRACTORS:
        raise KeyError(f"Model {name!r} is not loaded.")
    if batch_size is None:
        batch_size = 128 if EXTRACTORS[name].device == 'cuda' else 32      # a GPU wants bigger batches than a 2-core CPU

    cache = _RAW.setdefault(name, {})

    todo = sorted(
        (t for t in dict.fromkeys(texts) if t not in cache),
        key=len
    )

    for start in tqdm(
        range(0, len(todo), 512),
        desc=f"JobBERT-{name}",
        disable=not (show and len(todo) >= 512)
    ):
        chunk = todo[start:start + 512]

        predictions = EXTRACTORS[name].predict_words(
            chunk,
            batch_size=batch_size
        )

        for text, result in zip(chunk, predictions):
            cache[text] = result


def truncation_report(texts, name=None, sample=2000):
    """How many units would not fit in MAX_TOKENS (these are now scored in overlapping windows; v16 dropped their tail)?"""
    name = name or next(iter(EXTRACTORS))
    tok = EXTRACTORS[name].tok
    units = list(dict.fromkeys(u for t in texts for u in split_units(t)))[:sample]
    if not units:
        return {'units': 0, 'over_limit': 0, 'share': 0.0, 'p95_tokens': 0}
    lens = np.array([len(x) for x in tok(units, add_special_tokens=True)['input_ids']])
    limit = EXTRACTORS[name].max_tokens
    return {'units': len(units), 'over_limit': int((lens > limit).sum()), 'share': float((lens > limit).mean()),
            'p95_tokens': int(np.percentile(lens, 95))}


# ================================================================
# 6. GAZETTEER MATCHING
# ================================================================

# v17 tool guard (cfg['tool_guard']): dictionary words that are also ordinary English. 'Excel in a fast-paced environment' is
# not Excel, 'go to market' is not Go. Such a word counts as a tool only when it is capitalised in the text, and, for the
# verb-like ones, when it is not followed by a preposition or article.
CAP_REQUIRED = {'excel', 'express', 'shell', 'spark', 'swift', 'go', 'hive', 'word', 'access', 'teams', 'outlook', 'office', 'sage'}
VERB_HOMOGRAPHS = {'excel', 'express', 'spark', 'swift', 'access', 'go'}
NEXT_BLOCK = {'in', 'at', 'by', 'with', 'on', 'under', 'as', 'to', 'for', 'of', 'from', 'into', 'through', 'our', 'your', 'their',
              'the', 'a', 'an'}


def gazetteer_spans(text, max_len=6, guard=False):
    """Longest-first dictionary matching on complete token sequences."""
    toks = [
        (m.group(), m.start(), m.end())
        for m in TOKEN_PATTERN.finditer(text)
    ]

    normalized = [
        re.sub(r"^\.+|\.+$", "", token.lower()) or token.lower()
        for token, _, _ in toks
    ]

    out = []
    i = 0

    while i < len(toks):
        hit = None

        for length in range(
            min(max_len, len(toks) - i),
            0,
            -1
        ):
            candidate = tuple(normalized[i:i + length])

            if candidate in GAZ:
                hit = length
                break

        if hit and guard and hit == 1 and normalized[i] in CAP_REQUIRED:
            nxt = normalized[i + 1] if i + 1 < len(toks) else None
            if not toks[i][0][:1].isupper() or (normalized[i] in VERB_HOMOGRAPHS and nxt in NEXT_BLOCK):
                hit = None

        if hit:
            start = toks[i][1]
            end = toks[i + hit - 1][2]

            out.append(text[start:end].strip(" ."))
            i += hit
        else:
            i += 1

    return out


def add_gazetteer(unit, spans, guard=False):
    """
    Add dictionary matches without confusing partial words
    such as Java and JavaScript.
    """
    if not GAZ:
        return spans

    out = list(spans)

    for phrase in gazetteer_spans(unit, guard=guard):
        phrase_norm = normalize_skill(phrase)

        if not phrase_norm:
            continue

        existing_norms = [
            normalize_skill(item["skill_text"])
            for item in out
        ]

        # Do not add a dictionary match already covered by a span.
        if any(
            contains_token_sequence(existing, phrase_norm)
            for existing in existing_norms
        ):
            continue

        # Remove shorter spans only if they are complete token
        # subsequences of the dictionary phrase.
        kept = []

        for item, existing in zip(out, existing_norms):
            if (
                existing
                and contains_token_sequence(phrase_norm, existing)
            ):
                continue

            kept.append(item)

        out = kept

        out.append({
            "skill_text": phrase,
            "score": 1.0,
            "src": "dict"
        })

    return out


# ================================================================
# 7. COMBINE MODEL PREDICTIONS
# ================================================================

def combine_models(per_model):
    """Combine spans, preferring the higher-scoring overlapping span."""
    all_spans = [
        {**span, "src": model_name}
        for model_name, spans in per_model.items()
        for span in spans
    ]

    if len(per_model) <= 1:
        return sorted(all_spans, key=lambda span: span["start"])

    all_spans.sort(key=lambda span: -span["score"])
    kept = []

    for span in all_spans:
        overlaps = any(
            not (
                span["end"] <= existing["start"]
                or span["start"] >= existing["end"]
            )
            for existing in kept
        )

        if not overlaps:
            kept.append(span)

    return sorted(kept, key=lambda span: span["start"])


# ================================================================
# 8. POSTPROCESS SPANS
# ================================================================

def postprocess_spans(spans, cfg, pos_doc=None, ner_doc=None):
    """
    Apply score, rule, NER and POS filters against ORIGINAL span boundaries.
    Clean the text only after filtering.
    """
    out = []
    seen = set()

    for span in spans:
        if span["score"] < cfg.get("min_score", 0.0):
            continue

        if cfg.get("rule_filter") and is_non_skill_rule(span["text"]):
            continue

        if cfg.get("ner_filter") and ner_rejects(span["text"], span["start"], span["end"], ner_doc):
            continue

        # POS filtering must use offsets from the original unit.
        if cfg.get("pos_filter") and pos_doc is not None:
            char_span = pos_doc.char_span(
                span["start"],
                span["end"],
                alignment_mode="expand"
            )

            if char_span is not None:
                if not keep_span(list(char_span)):
                    continue

        text = clean_skill_span(span["text"])

        if (
            len(text) < 2
            or not re.search(r"[A-Za-z]", text)
            or is_noise_span(text)
        ):
            continue

        max_words = cfg.get("max_words")

        if max_words and len(text.split()) > max_words:
            continue

        key = text.casefold()

        if key in seen:
            continue

        seen.add(key)

        out.append({
            "skill_text": text,
            "score": float(span["score"]),
            "src": span.get("src", "")
        })

    return out


# ================================================================
# 9. EXTRACT SPANS FROM ONE UNIT
# ================================================================

def unit_spans(unit, cfg, pos_doc=None, ner_doc=None):
    """Extract candidate skills from a single unit."""
    per_model = {}

    for model_name in cfg["models"]:
        words = _RAW.get(model_name, {}).get(unit)

        if words is None:
            continue

        per_model[model_name] = snap_spans(
            unit,
            decode_words(
                unit,
                words,
                cfg["tau"][model_name]
            )
        )

    combined = combine_models(per_model)

    processed = postprocess_spans(
        combined,
        cfg,
        pos_doc=pos_doc,
        ner_doc=ner_doc
    )

    if cfg.get("gazetteer"):
        processed = add_gazetteer(unit, processed, guard=cfg.get("tool_guard", False))

    return processed


def _active_models(cfg):
    return [
        model_name
        for model_name in cfg["models"]
        if model_name in EXTRACTORS
    ]


# ================================================================
# 10. EXTRACT SKILLS FROM DOCUMENTS
# ================================================================

def extract_docs(texts, ids, cfg, batch_size=None, show=False):
    """
    Return DataFrame:
    doc_id, skill_text, score, src, unit
    """
    units_per_doc = [split_units(text) for text in texts]

    unique_units = list(dict.fromkeys(
        unit
        for units in units_per_doc
        for unit in units
    ))

    for model_name in _active_models(cfg):
        predict_cached(
            model_name,
            unique_units,
            batch_size=batch_size,
            show=show
        )

    if cfg.get("pos_filter"):
        pos_docs = dict(zip(unique_units, get_nlp_pos().pipe(unique_units, batch_size=256)))
    else:
        pos_docs = {}

    if cfg.get("ner_filter"):
        ner_docs = dict(zip(unique_units, get_nlp_ner().pipe(unique_units, batch_size=256)))
    else:
        ner_docs = {}

    rows = []

    for doc_id, units in zip(ids, units_per_doc):
        for unit in units:
            predictions = unit_spans(
                unit,
                cfg,
                pos_doc=pos_docs.get(unit),
                ner_doc=ner_docs.get(unit)
            )

            for prediction in predictions:
                rows.append({
                    "doc_id": str(doc_id),
                    **prediction,
                    "unit": unit[:300]
                })

    return pd.DataFrame(rows, columns=DocSpanStore.COLS)


# ================================================================
# 11. CONFIGURATION SIGNATURE
# ================================================================

def gaz_fingerprint():
    """Identifies the dictionary content, so changing extra_terms.txt or the ESCO file changes the cache key."""
    if not GAZ:
        return 'nogaz'
    h = hashlib.md5()
    for k in sorted(GAZ):
        h.update((" ".join(k) + "\n").encode())
    return h.hexdigest()[:8]


def cfg_signature(cfg):
    """Cache key = configuration + everything else that changes what a document produces:
    engine version, dictionary content (when the dictionary is on), the model repositories and the windowing settings."""
    clean = json.loads(json.dumps(cfg, default=list, sort_keys=True))
    clean['_engine'] = ENGINE_VERSION
    clean['_gaz'] = gaz_fingerprint() if cfg.get('gazetteer') else None
    clean['_models'] = {m: EXTRACTORS[m].repo for m in cfg.get('models', ()) if m in EXTRACTORS}
    clean['_window'] = [MAX_TOKENS, globals().get('STRIDE_TOKENS'), MAX_UNIT_WORDS, CHUNK_OVERLAP]
    return hashlib.md5(json.dumps(clean, sort_keys=True).encode()).hexdigest()[:8]


# ================================================================
# 12. DOCUMENT SPAN CACHE  (append-only parquet shards)
# ================================================================

class DocSpanStore:
    """Persistent per-document extraction cache.
    v16 rewrote one growing CSV after every 50 documents (so a 10,000-document run rewrote ~200 files of increasing size to Drive)
    and a crash during the write could corrupt it. v17 appends one small parquet shard per chunk, written atomically, with the
    finished document ids stored next to it. A shard whose id list is missing (crash in between) is ignored and redone."""

    COLS = [
        "doc_id",
        "skill_text",
        "score",
        "src",
        "unit"
    ]

    def __init__(self, kind, cfg):
        self.kind = kind
        self.cfg = dict(cfg)
        self.sig = cfg_signature(cfg)
        self.dir = os.path.join(PROCESSED_DIR, f"spans_{ENGINE_VERSION}_{kind}_{self.sig}")
        os.makedirs(self.dir, exist_ok=True)
        self.df, self.done = self._load()
        print(f"[{kind}] cache {os.path.basename(self.dir)}: {len(self.done)} docs, {len(self.df):,} spans")

    def _load(self):
        frames, done = [], set()
        for f in sorted(os.listdir(self.dir)):
            if not f.endswith(".parquet"):
                continue
            ids_path = os.path.join(self.dir, f[:-len(".parquet")] + ".done.json")
            if not os.path.exists(ids_path):          # half-written shard: drop it, its documents are processed again
                os.remove(os.path.join(self.dir, f))
                continue
            frames.append(pd.read_parquet(os.path.join(self.dir, f)))
            with open(ids_path, "r", encoding="utf-8") as file:
                done.update(json.load(file))
        frames = [fr for fr in frames if len(fr)]
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=self.COLS)
        return df, done

    def _next_shard(self):
        idx = [int(f[5:10]) for f in os.listdir(self.dir) if f.startswith("part_") and f.endswith(".parquet")]
        return f"part_{(max(idx) + 1 if idx else 0):05d}"

    def _write_shard(self, result, chunk_ids):
        name = self._next_shard()
        result = result.astype({"doc_id": str, "skill_text": str, "src": str, "unit": str, "score": float})
        tmp_pq, tmp_js = os.path.join(self.dir, name + ".tmp.parquet"), os.path.join(self.dir, name + ".tmp.json")
        result.to_parquet(tmp_pq, index=False)
        with open(tmp_js, "w", encoding="utf-8") as file:
            json.dump(sorted(chunk_ids), file)
        os.replace(tmp_pq, os.path.join(self.dir, name + ".parquet"))       # parquet first ...
        os.replace(tmp_js, os.path.join(self.dir, name + ".done.json"))     # ... the id list last: it is what marks the shard as complete

    def ensure(self, ids, text_of, chunk_docs=None):
        if chunk_docs is None:
            chunk_docs = 200 if any(e.device == 'cuda' for e in EXTRACTORS.values()) else 50
        ids = [str(value) for value in ids]

        todo = [
            doc_id
            for doc_id in dict.fromkeys(ids)
            if doc_id not in self.done
        ]

        if not todo:
            print(f"[{self.kind}] all documents already cached")
            return

        start_time = time.time()

        for start in tqdm(
            range(0, len(todo), chunk_docs),
            desc=f"extract {self.kind}"
        ):
            chunk = todo[start:start + chunk_docs]

            result = extract_docs(
                [text_of(doc_id) for doc_id in chunk],
                chunk,
                self.cfg
            )

            self._write_shard(result, chunk)

            if len(result):
                self.df = pd.concat([self.df, result], ignore_index=True)
            self.done.update(chunk)

        elapsed = (time.time() - start_time) / 60

        print(
            f"[{self.kind}] extracted {len(todo)} documents "
            f"in {elapsed:.1f} minutes"
        )

    def get(self, ids):
        wanted = {str(value) for value in ids}

        return self.df[
            self.df["doc_id"].isin(wanted)
        ].copy()


print("SkillXray extraction engine v17 ready (engine version", ENGINE_VERSION + ").")

# ==============================================================================
# 5a. ESCO skills table (cell 14, only the ESCO part)
# ==============================================================================
esco_skills = pd.read_csv(os.path.join(ESCO_DIR, 'skills_en.csv'))

# ==============================================================================
# 5b. Dictionary matcher (cell 18)
# ==============================================================================
# ==============================================================================
# Enhanced Dictionary Matcher & Domain Vocabulary (Fixes False Negatives/Positives)
# ==============================================================================

TOOLS = [
    "Python", "SQL", "Java", "JavaScript", "TypeScript", "React", "Node.js",
    "Express", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git", "GitHub",
    "Excel", "Tableau", "Power BI", "PyTorch", "TensorFlow", "Pandas", "NumPy",
    "PostgreSQL", "MySQL", "MongoDB", "Hadoop", "Spark", "Kafka", "Hive",
    "Salesforce", "QuickBooks", "SAP", "Jira", "Shell", "Bash", "Linux",
    "Photoshop", "PowerPoint", "Outlook", "C++", "C#"
]
TOOLS_AMBIGUOUS = {
    "R", "C", "Go", "Excel", "Express", "Shell", "Spark", "Hive", "Swift", "Outlook", "Word",
    "Access", "Teams", "Office", "Sage", "Puppet", "Chef", "SaltStack", "Vault", "Consul", "Nomad",
    "Rhino", "Sketch", "Zoom", "Flux", "Storm", "Pig", "Chroma", "Canvas", "Linear", "Outreach",
    "Gong", ".NET",
}
CAP_REQUIRED |= {tool.lower() for tool in TOOLS_AMBIGUOUS if tool != ".NET"} | {"net"}
VERB_HOMOGRAPHS |= {"access", "flux", "storm", "sketch", "zoom", "outreach", "linear"}

# Expanded GENERIC blocklist to filter out common false-positive nouns/verbs
GENERIC = {
    ("plan",), ("report",), ("work",), ("team",), ("support",), ("service",),
    ("services",), ("business",), ("manage",), ("develop",), ("create",),
    ("design",), ("time",), ("review",), ("test",), ("use",), ("schedule",),
    ("terms",), ("training",), ("infrastructure",), ("assess",), ("climb",)
}

# Default domain terms the models tend to miss (from false-negative analysis). Merged into extra_terms.txt.
DEFAULT_EXTRA_TERMS = [
    "attention to detail", "regulatory compliance", "strategic finance", "service excellence",
    "lesson plans", "multidisciplinary interventions", "professional development",
    "marketing budget", "marketing plan", "high-speed internet", "software program management",
    "business development", "account management", "contract management", "document management",
    "capacity analysis", "sales meetings", "marketing personnel", "cellular reception", "accuracy",
    "routing", "configuration", "cost estimation", "distribution expansion", "bootstrapping", "CRM",
]

# (the notebook appended missing default terms to extra_terms.txt; here they are merged in memory, the file is never written)
_extra = os.path.join(ESCO_DIR, 'extra_terms.txt')
_file_terms = [l.strip() for l in open(_extra, encoding='utf-8') if l.strip() and not l.startswith('#')] if os.path.exists(_extra) else []
EXTRA_TERMS = list(dict.fromkeys(_file_terms + [t for t in DEFAULT_EXTRA_TERMS if t.lower() not in {x.lower() for x in _file_terms}]))

def _norm_tuple(s):
    return tuple(re.findall(r"[a-z0-9+#.]+", s.lower()))

def build_gazetteer(esco_df, tools, extra=()):
    terms = []
    if esco_df is not None and 'preferredLabel' in esco_df.columns:
        for pref, alt in esco_df[['preferredLabel', 'altLabels']].itertuples(index=False):
            terms.append(str(pref))
            if isinstance(alt, str):
                terms += [a.strip() for a in alt.split('\n') if a.strip()]

    protected = set(tools) | set(extra)
    idx = {}
    for t in terms + list(tools) + list(extra):
        k = _norm_tuple(str(t))
        if not k or len(k) > 4 or k in GENERIC:
            continue
        if len(k) == 1 and len(k[0]) < 4 and str(t) not in protected:
            continue
        idx[k] = str(t)
    return idx

GAZ = build_gazetteer(esco_skills if 'esco_skills' in globals() else None, TOOLS, EXTRA_TERMS)
print(f"Dictionary ready: {len(GAZ):,} phrases loaded ({len(EXTRA_TERMS)} domain terms from extra_terms.txt)")

# ==============================================================================
# 6. SBERT, ESCO linker, standardisation (cell 33)
# ==============================================================================
from sentence_transformers import SentenceTransformer
from app.config import SBERT_NAME as DEFAULT_SBERT_NAME, linker_embeddings_path, load_linker_settings

# ------------------------------------------------------------------ settings
os.makedirs(SBERT_DIR, exist_ok=True)
LINKER_CFG_PATH = os.path.join(BASE_DIR, 'models/linker/linker_config.json')
SBERT_NAME, LINK_THRESHOLD, LINK_MARGIN = load_linker_settings(Path(LINKER_CFG_PATH))
ESCO_EMB_PATH = str(linker_embeddings_path(SBERT_NAME, Path(SBERT_DIR)))
LINK_OVERRIDES_PATH = os.path.join(ESCO_DIR, 'link_overrides.csv')
NON_SKILL_PATTERN = r"\b(university|college|institute|school|academy|inc|llc|ltd|corp|corporation|company|certificate|diploma|bachelor|master|associate degree)\b"
LINK_THRESHOLD_FALLBACK, LINK_MARGIN_FALLBACK = 0.70, 0.03     # used only until the linker has been tuned
LINK_THRESHOLD_OVERRIDE = None                                  # set a number to force a value
LINK_MARGIN_OVERRIDE = None
KEEP_CURATED_NON_ESCO = True

HUB_K = 10                      # neighbourhood size for the hubness correction (v17)
LEX_STOP_WORDS = {'of', 'and', 'the', 'for', 'in', 'to', 'with', 'a', 'an', 'on', 'at', 'by', 'use', 'using', 'perform', 'manage', 'apply',
                  'carry', 'out', 'ensure', 'conduct', 'provide', 'develop', 'create', 'work', 'skill', 'knowledge', 'experience', 'ability',
                  'basic', 'principle', 'technique'}
HUB_BETA, LEX_GUARD, GUARD_HI = 0.0, False, 0.85      # v17 linker options: OFF until the tuning cell below shows they help on annotations
if os.path.exists(LINKER_CFG_PATH):
    _cfg = json.load(open(LINKER_CFG_PATH))
    LINK_TUNED = bool(_cfg.get('tuned_on_annotations', False))
    HUB_BETA, LEX_GUARD, GUARD_HI = float(_cfg.get('hub_beta', 0.0)), bool(_cfg.get('lexical_guard', False)), float(_cfg.get('guard_hi', 0.85))
else:
    LINK_TUNED = False
if LINK_THRESHOLD_OVERRIDE is not None:
    LINK_THRESHOLD, LINK_TUNED = float(LINK_THRESHOLD_OVERRIDE), False
if LINK_MARGIN_OVERRIDE is not None:
    LINK_MARGIN, LINK_TUNED = float(LINK_MARGIN_OVERRIDE), False
print(f"link rule: similarity >= {LINK_THRESHOLD:.2f} and margin >= {LINK_MARGIN:.2f}, or exact ESCO label"
      f" | hub correction beta={HUB_BETA} | lexical guard={'on (below ' + str(GUARD_HI) + ')' if LEX_GUARD else 'off'}. "
      + ("Tuned on your annotations." if LINK_TUNED else "WARNING: not tuned on annotations - run the linker tuning cell (9a-2) that follows this one."))

# ------------------------------------------------------------------ ESCO labels
_alts = esco_skills['altLabels'] if 'altLabels' in esco_skills.columns else pd.Series([None] * len(esco_skills))
_terms = []
for uri, pref, alt in zip(esco_skills['conceptUri'], esco_skills['preferredLabel'], _alts):
    if not isinstance(pref, str):
        continue
    _terms.append((pref, uri, pref))
    if isinstance(alt, str):
        _terms += [(a.strip(), uri, pref) for a in alt.split('\n') if a.strip()]
esco_terms_df = (pd.DataFrame(_terms, columns=['term', 'conceptUri', 'preferredLabel'])
                   .drop_duplicates(subset=['term']).reset_index(drop=True))

def _norm_key(s):
    """Lookup key: lower case, punctuation removed, light plural stripping ("lesson plans" == "lesson plan")."""
    words = re.sub(r"[^a-z0-9+#]+", " ", str(s).lower()).split()
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words)

EXACT = {}
for _i, _t in enumerate(esco_terms_df['term'].values):
    EXACT.setdefault(_norm_key(_t), _i)
URI_OF_LABEL = dict(zip(esco_skills['preferredLabel'], esco_skills['conceptUri']))
CURATED = {_norm_key(t): t for t in list(TOOLS) + list(EXTRA_TERMS)}          # canonical names of curated tools / terms
print(f"ESCO: {len(esco_skills):,} skills, {len(esco_terms_df):,} labels | curated tools/terms: {len(CURATED)}")

# ------------------------------------------------------------------ SBERT + embeddings (cached on Drive)
if SBERT_NAME != DEFAULT_SBERT_NAME and not os.path.isfile(ESCO_EMB_PATH):
    raise FileNotFoundError(
        f"Configured linker model {SBERT_NAME!r} requires its precomputed ESCO index: {ESCO_EMB_PATH}"
    )
_DEV = 'cuda' if torch.cuda.is_available() else 'cpu'
sbert_model = SentenceTransformer(SBERT_NAME, device=_DEV)
expected_embedding_shape = (len(esco_terms_df), sbert_model.get_sentence_embedding_dimension())
cached_embeddings = np.load(ESCO_EMB_PATH, mmap_mode='r') if os.path.exists(ESCO_EMB_PATH) else None
if SBERT_NAME != DEFAULT_SBERT_NAME and cached_embeddings.shape != expected_embedding_shape:
    raise ValueError(
        f"ESCO index {ESCO_EMB_PATH} has shape {cached_embeddings.shape}; expected {expected_embedding_shape} "
        f"for linker model {SBERT_NAME!r}"
    )
if cached_embeddings is not None and cached_embeddings.shape == expected_embedding_shape:
    _E = np.asarray(cached_embeddings, dtype=np.float32); print("loaded cached ESCO embeddings", _E.shape)
else:
    if cached_embeddings is not None:
        print(f"cached ESCO embeddings have shape {cached_embeddings.shape}; expected {expected_embedding_shape}, recomputing")
    _E = sbert_model.encode(esco_terms_df['term'].tolist(), batch_size=128, show_progress_bar=True, convert_to_numpy=True).astype(np.float32)
    try:
        np.save(ESCO_EMB_PATH, _E)
    except OSError as _e:
        print('could not cache the ESCO embeddings:', _e)
    print('computed ESCO embeddings', _E.shape)
ESCO_EMB = _E / np.maximum(np.linalg.norm(_E, axis=1, keepdims=True), 1e-9)
_ESCO_T = None
_TOPK_CACHE = {}          # text -> (scores, indices) for the K_RETRIEVE nearest labels; valid while the encoder and embeddings are unchanged
K_RETRIEVE = 10

def esco_topk(texts, k=K_RETRIEVE, chunk=1024):
    """The k nearest ESCO labels (cosine) for each text -> (scores, indices) of shape (n, k). Results are cached per text,
    so the linker tuning below can score hundreds of configurations without encoding anything again."""
    global _ESCO_T
    texts = [str(t) for t in texts]
    k = min(k, K_RETRIEVE)
    uniq = [t for t in dict.fromkeys(texts)]
    new = [t for t in uniq if t not in _TOPK_CACHE]
    if new:
        q = sbert_model.encode(new, batch_size=128, normalize_embeddings=True, convert_to_numpy=True,
                               show_progress_bar=len(new) > 2000).astype(np.float32)
        if _ESCO_T is None:
            _ESCO_T = torch.from_numpy(ESCO_EMB).to(_DEV)
        for i in range(0, len(q), chunk):
            s, j = (torch.from_numpy(q[i:i + chunk]).to(_DEV) @ _ESCO_T.T).topk(K_RETRIEVE, dim=1)
            for t, sr, jr in zip(new[i:i + chunk], s.cpu().numpy(), j.cpu().numpy()):
                _TOPK_CACHE[t] = (sr, jr)
    sc = np.stack([_TOPK_CACHE[t][0][:k] for t in texts]) if texts else np.zeros((0, k), np.float32)
    ix = np.stack([_TOPK_CACHE[t][1][:k] for t in texts]) if texts else np.zeros((0, k), np.int64)
    return sc, ix

# ------------------------------------------------------------------ hubness correction (v17)
# Some ESCO labels ('think creatively', 'demining operations', 'computer engineering') are the nearest neighbour of a great many
# unrelated phrases: "hubs" of the embedding space. HUB_R[j] = how close label j is, on average, to its K nearest corpus spans.
# A skill whose labels are close to everything gets its score lowered:  score' = cos - beta * (HUB_R[j] - mean(HUB_R)).
HUB_PATH = os.path.join(SBERT_DIR, f'esco_hubness_k{HUB_K}.npy')
HUB_R = None
if os.path.exists(HUB_PATH):
    _h = np.load(HUB_PATH)
    if _h.shape[0] == len(esco_terms_df):
        HUB_R = _h.astype(np.float32)
HUB_R_MEAN = float(HUB_R.mean()) if HUB_R is not None else 0.0
if HUB_BETA > 0 and HUB_R is None:
    print("[!] hub_beta > 0 in the linker config but", HUB_PATH, "is missing or stale: hub correction disabled. Re-run the linker tuning cell.")
    HUB_BETA = 0.0

def compute_hubness(span_texts, k=HUB_K, chunk=4096):
    """Mean cosine of every ESCO label to its k nearest spans from the corpus. Saved on Drive next to the label embeddings."""
    global HUB_R, HUB_R_MEAN, _ESCO_T
    q = sbert_model.encode(list(span_texts), batch_size=256, normalize_embeddings=True, convert_to_numpy=True,
                           show_progress_bar=True).astype(np.float32)
    Q = torch.from_numpy(q).to(_DEV)
    if _ESCO_T is None:
        _ESCO_T = torch.from_numpy(ESCO_EMB).to(_DEV)
    kk = min(k, Q.shape[0])
    r = np.zeros(ESCO_EMB.shape[0], np.float32)
    for i in range(0, ESCO_EMB.shape[0], chunk):
        r[i:i + chunk] = (_ESCO_T[i:i + chunk] @ Q.T).topk(kk, dim=1).values.mean(1).cpu().numpy()
    # hubness belongs to the SKILL, not to one of its wordings: average over all labels of a concept, so that the
    # alternative labels of a hub skill ('be creative' for 'think creatively') are demoted together with it
    r = pd.Series(r).groupby(esco_terms_df['conceptUri'].to_numpy()).transform('mean').to_numpy(np.float32)
    np.save(HUB_PATH, r)
    HUB_R, HUB_R_MEAN = r, float(r.mean())
    return r

# ------------------------------------------------------------------ lexical guard (v17)
def _stem(w):
    for suf in ('ments', 'ment', 'ing', 'ers', 'er', 'ions', 'ion', 'ed', 'ly', 'al', 'es', 's'):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)]
    return w

def _content_stems(s):
    return {_stem(w) for w in _norm_key(s).split() if w not in LEX_STOP_WORDS and len(w) > 2}

def lexically_related(span, matched_term, preferred_label):
    """Do the span and the ESCO label share a content word? ('team leadership' ~ 'lead a team' yes; 'clearance' ~ 'demining operations' no.)"""
    return bool(_content_stems(span) & (_content_stems(matched_term) | _content_stems(preferred_label)))

LINK_CFG = {'threshold': LINK_THRESHOLD, 'margin': LINK_MARGIN, 'hub_beta': HUB_BETA, 'lexical_guard': LEX_GUARD, 'guard_hi': GUARD_HI}

# ------------------------------------------------------------------ rejection rules
STOP_WORDS = {"a", "an", "and", "or", "the", "of", "in", "on", "at", "to", "for", "with", "by", "from", "as", "is", "are", "was",
              "be", "been", "this", "that", "these", "those", "it", "its", "their", "our", "your", "we", "you", "they", "he",
              "she", "i", "not", "no", "yes", "making", "using", "used", "use", "work", "working", "worked", "etc",
              "including", "such", "also", "well", "new", "good", "strong"}
ALLOW_SHORT = {"c", "r", "go", "ai", "ml", "ui", "ux", "qa", "hr", "it", "bi", "c#", "c++", ".net", "sql", "aws", "gcp", "css", "php"}
NON_SKILL_RE = re.compile(NON_SKILL_PATTERN, re.I)

def is_junk(span):
    low = span.lower().strip()
    if not re.search(r"[A-Za-z]", span):
        return True
    if low in STOP_WORDS and span.strip() != "IT":        # "IT" (information technology) vs the pronoun "it"
        return True
    if len(low) < 3 and low not in ALLOW_SHORT:
        return True
    if low in ALLOW_SHORT:                                 # c++, c#, .net ... have few letters but are real skills
        return "$" in span
    letters = sum(ch.isalpha() for ch in span)
    return "$" in span or letters < 0.5 * len(span)

REQUIRED_DROPS = ['TS/SCI', 'TS/SCI w']   # a US security clearance, not a skill
def load_overrides():
    ov = pd.read_csv(LINK_OVERRIDES_PATH, dtype=str).fillna('')
    ov.columns = [c.strip().lower() for c in ov.columns]
    out = {_norm_key(r.span): (r.action.strip().upper(), r.esco_label.strip()) for r in ov.itertuples() if r.span.strip()}
    for s in REQUIRED_DROPS:
        out.setdefault(_norm_key(s), ('DROP', ''))
    return out
LINK_OVERRIDES = load_overrides() if os.path.exists(LINK_OVERRIDES_PATH) else {_norm_key(s): ('DROP', '') for s in REQUIRED_DROPS}
print(f"{len(LINK_OVERRIDES)} curated link overrides")

def standardise_spans(df, link_cfg=None):
    """df needs a 'skill_text' column. Adds: status, reason, esco_uri, esco_label, similarity, margin, exact, in_esco.
    link_cfg (default LINK_CFG): threshold, margin, hub_beta, lexical_guard, guard_hi."""
    lc = {**LINK_CFG, **(link_cfg or {})}
    df = df.reset_index(drop=True).copy()
    texts = df['skill_text'].astype(str).tolist()
    n = len(texts)
    status, reason = np.array(['rejected'] * n, dtype=object), np.array([''] * n, dtype=object)
    uri, label = np.array([None] * n, dtype=object), np.array([None] * n, dtype=object)
    sim, margin = np.zeros(n), np.zeros(n)
    exact, in_esco = np.zeros(n, bool), np.zeros(n, bool)

    junk = np.array([is_junk(t) for t in texts])
    reason[junk] = 'junk'
    todo = np.where(~junk)[0]
    if len(todo):
        sc, ix = esco_topk([texts[i] for i in todo], k=K_RETRIEVE)
        if lc['hub_beta'] > 0 and HUB_R is not None:           # demote labels that are close to everything, then re-rank
            sc = sc - lc['hub_beta'] * (HUB_R[ix] - HUB_R_MEAN)
            o = np.argsort(-sc, axis=1)
            sc, ix = np.take_along_axis(sc, o, 1), np.take_along_axis(ix, o, 1)
        U = esco_terms_df['conceptUri'].to_numpy(dtype=object)
        L = esco_terms_df['preferredLabel'].to_numpy(dtype=object)
        T = esco_terms_df['term'].to_numpy(dtype=object)
        for r, i in enumerate(todo):
            t, key = texts[i], _norm_key(texts[i])
            ov = LINK_OVERRIDES.get(key)
            if ov and ov[0] == 'DROP':
                reason[i] = 'override_drop'; continue
            if ov and ov[0] == 'MAP' and ov[1] in URI_OF_LABEL:
                status[i], uri[i], label[i], sim[i], margin[i], exact[i], in_esco[i] = 'accepted', URI_OF_LABEL[ov[1]], ov[1], 1.0, 1.0, True, True
                continue
            if ov and ov[0] == 'KEEP' and key not in EXACT:   # a real skill ESCO lacks (Pandas, React): accept as curated, never fuzzy-link it; exact ESCO labels keep their ESCO link
                canon = ov[1] or t
                status[i], uri[i], label[i], sim[i], margin[i], exact[i], in_esco[i] = 'accepted', 'curated:' + re.sub(r'[^a-z0-9]+', '-', canon.lower()).strip('-'), canon, 1.0, 1.0, False, False
                continue
            j = EXACT.get(key)
            if j is not None:
                status[i], uri[i], label[i], sim[i], margin[i], exact[i], in_esco[i] = 'accepted', U[j], L[j], 1.0, 1.0, True, True
                continue
            top = U[ix[r]]
            diff = np.nonzero(top != top[0])[0]
            m = float(sc[r, 0] - sc[r, diff[0]]) if len(diff) else 1.0
            sim[i], margin[i] = float(sc[r, 0]), m
            if NON_SKILL_RE.search(t):
                reason[i] = 'not_skill_words'; continue
            fuzzy_ok = sc[r, 0] >= lc['threshold'] and m >= lc['margin']
            guarded = fuzzy_ok and lc['lexical_guard'] and sc[r, 0] < lc['guard_hi'] and not lexically_related(t, T[ix[r, 0]], L[ix[r, 0]])
            if fuzzy_ok and not guarded:
                status[i], uri[i], label[i], in_esco[i] = 'accepted', top[0], L[ix[r, 0]], True
            elif KEEP_CURATED_NON_ESCO and key in CURATED:
                canon = CURATED[key]
                status[i], uri[i], label[i], in_esco[i] = 'accepted', 'curated:' + re.sub(r'[^a-z0-9]+', '-', canon.lower()).strip('-'), canon, False
            else:
                reason[i] = 'no_lexical_support' if guarded else ('below_threshold' if sc[r, 0] < lc['threshold'] else 'ambiguous')
    df['status'], df['reason'], df['esco_uri'], df['esco_label'] = status, reason, uri, label
    df['similarity'], df['margin'], df['exact'], df['in_esco'] = sim, margin, exact, in_esco
    return df

def collapse_to_skills(spans):
    """Accepted spans -> one row per document and ESCO skill."""
    acc = spans[spans['status'] == 'accepted'].sort_values('similarity', ascending=False)
    if acc.empty:
        return pd.DataFrame(columns=['doc_id', 'esco_uri', 'esco_label', 'in_esco', 'similarity', 'exact', 'mentions', 'surface_forms'])
    return (acc.groupby(['doc_id', 'esco_uri'], as_index=False, sort=False)
               .agg(esco_label=('esco_label', 'first'), in_esco=('in_esco', 'max'), similarity=('similarity', 'max'),
                    exact=('exact', 'max'), mentions=('skill_text', 'size'),
                    surface_forms=('skill_text', lambda s: sorted(set(s))[:5])))

# ==============================================================================
# 7a. Requirement blocklist (cell 83)
# ==============================================================================
def _load_blocklist():
    """The blocklist from 14h, reloaded from disk if 14h hasn't run this session. Returns an empty set when the file is missing."""
    p = os.path.join(RESULTS_DIR, 'requirement_blocklist.csv')
    if not os.path.exists(p):
        print(f"[blocklist] {os.path.basename(p)} missing — run 14h or the one-time seed to build it")
        return set()
    df = pd.read_csv(p, dtype=str)
    col = 'esco_uri' if 'esco_uri' in df.columns else df.columns[0]
    return set(df[col].dropna().astype(str))


def _apply_blocklist(prof, block=None):
    """Drop blocked requirements and renormalise weights. Merges the disk blocklist with any in-memory BLOCK.
    Safe to call on an empty frame or with an empty blocklist."""
    if block is None:
        block = _load_blocklist() | set(globals().get('BLOCK', set()))
    if not block or prof is None or len(prof) == 0:
        return prof
    keep = ~prof['esco_uri'].astype(str).isin(block)
    if keep.all():
        return prof
    removed = int((~keep).sum())
    prof = prof[keep].copy()
    if len(prof):
        prof['weight'] = prof['weight'] / prof['weight'].sum()
    print(f"  [blocklist] removed {removed} blocked requirement(s)")
    return prof.reset_index(drop=True)

# ==============================================================================
# 7b. Role profiles: static, frozen (cells 42, 84, 86)
# ==============================================================================
PROFILE_OF = {}
_rp = os.path.join(EXTRACT_DIR, 'role_profiles.parquet')
if os.path.exists(_rp):
    PROFILE_OF = {role: df.reset_index(drop=True) for role, df in pd.read_parquet(_rp).groupby('role')}   # section 10 output
else:
    print('[!] data/processed/extracted/role_profiles.parquet missing: no static fallback profiles')

def _static(role, reason):
    if role not in PROFILE_OF:
        raise ValueError(f"no profile for role {role!r}; available: {sorted(PROFILE_OF)}")
    p = PROFILE_OF[role].reset_index(drop=True)
    p = _apply_blocklist(p)                                   # same filter as the live path
    return p, {'source': 'static', 'role': role, 'reason': reason,
               'n_postings': int(p['n_postings'].iloc[0]) if 'n_postings' in p.columns and len(p) else 0}



def _frozen_snapshot():
    files = sorted(glob.glob(os.path.join(LIVE_DIR, 'release_*.parquet')))
    return pd.read_parquet(files[-1]) if files else None, (os.path.basename(files[-1])[8:-8] if files else None)

_PROFILE_PROVIDER = None

def set_profile_provider(provider):
    """Set an optional server-side source for profiles built from stored postings."""
    global _PROFILE_PROVIDER
    _PROFILE_PROVIDER = provider

def available_roles():
    """Roles the app can score: those in the latest frozen release, plus the static profiles as a fallback."""
    snap, _ = _frozen_snapshot()
    database_roles = set(_PROFILE_PROVIDER.available_roles()) if _PROFILE_PROVIDER is not None else set()
    return sorted((set(snap['role']) if snap is not None else set()) | set(PROFILE_OF) | database_roles)

def get_profile(role, mode=None):
    """(profile, info). mode 'frozen' (default) = latest release_*.parquet, then the static profile; 'static' = static only.
    The blocklist is applied to every path. (The notebook's 'live' mode needs a JSearch key and is not part of this package.)"""
    mode = mode or 'frozen'
    if mode == 'frozen':
        if _PROFILE_PROVIDER is not None:
            profile = _PROFILE_PROVIDER.get_profile(role)
            if profile is not None:
                prof, info = profile
                return _apply_blocklist(prof), info
        snap, tag = _frozen_snapshot()
        if snap is not None:
            p = snap[snap['role'] == role].reset_index(drop=True)
            if len(p):
                p = _apply_blocklist(p)
                return p, {'source': 'frozen', 'role': role, 'release': tag,
                           'n_postings': int(p['n_postings'].iloc[0]) if 'n_postings' in p.columns and len(p) else 0}
        reason = _PROFILE_PROVIDER.fallback_reason(role) if _PROFILE_PROVIDER is not None else None
        return _static(role, reason or 'no frozen release for this role yet')
    return _static(role, 'static mode')

# ==============================================================================
# 8a. Embeddings and the ESCO graph (cell 51)
# ==============================================================================
# ==============================================================================
# 13a. Embeddings and the ESCO graph
# ==============================================================================
from sklearn.feature_extraction.text import TfidfVectorizer

SBERT_MATCH = 0.75     # minimum SBERT similarity for a candidate skill to cover a required skill (tuned in section 14)
TFIDF_MATCH = 0.50     # same, for the TF-IDF baseline
GAP_CUTOFF  = 0.50     # a required skill is a gap when its credit is below this
ESCO_GRAPH_CREDIT = {'related': 0.40, 'sibling': 0.45}   # strictly below GAP_CUTOFF: they raise the index but the skill is still listed as a gap
assert max(ESCO_GRAPH_CREDIT.values()) < GAP_CUTOFF, 'graph credit >= GAP_CUTOFF would count related/sibling skills as covered'
METHODS = ('exact', 'tfidf', 'sbert', 'sbert_graph')

_LABEL_EMB = {}
def embed_labels(labels):
    """Unit-length SBERT vectors for skill labels, cached in memory."""
    new = [l for l in dict.fromkeys(labels) if l not in _LABEL_EMB]
    if new:
        vecs = sbert_model.encode(new, batch_size=128, normalize_embeddings=True, convert_to_numpy=True,
                                  show_progress_bar=len(new) > 2000).astype(np.float32)
        _LABEL_EMB.update(zip(new, vecs))
    if not labels:
        return np.zeros((0, sbert_model.get_sentence_embedding_dimension()), np.float32)
    return np.vstack([_LABEL_EMB[l] for l in labels])

_TFIDF = None
def _tfidf():
    global _TFIDF
    if _TFIDF is None:
        _TFIDF = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words='english').fit(
            esco_terms_df['term'].astype(str))
    return _TFIDF

def _col(df, *keys):
    return next((c for c in df.columns if all(k in c.lower() for k in keys)), None)

def load_esco_graph():
    """Related-skill links and skill-group (parent) links from the ESCO download; None when the files are missing."""
    rel_p = os.path.join(ESCO_DIR, 'skillSkillRelations_en.csv')
    br_p = os.path.join(ESCO_DIR, 'broaderRelationsSkillPillar_en.csv')
    if not (os.path.exists(rel_p) and os.path.exists(br_p)):
        print("ESCO graph files not found in", ESCO_DIR, "- sbert_graph will behave like sbert.\n"
              "  Download them with the ESCO CSV export (skillSkillRelations_en.csv, broaderRelationsSkillPillar_en.csv).")
        return None
    rel, br = pd.read_csv(rel_p, dtype=str), pd.read_csv(br_p, dtype=str)
    a, b = _col(rel, 'original'), _col(rel, 'related')
    child, parent = _col(br, 'concepturi'), _col(br, 'broaderuri')
    if None in (a, b, child, parent):
        print("ESCO graph files have unexpected columns:", list(rel.columns), list(br.columns), "- graph skipped.")
        return None
    related, parents, children = defaultdict(set), defaultdict(set), defaultdict(set)
    for u, v in zip(rel[a], rel[b]):
        related[u].add(v); related[v].add(u)
    for c, p in zip(br[child], br[parent]):
        parents[c].add(p); children[p].add(c)
    print(f"ESCO graph: {len(related):,} skills with related links, {len(parents):,} with a parent group")
    return {'related': related, 'parents': parents, 'children': children}

ESCO_GRAPH = load_esco_graph()

def graph_credit(uri, cand_uris, graph):
    """1 for the same skill, then the partial credits in ESCO_GRAPH_CREDIT for a related skill or a skill in the same group, else 0."""
    if graph is None:
        return 0.0
    if uri in cand_uris:
        return 1.0
    if graph['related'].get(uri, set()) & cand_uris:
        return ESCO_GRAPH_CREDIT['related']
    if any((graph['children'].get(p, set()) - {uri}) & cand_uris for p in graph['parents'].get(uri, ())):
        return ESCO_GRAPH_CREDIT['sibling']
    return 0.0

# ==============================================================================
# 8b. Empty skills table (cell 52)
# ==============================================================================
EMPTY_SKILLS = pd.DataFrame(columns=['doc_id', 'esco_uri', 'esco_label', 'in_esco', 'similarity', 'exact', 'mentions', 'surface_forms'])

# ==============================================================================
# 8c. Option A, taxonomy inheritance (cell 71)
# ==============================================================================
# ==============================================================================
# 16a. Option A - taxonomy inheritance: a skill the candidate has also covers its ESCO ancestors
# ==============================================================================
# Needs: section 13a (ESCO_GRAPH), 13b (RES_SKILLS_BY_DOC, EMPTY_SKILLS), 14c (SPANS_BY_DOC, EXCLUDE), PROFILE_OF.
# 14g measured graph links as *partial* credit and 14h hand-wrote an UMBRELLA word list. Here coverage flows up the real ESCO
# hierarchy instead: if the resume has any skill BELOW a required skill, the required (umbrella) skill is covered. It is directional:
# Python covers "computer programming", but "computer programming" does not cover Python.
INHERIT_MAX_DEPTH   = 2      # levels below the required skill that still count as "inside" it
INHERIT_MAX_DESC    = 150    # a node with more descendants than this is a top-level group ("working with computers"): one child must not cover it
INHERIT_MIN_SIM     = 0.85   # a descendant only passes coverage up when it was linked exactly or with at least this similarity (notebook patch)
USE_UMBRELLA_FALLBACK = True # also accept the hand-written UMBRELLA map from 14h where the graph has no children for that skill

def build_descendants(graph, max_depth=INHERIT_MAX_DEPTH, max_desc=INHERIT_MAX_DESC):
    """uri -> frozenset of descendant URIs up to max_depth levels. Nodes that are too broad are left out on purpose."""
    out = {}
    for node in graph['children']:
        seen, frontier = set(), {node}
        for _ in range(max_depth):
            nxt = set().union(*(graph['children'].get(n, set()) for n in frontier)) - seen - {node}
            seen |= nxt
            frontier = nxt
            if not frontier:
                break
        if 0 < len(seen) <= max_desc:
            out[node] = frozenset(seen)
    return out

DESC = build_descendants(ESCO_GRAPH) if ESCO_GRAPH is not None else {}

def inherited_cover(uri, cand_uris, cand_df=None, desc=None):
    """(covered, via_uri): True when the candidate has this skill itself, or a confidently linked skill below it.
    'Confident' = exact ESCO label / curated link, or similarity >= INHERIT_MIN_SIM. Pass the candidate skills table as cand_df
    to apply the gate; without it every candidate skill counts (the pre-patch behaviour)."""
    desc = DESC if desc is None else desc
    if uri in cand_uris:
        return True, uri
    if cand_df is not None and len(cand_df):
        ok = cand_df[(cand_df['exact'] == True) | (cand_df['similarity'] >= INHERIT_MIN_SIM)]
        valid = set(ok['esco_uri'])
    else:
        valid = cand_uris
    hit = desc.get(uri, frozenset()) & valid
    return (True, sorted(hit)[0]) if hit else (False, None)

def umbrella_term(req_label, text):
    """Fallback to the 14h word list (None when that cell has not been run)."""
    fn = globals().get('umbrella_hit')
    return fn(req_label, text) if (USE_UMBRELLA_FALLBACK and fn is not None) else None

# ==============================================================================
# 8d. Umbrella word list (cell 69)
# ==============================================================================
UMBRELLA = {
    # software
    'computer programming': ['python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'php', 'ruby', 'kotlin', 'swift', 'dart', 'scala', 'rust', '!Go', 'programming'],
    'software frameworks': ['!React', 'angular', 'vue', 'django', 'flask', 'spring', 'springboot', 'express.js', 'laravel', 'flutter', '.net', 'rails', 'next.js', 'bootstrap', 'jquery', 'framework'],
    'database': ['mysql', 'postgresql', 'postgres', 'mongodb', 'sqlite', 'oracle', 'firebase', 'redis', 'dynamodb', 'mariadb', 'sql server', 'nosql', 'database'],
    'web services': ['rest', 'restful', 'graphql', 'soap', 'microservice', 'web service', 'api'],
    'cloud technologies': ['aws', 'azure', 'gcp', 'google cloud', 'firebase', 'heroku', 'cloud'],
    'devops': ['docker', 'kubernetes', 'jenkins', 'ci/cd', 'terraform', 'ansible', 'github actions', 'gitlab', 'devops'],
    'implement front-end website design': ['html', 'css', '!React', 'angular', 'vue', 'front-end', 'frontend', 'front end', 'bootstrap', 'tailwind'],
    'data models': ['data model', 'data modeling', 'data modelling', 'er diagram', 'schema design', 'database design'],
    'use software design patterns': ['design pattern', 'mvc', 'singleton'],
    'systems development life-cycle': ['sdlc', 'software development lifecycle', 'software development life cycle', 'development lifecycle', 'project lifecycle'],
    # accounting, sales, HR
    'use accounting systems': ['quickbooks', 'sap', 'oracle financials', 'sage', 'xero', 'peoplesoft', 'netsuite', 'great plains', 'accounting software'],
    'use spreadsheets software': ['excel', 'google sheets', 'spreadsheet'],
    'use microsoft office': ['microsoft word', 'powerpoint', 'outlook', 'ms office', 'microsoft office', 'office suite'],
    'customer relationship management': ['salesforce', 'hubspot', 'zoho', 'dynamics 365', 'crm'],
    'human resource management': ['hris', 'adp', 'workday', 'human resource'],
    'electronic communication': ['email', 'e-mail', 'outlook'],
}
_UM = {k: [(t[1:], True) if t.startswith('!') else (t, False) for t in v] for k, v in UMBRELLA.items()}

def umbrella_hit(req_label, text):
    """The first child term of the requirement's umbrella found in the text, or None. Whole words, plural 's' tolerated."""
    for term, case in _UM.get(str(req_label).strip().lower(), ()):
        if re.search(r'(?<![A-Za-z0-9])' + re.escape(term) + r's?(?![A-Za-z0-9])', text, 0 if case else re.I):
            return term
    return None

# ==============================================================================
# 8e. Option B, context windows (cell 72)
# ==============================================================================
EXCLUDE = {'junk', 'not_skill_words', 'override_drop'}   # cell 58: rejected spans are never evidence
# ==============================================================================
# 16b. Option B - context windows: match the requirement against sentences, not only extracted spans
# ==============================================================================
# Needs: split_units (section 6), embed_labels (13a), RES_SKILLS_BY_DOC, SPANS_BY_DOC, EXCLUDE, RES_TEXT.
# An isolated span ("team", "stakeholders") loses the verb that makes it a skill ("led a team of 6", "presented to stakeholders").
# A window is one resume sentence/bullet or two neighbouring ones. It is embedded whole and compared with the requirement label.
CTX_MAX_WORDS = 60

def context_windows(text, max_words=CTX_MAX_WORDS):
    """Sentences/bullets of the resume plus every pair of neighbouring ones (lower-cased, de-duplicated)."""
    return [window for window, _ in context_window_sources(text, max_words)]

def context_window_sources(text, max_words=CTX_MAX_WORDS):
    """Context windows paired with their original-case CV text."""
    units = [u for u in split_units(text) if 3 <= len(u.split()) <= max_words]
    pairs = [units[i] + ' ' + units[i + 1] for i in range(len(units) - 1)
             if len(units[i].split()) + len(units[i + 1].split()) <= 2 * max_words]
    sources = {}
    for window in units + pairs:
        sources.setdefault(window.lower(), window)
    return list(sources.items())

def span_labels_of(cand, sp):
    """Everything extracted from one resume that can count as evidence: linked ESCO labels plus usable raw spans."""
    linked = cand['esco_label'].astype(str).tolist()
    raw = [] if sp is None else sp.loc[~sp['reason'].isin(EXCLUDE), 'skill_text'].astype(str).str.lower().tolist()
    return list(dict.fromkeys(linked + raw))

def span_evidence_of(cand, sp):
    """Original CV phrases aligned with span_labels_of, for citations in analysis results."""
    evidence = {}
    for row in cand.itertuples(index=False):
        forms = getattr(row, 'surface_forms', ())
        evidence.setdefault(str(row.esco_label).lower(), str(forms[0]) if forms else str(row.esco_label))
    if sp is not None:
        for snippet in sp.loc[~sp['reason'].isin(EXCLUDE), 'skill_text'].astype(str):
            evidence.setdefault(snippet.lower(), snippet)
    return [evidence[label.lower()] for label in span_labels_of(cand, sp)]

def _highlight_in_snippet(snippet, candidates):
    for candidate in sorted((str(value) for value in candidates if value), key=len, reverse=True):
        match = re.search(re.escape(candidate), snippet, re.IGNORECASE)
        if match:
            return snippet[match.start():match.end()]
    return snippet

def _maxsim(R, E):
    return np.zeros(len(R)) if E.shape[0] == 0 else (R @ E.T).max(axis=1)

# ==============================================================================
# 8f. Option C, z-score statistics (cell 73)
# ==============================================================================
# ==============================================================================
# 16c. Option C - z-score scaling of every similarity against the whole resume database
# ==============================================================================
# Needs 16b. A generic requirement ("communication") is close to nearly every resume, a specific one ("Kubernetes") to few. One fixed
# threshold treats them the same. For each requirement we learn mean and std of the best similarity over the background resumes, and
# compare z = (sim - mean) / std instead. The statistics are computed once, cached, and saved to JSON, so a backend only needs the JSON.
Z_SD_FLOOR = 0.03     # a requirement every resume matches equally would otherwise get a huge z from tiny noise
Z_CLIP     = (-5.0, 10.0)
MIN_BG     = 30       # fewer background resumes than this and the statistics are not trustworthy

class NormStats:
    def __init__(self, evidence_list=None, floor=Z_SD_FLOOR, fallback=None):
        self.E = [e for e in (evidence_list or []) if e.shape[0] > 0]    # resumes with no evidence would drag the mean down
        self.floor, self.s = floor, {}
        self.fallback = fallback      # (mean, std) used for a requirement without saved statistics, when no background resumes are loaded
        self.missing = set()
    def ensure(self, labels):
        new = [l for l in dict.fromkeys(labels) if l not in self.s]
        if not new:
            return
        if not self.E and self.fallback is not None:      # the notebook's own fallback constants (cell 98); flagged in NormStats.missing
            for l in new:
                self.s[l] = (float(self.fallback[0]), float(max(self.fallback[1], self.floor)))
                self.missing.add(l)
            return
        if not self.E:
            raise KeyError(f"no statistics for {len(new)} requirement(s), e.g. {new[:3]}; rebuild with background resumes (NormStats(evidence))")
        R = embed_labels(new)
        M = np.vstack([_maxsim(R, E) for E in self.E])                    # background resumes x new requirements
        for l, a, b in zip(new, M.mean(axis=0), M.std(axis=0)):
            self.s[l] = (float(a), float(max(b, self.floor)))
    def z(self, labels, sims):
        labels = list(labels)
        self.ensure(labels)
        return np.clip(np.array([(x - self.s[l][0]) / self.s[l][1] for l, x in zip(labels, sims)]), *Z_CLIP)
    def save(self, path):
        json.dump({'floor': self.floor, 'stats': self.s}, open(path, 'w'))
    @classmethod
    def load(cls, path, fallback=None):
        d = json.load(open(path)); ns = cls([], d['floor'], fallback=fallback); ns.s = {k: tuple(v) for k, v in d['stats'].items()}
        return ns

# ==============================================================================
# 8g. Rule components (cell 75)
# ==============================================================================
def rule_components(name):
    """'A+B+C: ...' -> which of Option A (inheritance), B (windows), C (z-score) the rule uses."""
    tok = set(name.split(':')[0].split('+'))
    return {'A': 'A' in tok, 'B': 'B' in tok, 'C': 'C' in tok}

# ==============================================================================
# 9. The matcher and run_v2 (cell 77)
# ==============================================================================
# ==============================================================================
# 16e. The upgraded matcher as a function, saved config, and a live run on a CV
# ==============================================================================
# Needs 16a-16d. Same call pattern as section 15, but explains WHY each requirement counts as covered.
# Evidence floor: a closest span below this similarity is shown as nothing / as the posting wording, not as a "match".
# 0.60 is a judgement call from one CV table (Cisco for CI/CD = 0.34 is noise; 'aws ai' for AWS = 0.71 is a useful near miss). Tune it.
EVIDENCE_MIN_SIM = 0.60
WIN_MIN_RAW_SIM = 0.65
SPAN_MIN_RAW_SIM = 0.68

def _posting_phrases(role, prof=None):
    """{esco_uri: [phrases job postings use]} for a role, or {} when the phrase tables were never built in this session."""
    g = globals()
    for name in ('PH_ALL', 'PHRASES'):
        d = g.get(name)
        if isinstance(d, dict) and role in d:
            return d[role]
    return {}

def _phrase_list(value, limit=6):
    """Posting phrases as a clean list of lower-case strings. Accepts a list (role_phrases.json) or an 'a | b | c' string."""
    if value is None:
        return []
    items = value.split('|') if isinstance(value, str) else list(value)
    return [str(x).strip().lower() for x in items if str(x).strip()][:limit]

def _shown_evidence(span, sim, phrases, floor=None):
    """Show the closest CV span only when it is close; otherwise say so and show how postings word the requirement."""
    floor = EVIDENCE_MIN_SIM if floor is None else floor
    if span and sim >= floor:
        return str(span)[:90]
    ph = [p for p in _phrase_list(phrases, limit=2)]
    return ('no close match in CV; postings say: ' + ' | '.join(ph))[:90] if ph else ''

def match_v2(cand, sp, text, prof, rule=None, thr=None, phrases=None):
    """Apply the v22 notebook matcher and return one evidence row per required skill."""
    rule, thr = rule or V2_RULE, V2_T if thr is None else thr
    comp = rule_components(rule)
    use_A, use_win, use_z = comp['A'], comp['B'], comp['C']
    labels = prof['esco_label'].astype(str).tolist()
    cu = set(cand['esco_uri']); uri_label = dict(zip(cand['esco_uri'], cand['esco_label']))
    ev_s = span_labels_of(cand, sp)
    ev_s_sources = span_evidence_of(cand, sp)
    window_sources = context_window_sources(text) if use_win else []
    wins = [window for window, _ in window_sources]
    R = embed_labels(labels)
    Es, Ew = embed_labels(ev_s), embed_labels(wins)
    S_s = (R @ Es.T) if len(ev_s) else np.zeros((len(labels), 1)); S_w = (R @ Ew.T) if len(wins) else np.zeros((len(labels), 1))
    s_s, s_w = S_s.max(axis=1), S_w.max(axis=1)

    # The notebook applies posting-phrase similarities to span scores for every selected rule.
    if len(ev_s):
        s_phr = np.zeros(len(labels))
        for i, u in enumerate(prof['esco_uri']):
            ph = _phrase_list((phrases or {}).get(u))
            if ph:
                s_phr[i] = float((embed_labels(ph) @ Es.T).max())
        s_s = np.maximum(s_s, s_phr)

    if use_z:
        z_s = np.where(
            (s_s >= SPAN_MIN_RAW_SIM)
            & np.array([has_explicit_tool_mention(label, text, CAP_REQUIRED, EXTRACTION_CFG.get('tool_guard', False))
                        for label in labels]),
            NS_SPANS.z(labels, s_s),
            -9.0,
        )
        z_w = np.where(
            (s_w >= WIN_MIN_RAW_SIM)
            & np.array([has_explicit_tool_mention(label, text, CAP_REQUIRED, EXTRACTION_CFG.get('tool_guard', False))
                        for label in labels]),
            NS_WIN.z(labels, s_w),
            -9.0,
        ) if use_win else np.full(len(labels), -9.0)
        score = np.maximum(z_s, z_w) if use_win else z_s
    else:
        z_s, z_w = s_s, s_w
        score = np.maximum(s_s, s_w) if use_win else s_s

    is_cert_line = is_certificate_text(text)
    out = []
    for i, (u, l) in enumerate(zip(prof['esco_uri'], labels)):
        inh_ok, inh_uri = inherited_cover(u, cu, cand) if use_A else (False, None)
        um = umbrella_term(l, text) if (use_A and not is_cert_line) else None
        win_won = bool(use_win and z_w[i] > z_s[i])
        mention_ok = has_explicit_tool_mention(l, text, CAP_REQUIRED, EXTRACTION_CFG.get('tool_guard', False))
        inherited_reason = f"inherited from '{uri_label.get(inh_uri, '?')}'" if inh_ok else None
        reason, cov = coverage_decision(
            exact=u in cu,
            inherited_reason=inherited_reason,
            umbrella_term=um,
            score=float(score[i]),
            threshold=float(thr),
            tool_mention_allowed=mention_ok,
        )
        if reason == "match":
            reason = "context window" if win_won else "extracted span"

        span_index = int(S_s[i].argmax()) if ev_s else None
        window_index = int(S_w[i].argmax()) if wins else None
        use_window = win_won and window_index is not None
        ev = wins[window_index] if use_window else (ev_s[span_index] if span_index is not None else '')
        cv_evidence = window_sources[window_index][1] if use_window else (
            ev_s_sources[span_index] if span_index is not None else ''
        )
        if cov and not cv_evidence and reason.startswith('umbrella term '):
            umbrella = reason[len('umbrella term '):].strip("'")
            for source in split_units(text):
                if re.search(r'(?<![A-Za-z0-9])' + re.escape(umbrella) + r's?(?![A-Za-z0-9])', source, re.I):
                    cv_evidence = source
                    break
        highlight_candidates = ([ev_s_sources[span_index]] if span_index is not None else []) + [l]
        if reason.startswith('umbrella term '):
            highlight_candidates.insert(0, reason[len('umbrella term '):].strip("'"))
        cv_highlight = _highlight_in_snippet(cv_evidence, highlight_candidates) if cv_evidence else ''
        raw_best = float(s_w[i] if use_window else s_s[i])
        disp = float(NS_SPANS.z([l], [s_s[i]])[0]) if (use_z and score[i] <= -9.0) else float(score[i])
        out.append({'esco_uri': u, 'esco_label': l, 'weight': float(prof['weight'].iloc[i]), 'covered': cov, 'reason': reason,
                    'score': round(disp, 2), 'closest_evidence': _shown_evidence(ev, raw_best, (phrases or {}).get(u, [])),
                    'cv_evidence': cv_evidence if cov else '',
                    'cv_highlight': cv_highlight if cov else '',
                    'gap_confidence': round(float(1 / (1 + np.exp((disp - thr) * (1.0 if use_z else 12.0)))), 2)})
    return pd.DataFrame(out)

def run_v2(text, role, profile=None):
    """Raw CV text + role -> {have, missing, readiness} plus the per-requirement table."""
    if 'V2_RULE' not in globals() or globals().get('V2_RULE') is None:
        _reload_v2_config()
    role = {r.lower(): r for r in PROFILE_OF}.get(role.strip().lower(), role)
    started = time.perf_counter()
    sections = parse_resume_sections(text)
    raw = extract_docs([text], ['live'], EXTRACTION_CFG)
    extracted_at = time.perf_counter()
    sp = standardise_spans(raw) if len(raw) else None
    if sp is not None:
        sp['resume_section'] = [
            section_for_text(str(unit), sections)
            for unit in sp['unit'].astype(str)
        ]
    cand = collapse_to_skills(sp) if sp is not None else EMPTY_SKILLS
    linked_at = time.perf_counter()
    prof = (PROFILE_OF[role] if profile is None else profile).reset_index(drop=True)
    tab = match_v2(cand, sp, text, prof, phrases=_posting_phrases(role))
    tab = apply_section_credit(tab, cand, sp, sections)
    matched_at = time.perf_counter()
    ready = float((tab['weight'] * tab['credit']).sum() / tab['weight'].sum())
    return {'have': tab.loc[tab['credit'] >= 1.0, 'esco_label'].tolist(),
            'missing': [
                {'skill': row.esco_label, 'confidence': row.gap_confidence,
                 'credit': float(row.credit), 'evidence_section': row.evidence_section}
                for row in tab.loc[tab['credit'] < 1.0].itertuples()
            ],
            'readiness': round(ready, 3), 'table': tab,
            'resume_sections': list(dict.fromkeys(category for category, _ in sections)),
            'extracted_skills': [
                {'skill': r.esco_label, 'uri': r.esco_uri, 'in_esco': bool(r.in_esco), 'mentions': int(r.mentions)}
                for r in cand.itertuples()
            ],
            'timings_ms': {
                'extract': int((extracted_at - started) * 1000),
                'link': int((linked_at - extracted_at) * 1000),
                'match': int((matched_at - linked_at) * 1000),
            }}


V2_RULE = V2_T = V2_USE = None
NS_SPANS = NS_WIN = None
def _reload_v2_config():
    """Restore V2_RULE / V2_T / V2_USE / NS_* from disk if a fresh session skipped 16d."""
    global V2_RULE, V2_T, V2_USE, NS_SPANS, NS_WIN, INHERIT_MAX_DEPTH, INHERIT_MAX_DESC
    cfg_path = os.path.join(RESULTS_DIR, 'matching_v2_config.json')
    if not os.path.exists(cfg_path):
        raise RuntimeError("matching_v2_config.json missing: run section 16d once to fit the rule")
    cfg = json.load(open(cfg_path))
    V2_RULE = cfg['rule']
    V2_T = float(cfg['threshold'])
    V2_USE = cfg['use']
    INHERIT_MAX_DEPTH = int(cfg.get('inherit_max_depth', INHERIT_MAX_DEPTH))
    INHERIT_MAX_DESC = int(cfg.get('inherit_max_desc', INHERIT_MAX_DESC))
    NS_SPANS = NormStats.load(os.path.join(RESULTS_DIR, 'matching_v2_stats_spans.json'), fallback=(0.35, 0.15))
    NS_WIN   = NormStats.load(os.path.join(RESULTS_DIR, 'matching_v2_stats_windows.json'), fallback=(0.25, 0.12))
    print(f"[run_v2] restored rule={V2_RULE!r} threshold={V2_T:.2f} components={V2_USE}")

# ==============================================================================
# 10. Posting phrases, scoring entry point, CV reading (cells 86, 98; phrases are new)
# ==============================================================================
PH_ALL = {}                      # {role: {esco_uri: [phrases postings use]}}, exported from the notebook by export_from_notebook.py
_php = os.path.join(RESULTS_DIR, 'role_phrases.json')
if os.path.exists(_php):
    PH_ALL = json.load(open(_php))

def score_cv(cv_text, role, mode=None):
    prof, info = get_profile(role, mode)
    res = run_v2(cv_text, role, profile=prof)
    res['profile'] = {k: info.get(k) for k in ('source', 'release', 'n_postings', 'age_h', 'country', 'reason')}
    return res


def _docx_text(path):
    """All text of a Word file in reading order, INCLUDING tables. python-docx's `doc.paragraphs` skips table cells, and many CVs put
    their skills (or the whole layout) in tables: v16 extracted only 219 words from the test CV and scored it 0.04.
    Repeated text from merged cells is collapsed."""
    try:
        import docx
    except ImportError:
        raise ImportError('python-docx is required for .docx files')
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    document = docx.Document(path)
    out = []

    def walk(parent_elm, parent):
        for child in parent_elm.iterchildren():
            tag = child.tag.rsplit('}', 1)[-1]
            if tag == 'p':
                t = Paragraph(child, parent).text.strip()
                if t:
                    out.append(t)
            elif tag == 'tbl':
                for row in Table(child, parent).rows:
                    seen = []
                    for cell in row.cells:
                        if any(cell._tc is s for s in seen):          # a merged cell appears once per column it spans
                            continue
                        seen.append(cell._tc)
                        walk(cell._tc, cell)                           # nested tables and paragraphs inside the cell
    walk(document.element.body, document)
    for section in document.sections:                                    # headers and footers often hold the name/contact block only: add, never required
        for part in (section.header, section.footer):
            for p in part.paragraphs:
                if p.text.strip():
                    out.append(p.text.strip())
    return "\n".join(out)

def read_resume_file(path):
    """.docx (with tables), .pdf (pypdf) or .txt -> text."""
    low = path.lower()
    if low.endswith('.docx'):
        return _docx_text(path)
    if low.endswith('.pdf'):
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
    with open(path, encoding='utf-8', errors='ignore') as f:
        return f.read()


# ==============================================================================
# 11. Notebook-parity switches (applied in memory only; no file is written)
# ==============================================================================
# The notebook turns the NER filter on after saving extraction_config.json, so the module does the same.
# Needs: python -m spacy download en_core_web_sm. The flag is part of the extraction cache key, so old cached spans are not reused.
EXTRACTION_CFG['ner_filter'] = True

# The notebook adds a 'vs code' MAP override to link_overrides.csv; register it here without touching the file.
_VSCODE_SPAN, _VSCODE_LABEL = 'vs code', 'use software development tools'
if _VSCODE_LABEL in URI_OF_LABEL:
    LINK_OVERRIDES.setdefault(_norm_key(_VSCODE_SPAN), ('MAP', _VSCODE_LABEL))
    PROTECTED_EXTRA.add(_gaz_key(_VSCODE_SPAN))      # the NER filter must never remove it


_reload_v2_config()
print("SkillXray ready | roles:", len(available_roles()))