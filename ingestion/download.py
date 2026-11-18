"""Optional: download documents listed in data/sources.csv into data/raw."""
import csv
from pathlib import Path

import requests


def download_all(csv_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with csv_path.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("name") and not r["name"].startswith("#")]
    for row in rows:
        url = row["url"]
        ext = Path(url.split("?")[0]).suffix or ".pdf"
        target = out_dir / f"{row['name']}{ext}"
        if target.exists():
            print(f"skip (exists): {target.name}")
            continue
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        target.write_bytes(resp.content)
        print(f"downloaded: {target.name}")
