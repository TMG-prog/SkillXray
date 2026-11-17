"""Uploaded resume (PDF / DOCX / TXT) -> plain text."""
from __future__ import annotations

import io
import re


class UnsupportedFile(ValueError):
    pass


def _reflow(text: str) -> str:
    """PDFs break lines at the page width, not at sentence ends. Join a line onto the previous one when the
    previous line has no closing punctuation and the next starts lowercase, but keep bullets and headings apart."""
    lines = [re.sub(r"^[-*\u2013]\s+", "\u2022 ", l.strip()) for l in text.replace("\r", "\n").split("\n")]
    out = []
    for l in lines:
        if not l:
            out.append("")
            continue
        if out and out[-1] and not re.search(r"[.!?:;]$", out[-1]) and l[:1].islower() \
                and not re.match(r"^[\u2022\u25AA\u2023\u25CF\u25E6\u00B7\-*]\s*", l):
            out[-1] = out[-1] + " " + l
        else:
            out.append(l)
    # The extraction code (kept identical to the notebook) flattens line breaks before it splits sentences, so a
    # heading or bullet with no full stop would run into the next line. Ending each line with one keeps them apart.
    out = [l if (not l or re.search(r"[.!?:;,]$", l)) else l + "." for l in out]
    return "\n".join(out)


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        try:
            if not reader.decrypt(""):
                raise UnsupportedFile("This PDF is password-protected.")
        except UnsupportedFile:
            raise
        except Exception:
            raise UnsupportedFile("This PDF is password-protected.")
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def _docx(data: bytes) -> str:
    import docx
    d = docx.Document(io.BytesIO(data))
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            parts += [c.text for c in row.cells]
    return "\n".join(parts)


def extract_text(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if data[:4] == b"%PDF" or name.endswith(".pdf"):
        text = _pdf(data)
    elif data[:2] == b"PK" or name.endswith(".docx"):
        text = _docx(data)
    elif name.endswith(".doc"):
        raise UnsupportedFile("Old .doc files are not supported. Save the resume as .docx or PDF.")
    elif name.endswith(".txt") or not name:
        text = data.decode("utf-8", errors="replace")
    else:
        raise UnsupportedFile("Unsupported file type. Upload a PDF, DOCX or TXT resume.")
    text = _reflow(text)
    if len(re.sub(r"\s+", "", text)) < 50:
        raise UnsupportedFile("Could not read any text from this file. If it is a scanned image, "
                              "upload a text-based PDF or DOCX instead.")
    return text
