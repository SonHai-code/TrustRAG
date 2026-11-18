"""Command line entry point.

  python -m ingestion.cli download
  python -m ingestion.cli ingest --input data/raw
  python -m ingestion.cli search "thời hạn lưu trữ tài liệu"
"""
import argparse
import json
from pathlib import Path

from ingestion.chunker import chunk_document
from ingestion.parse import clean_text, parse_file

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}


def cmd_ingest(input_dir: Path, dry_run: bool, recreate: bool = False) -> None:
    files = sorted(p for p in input_dir.rglob("*") if p.suffix.lower() in SUPPORTED)
    if not files:
        print(f"No documents found in {input_dir}")
        return
    all_chunks = []
    for path in files:
        text = clean_text(parse_file(path))
        chunks = chunk_document(path.stem, text)
        print(f"{path.name}: {len(chunks)} chunks")
        all_chunks.extend(chunks)

    out = Path("data/processed/chunks.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c.as_payload(), ensure_ascii=False) + "\n")
    print(f"Saved {len(all_chunks)} chunks -> {out}")

    if dry_run:
        print("Dry run: skipped embedding/indexing.")
        return
    from ingestion.index import upsert_chunks
    n = upsert_chunks(all_chunks, recreate=recreate)
    print(f"Indexed {n} chunks into Qdrant.")


def cmd_search(query: str, top_k: int) -> None:
    from ingestion.index import search
    for i, hit in enumerate(search(query, top_k), 1):
        p = hit.payload
        print(f"\n#{i} score={hit.score:.3f}  {p['doc_name']} | Điều {p['article']} {p['article_title']}")
        print(p["text"][:300])


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("download")
    p_ing = sub.add_parser("ingest")
    p_ing.add_argument("--input", default="data/raw")
    p_ing.add_argument("--dry-run", action="store_true", help="parse+chunk only")
    p_ing.add_argument("--recreate", action="store_true", help="drop and rebuild the Qdrant collection first")
    p_s = sub.add_parser("search")
    p_s.add_argument("query")
    p_s.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    if args.cmd == "download":
        from ingestion.download import download_all
        download_all(Path("data/sources.csv"), Path("data/raw"))
    elif args.cmd == "ingest":
        cmd_ingest(Path(args.input), args.dry_run, args.recreate)
    else:
        cmd_search(args.query, args.top_k)


if __name__ == "__main__":
    main()
