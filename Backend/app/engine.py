"""Skill extraction: resume text -> candidate skill spans.

Ported from notebook sections 3 and 6/6b. The logic is unchanged; the differences are only:
  * no Drive, no global caches: the models and the dictionary are held by an Extractor object
  * torch / transformers are imported only inside SpanExtractor, so the rest can be tested without them
  * the POS filter is not ported: in the notebook keep_span() returns True in every branch, so it never removed anything
"""
from __future__ import annotations

import re

import numpy as np

from . import config as C

CHUNK_OVERLAP = 2

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

# ------------------------------------------------------------------ dictionary vocabulary (notebook 6b)
TOOLS = [
    "Python", "SQL", "Java", "JavaScript", "TypeScript", "React", "Node.js",
    "Express", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git", "GitHub",
    "Excel", "Tableau", "Power BI", "PyTorch", "TensorFlow", "Pandas", "NumPy",
    "PostgreSQL", "MySQL", "MongoDB", "Hadoop", "Spark", "Kafka", "Hive",
    "Salesforce", "QuickBooks", "SAP", "Jira", "Shell", "Bash", "Linux",
    "Photoshop", "PowerPoint", "Outlook", "C++", "C#",
]
GENERIC = {
    ("plan",), ("report",), ("work",), ("team",), ("support",), ("service",),
    ("services",), ("business",), ("manage",), ("develop",), ("create",),
    ("design",), ("time",), ("review",), ("test",), ("use",), ("schedule",),
    ("terms",), ("training",), ("infrastructure",), ("assess",), ("climb",),
}
DEFAULT_EXTRA_TERMS = [
    "attention to detail", "regulatory compliance", "strategic finance", "service excellence",
    "lesson plans", "multidisciplinary interventions", "professional development",
    "marketing budget", "marketing plan", "high-speed internet", "software program management",
    "business development", "account management", "contract management", "document management",
    "capacity analysis", "sales meetings", "marketing personnel", "cellular reception", "accuracy",
    "routing", "configuration", "cost estimation", "distribution expansion", "bootstrapping", "CRM",
]


def _norm_tuple(s):
    return tuple(re.findall(r"[a-z0-9+#.]+", s.lower()))


def build_gazetteer(esco_df, tools, extra=()):
    terms = []
    if esco_df is not None and "preferredLabel" in esco_df.columns:
        alts = esco_df["altLabels"] if "altLabels" in esco_df.columns else [None] * len(esco_df)
        for pref, alt in zip(esco_df["preferredLabel"], alts):
            terms.append(str(pref))
            if isinstance(alt, str):
                terms += [a.strip() for a in alt.split("\n") if a.strip()]
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


# ------------------------------------------------------------------ text cleaning (notebook 6)
def clean_skill_span(text):
    text = re.sub(r"\s+", " ", str(text)).strip()
    for _ in range(3):
        text = re.sub(r"^[,;:\-\u2013\u2014/&*]+\s*", "", text)
        text = re.sub(r"\s*[,;:\-\u2013\u2014/&.*]+$", "", text)
        text = re.sub(r"^" + _EDGE + r"\s+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+" + _EDGE + r"$", "", text, flags=re.IGNORECASE)
    return text.strip()


def is_noise_unit(text):
    if _SALARY_NUM.search(text) and _SALARY_WORD.search(text):
        return True
    return bool(_EEO.search(text) or _POSTING_BOILERPLATE.search(text))


def is_noise_span(text):
    text = str(text).strip()
    if not text or "$" in text:
        return True
    letters = sum(ch.isalpha() for ch in text)
    if letters < 2:
        return True
    if letters < 0.5 * len(text):
        return True
    return False


def normalize_skill(text):
    return tuple(t.lower().strip(".") for t in TOKEN_PATTERN.findall(str(text)))


def contains_token_sequence(container, phrase):
    if not phrase or len(phrase) > len(container):
        return False
    return any(container[i:i + len(phrase)] == phrase for i in range(len(container) - len(phrase) + 1))


def clean_document_text(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r"(?i)\b(job\s+)?description[:\-\s]*", " ", text)
    text = re.sub(r"(?i)\bwhere\s+you'?ll\s+be\s+wor.*", " ", text)
    text = re.sub(r"\s*\([^)]*\)", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_SENT = None


def sent_nlp():
    """Rule-based sentence splitter (no model download)."""
    global _SENT
    if _SENT is None:
        import spacy
        _SENT = spacy.blank("en")
        _SENT.add_pipe("sentencizer")
    return _SENT


def split_units(text, max_words=None, overlap=CHUNK_OVERLAP):
    max_words = max_words or C.MAX_UNIT_WORDS
    if not isinstance(text, str):
        return []
    text = clean_document_text(text)
    parts = re.split(r"[\r\n]+|[\u2022\u25AA\u2023\u25CF\u25E6\u00B7]", text)
    parts = [p.strip() for p in parts if len(p.strip()) >= 3]
    units, seen = [], set()
    for doc in sent_nlp().pipe(parts, batch_size=256):
        for sent in doc.sents:
            sentence = sent.text.strip()
            if len(sentence) < 3 or not re.search(r"[A-Za-z]", sentence) or is_noise_unit(sentence):
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


# ------------------------------------------------------------------ model output -> spans (notebook 3)
def resolve_bio_ids(id2label):
    m = {}
    for k, v in id2label.items():
        tag = str(v).upper().split("-")[0]
        if tag in ("B", "I", "O"):
            m[tag] = int(k)
    if set(m) != {"B", "I", "O"}:
        m = {"B": 0, "I": 1, "O": 2}
    return m["B"], m["I"], m["O"]


def decode_words(text, words, tau):
    spans, cur = [], None
    for s, e, ps, is_b in words:
        if ps >= tau:
            if cur is None or is_b:
                if cur is not None:
                    spans.append(cur)
                cur = {"start": s, "end": e, "ps": [ps]}
            else:
                cur["end"] = e
                cur["ps"].append(ps)
        elif cur is not None:
            spans.append(cur)
            cur = None
    if cur is not None:
        spans.append(cur)
    return [{"start": c["start"], "end": c["end"], "score": float(np.mean(c["ps"])),
             "text": text[c["start"]:c["end"]].strip()} for c in spans]


def snap_spans(text, spans):
    out = []
    for sp in spans:
        s, e = sp["start"], sp["end"]
        while s > 0 and not text[s - 1].isspace():
            s -= 1
        while e < len(text) and not text[e].isspace():
            e += 1
        out.append({**sp, "start": s, "end": e, "text": text[s:e].strip()})
    return out


class SpanExtractor:
    """A JobBERT token-classification checkpoint. Same code as the notebook."""

    def __init__(self, repo, quantize=True, max_tokens=160):
        import torch
        from transformers import AutoModelForTokenClassification, AutoTokenizer
        self._torch = torch
        self.repo, self.max_tokens = repo, max_tokens
        self.tok = AutoTokenizer.from_pretrained(repo)
        model = AutoModelForTokenClassification.from_pretrained(repo).eval()
        self.b_id, self.i_id, self.o_id = resolve_bio_ids(model.config.id2label)
        if quantize:
            try:
                from torch.ao.quantization import quantize_dynamic
                model = quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
            except Exception as e:  # pragma: no cover
                print("  quantisation skipped:", e)
        self.model = model

    def predict_word_scores(self, texts, batch_size=32):
        torch = self._torch
        out = [None] * len(texts)
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        for b in range(0, len(order), batch_size):
            idx = order[b:b + batch_size]
            batch = [texts[i] for i in idx]
            enc = self.tok(batch, truncation=True, max_length=self.max_tokens, padding=True,
                           return_tensors="pt", return_offsets_mapping=True)
            feed = {k: v for k, v in enc.items() if k != "offset_mapping"}
            with torch.inference_mode():
                probs = torch.softmax(self.model(**feed).logits, dim=-1).cpu().numpy()
            offs = enc["offset_mapping"].numpy()
            for j, i in enumerate(idx):
                words, order_w = {}, []
                for t, w in enumerate(enc.word_ids(j)):
                    if w is None:
                        continue
                    s, e = int(offs[j][t][0]), int(offs[j][t][1])
                    if e <= s:
                        continue
                    if w not in words:
                        words[w] = [s, e, t]
                        order_w.append(w)
                    else:
                        words[w][1] = max(words[w][1], e)
                res = []
                for w in order_w:
                    s, e, t = words[w]
                    p = probs[j][t]
                    res.append((s, e, float(p[self.b_id]), float(p[self.i_id]), float(p[self.o_id])))
                out[i] = res
        return out

    def predict_words(self, texts, batch_size=32):
        return [[(s, e, 1.0 - po, pb >= pi) for s, e, pb, pi, po in words]
                for words in self.predict_word_scores(texts, batch_size)]


# ------------------------------------------------------------------ gazetteer, combining, post-processing (notebook 6)
def gazetteer_spans(text, gaz, max_len=6):
    toks = [(m.group(), m.start(), m.end()) for m in TOKEN_PATTERN.finditer(text)]
    normalized = [re.sub(r"^\.+|\.+$", "", t.lower()) or t.lower() for t, _, _ in toks]
    out, i = [], 0
    while i < len(toks):
        hit = None
        for length in range(min(max_len, len(toks) - i), 0, -1):
            if tuple(normalized[i:i + length]) in gaz:
                hit = length
                break
        if hit:
            start, end = toks[i][1], toks[i + hit - 1][2]
            out.append(text[start:end].strip(" ."))
            i += hit
        else:
            i += 1
    return out


def add_gazetteer(unit, spans, gaz):
    if not gaz:
        return spans
    out = list(spans)
    for phrase in gazetteer_spans(unit, gaz):
        phrase_norm = normalize_skill(phrase)
        if not phrase_norm:
            continue
        existing_norms = [normalize_skill(item["skill_text"]) for item in out]
        if any(contains_token_sequence(e, phrase_norm) for e in existing_norms):
            continue
        kept = []
        for item, existing in zip(out, existing_norms):
            if existing and contains_token_sequence(phrase_norm, existing):
                continue
            kept.append(item)
        out = kept
        out.append({"skill_text": phrase, "score": 1.0, "src": "dict"})
    return out


def combine_models(per_model):
    all_spans = [{**span, "src": name} for name, spans in per_model.items() for span in spans]
    if len(per_model) <= 1:
        return sorted(all_spans, key=lambda s: s["start"])
    all_spans.sort(key=lambda s: -s["score"])
    kept = []
    for span in all_spans:
        overlaps = any(not (span["end"] <= existing["start"] or span["start"] >= existing["end"])
                       for existing in kept)
        if not overlaps:
            kept.append(span)
    return sorted(kept, key=lambda s: s["start"])


def postprocess_spans(spans, cfg):
    out, seen = [], set()
    for span in spans:
        if span["score"] < cfg.get("min_score", 0.0):
            continue
        text = clean_skill_span(span["text"])
        if len(text) < 2 or not re.search(r"[A-Za-z]", text) or is_noise_span(text):
            continue
        max_words = cfg.get("max_words")
        if max_words and len(text.split()) > max_words:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append({"skill_text": text, "score": float(span["score"]), "src": span.get("src", "")})
    return out


class Extractor:
    """Resume text -> list of {skill_text, score, src, unit}."""

    def __init__(self, span_extractors: dict, cfg: dict, gaz: dict):
        self.models = span_extractors
        self.cfg = cfg
        self.gaz = gaz
        self.active = [m for m in cfg["models"] if m in span_extractors]
        if not self.active:
            raise RuntimeError(f"none of the configured models {cfg['models']} is loaded")

    def extract(self, text: str, batch_size: int = 32) -> list[dict]:
        units = split_units(text)
        raw = {name: {} for name in self.active}
        for name in self.active:
            todo = sorted(dict.fromkeys(units), key=len)
            for start in range(0, len(todo), 512):
                chunk = todo[start:start + 512]
                for t, res in zip(chunk, self.models[name].predict_words(chunk, batch_size=batch_size)):
                    raw[name][t] = res
        rows = []
        for unit in units:
            per_model = {}
            for name in self.active:
                words = raw[name].get(unit)
                if words is None:
                    continue
                per_model[name] = snap_spans(unit, decode_words(unit, words, self.cfg["tau"][name]))
            processed = postprocess_spans(combine_models(per_model), self.cfg)
            if self.cfg.get("gazetteer"):
                processed = add_gazetteer(unit, processed, self.gaz)
            rows += [{**p, "unit": unit[:300]} for p in processed]
        return rows
