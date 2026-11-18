"""Step 2: structure-aware chunking for Vietnamese legal documents.

Hierarchy:  Chương (chapter) > Điều (article) > Khoản (clause: "1.", "2.")
One chunk = one Article. If an Article is longer than MAX_CHUNK_CHARS it is
split by Clause. Each chunk keeps metadata so answers can cite the source.
"""
import re
from dataclasses import dataclass, asdict

from ingestion.config import MAX_CHUNK_CHARS

CHAPTER_RE = re.compile(r"^(Chương|CHƯƠNG)\s+([IVXLCDM\d]+)\b", re.UNICODE)
ARTICLE_RE = re.compile(r"^Điều\s+(\d+[a-z]?)\s*[.:]\s*(.*)$", re.UNICODE)
CLAUSE_RE = re.compile(r"^(\d+)\.\s+")


@dataclass
class Chunk:
    doc_name: str
    chapter: str
    article: str
    article_title: str
    clause: str
    text: str
    part: int = 0  # position inside its Article; keeps point IDs unique

    def as_payload(self) -> dict:
        return asdict(self)


def _split_long(body: str, limit: int) -> list[tuple[str, str]]:
    """Split an over-long article into (clause_label, text) parts."""
    parts, label, buf = [], "", []
    for line in body.splitlines():
        m = CLAUSE_RE.match(line)
        if m and buf:
            parts.append((label, "\n".join(buf)))
            buf = []
        if m:
            label = m.group(1)
        buf.append(line)
    if buf:
        parts.append((label, "\n".join(buf)))
    # merge small neighbours, hard-split oversize pieces
    merged: list[tuple[str, str]] = []
    for lab, txt in parts:
        while len(txt) > limit:
            merged.append((lab, txt[:limit]))
            txt = txt[limit:]
        if merged and len(merged[-1][1]) + len(txt) + 1 <= limit and not lab == "":
            prev_lab, prev_txt = merged[-1]
            merged[-1] = (prev_lab, prev_txt + "\n" + txt)
        else:
            merged.append((lab, txt))
    return merged


def chunk_document(doc_name: str, text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[Chunk]:
    chunks: list[Chunk] = []
    chapter = ""
    cur_article, cur_title, cur_lines = None, "", []
    expect_chapter_title = False

    def flush():
        nonlocal cur_article, cur_title, cur_lines
        if cur_article is None:
            return
        start = len(chunks)
        body = "\n".join(cur_lines).strip()
        header = f"Điều {cur_article}. {cur_title}".strip()
        if len(body) <= max_chars:
            chunks.append(Chunk(doc_name, chapter, cur_article, cur_title, "", f"{header}\n{body}".strip()))
        else:
            for lab, part in _split_long(body, max_chars):
                chunks.append(Chunk(doc_name, chapter, cur_article, cur_title, lab, f"{header}\n{part}".strip()))
        for i, c in enumerate(chunks[start:]):
            c.part = i
        cur_article, cur_title, cur_lines = None, "", []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m_ch = CHAPTER_RE.match(line)
        if m_ch:
            flush()
            chapter = line
            expect_chapter_title = True
            continue
        if expect_chapter_title and not ARTICLE_RE.match(line):
            chapter = f"{chapter} - {line}"  # chapter name sits on the next line
            expect_chapter_title = False
            continue
        expect_chapter_title = False
        m_ar = ARTICLE_RE.match(line)
        if m_ar:
            flush()
            cur_article, cur_title = m_ar.group(1), m_ar.group(2).strip()
            continue
        if cur_article is not None:
            cur_lines.append(line)
    flush()
    return chunks
