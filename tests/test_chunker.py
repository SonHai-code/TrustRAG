from pathlib import Path

from ingestion.chunker import chunk_document
from ingestion.parse import clean_text

SAMPLE = Path("data/sample/luat_mau.txt")


def _chunks():
    return chunk_document("luat_mau", clean_text(SAMPLE.read_text(encoding="utf-8")))


def test_one_chunk_per_article():
    chunks = _chunks()
    assert [c.article for c in chunks] == ["1", "2", "3", "4"]


def test_metadata_chapter_and_title():
    c = _chunks()[2]
    assert c.article == "3"
    assert c.article_title == "Thời hạn lưu trữ"
    assert "LƯU TRỮ TÀI LIỆU" in c.chapter


def test_long_article_is_split_by_clause():
    body = "\n".join(f"{i}. " + "nội dung " * 30 for i in range(1, 9))
    text = f"Chương I\nCHUNG\nĐiều 1. Dài\n{body}"
    chunks = chunk_document("x", text, max_chars=600)
    assert len(chunks) > 1
    assert all(len(c.text) <= 700 for c in chunks)
    assert all(c.article == "1" for c in chunks)


def test_point_ids_are_unique_for_split_articles():
    """Regression: split chunks of one Article used to share an ID and overwrite each other."""
    body = "\n".join(f"{i}. " + "nội dung " * 30 for i in range(1, 9))
    chunks = chunk_document("x", f"Chương I\nCHUNG\nĐiều 1. Dài\n{body}", max_chars=600)
    ids = {(c.doc_name, c.article, c.clause, c.part) for c in chunks}
    assert len(chunks) > 1 and len(ids) == len(chunks)
