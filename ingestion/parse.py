"""Step 1: turn PDF / DOCX / TXT files into plain text."""
from pathlib import Path


def parse_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import fitz  # pymupdf
        with fitz.open(path) as doc:
            return "\n".join(page.get_text() for page in doc)
    if suffix == ".docx":
        return _parse_docx(path)
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"Unsupported file type: {path}")


def clean_text(text: str) -> str:
    """Normalise whitespace but keep line breaks (needed to detect headings)."""
    lines = [" ".join(line.split()) for line in text.splitlines()]
    out, blank = [], 0
    for line in lines:
        blank = blank + 1 if not line else 0
        if blank <= 1:
            out.append(line)
    return "\n".join(out).strip()


def _parse_docx(path: Path) -> str:
    """Paragraphs AND tables, in document order (tables hold e.g. minimum-wage figures)."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = docx.Document(path)
    lines: list[str] = []
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            lines.append(Paragraph(child, doc).text)
        elif child.tag.endswith("}tbl"):
            for row in Table(child, doc).rows:
                cells: list[str] = []
                for cell in row.cells:  # merged cells repeat; drop adjacent duplicates
                    text = " ".join(cell.text.split())
                    if text and (not cells or cells[-1] != text):
                        cells.append(text)
                if cells:
                    lines.append(" | ".join(cells))
    return "\n".join(lines)
