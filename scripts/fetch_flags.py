#!/usr/bin/env python3
"""Download missing flags from countries.csv into the flags/ cache.
After downloading, writes cached filenames back into the CSV.

Usage:
    python scripts/fetch_flags.py
    python scripts/fetch_flags.py --limit 10   # скачать не более 10 новых флагов
    python scripts/fetch_flags.py --input "География мира/countries.csv"
"""

import argparse
import csv
import hashlib
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


FIELDNAMES = [
    "wikidata_id", "country", "capital",
    "country_flag_url", "country_flag_file",
    "capital_flag_url", "capital_flag_file",
    "capital_population", "capital_area", "capital_density", "capital_timezone",
]


def resolve_cached(url: str, cache_dir: Path) -> str | None:
    """Return cached filename (SVG or PNG) if exists, else None."""
    if not url:
        return None
    hash_ = hashlib.md5(url.encode()).hexdigest()[:12]
    for ext in ("svg", "png"):
        if (cache_dir / f"{hash_}.{ext}").exists():
            return f"{hash_}.{ext}"
    return None


def download_flag(url: str, cache_dir: Path) -> str:
    """Download flag to cache, return filename. Extension determined from Content-Type. Raises on failure."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError(f"Неподдерживаемая схема URL: {url}")
    hash_ = hashlib.md5(url.encode()).hexdigest()[:12]
    for attempt in range(5):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "school-knowledge-base/1.0 (https://github.com/oshliaer/school-knowledge-base)"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                content_type = resp.headers.get("Content-Type", "")
                ext = "png" if "png" in content_type else "svg"
                fname = f"{hash_}.{ext}"
                (cache_dir / fname).write_bytes(resp.read())
            return fname
        except Exception as e:
            if attempt == 4:
                raise RuntimeError(f"Не удалось скачать {url}: {e}") from e
            wait = (2 ** attempt) * (10 if "429" in str(e) else 2)
            print(f"    повтор через {wait}с: {e}", file=sys.stderr)
            time.sleep(wait)


def main():
    parser = argparse.ArgumentParser(description="Download missing flags, update CSV with filenames")
    parser.add_argument("--input", "-i", default="География мира/countries.csv")
    parser.add_argument("--limit", type=int, default=None, help="Максимум новых скачиваний")
    parser.add_argument("--replace-png", action="store_true",
                        help="Заменить PNG в кэше на SVG (скачать заново)")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    csv_path = repo_root / args.input
    cache_dir = csv_path.parent / "flags"
    cache_dir.mkdir(exist_ok=True)

    with csv_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    downloaded = 0
    skipped = 0
    limited = 0

    for row in rows:
        for url_field, file_field in (
            ("country_flag_url", "country_flag_file"),
            ("capital_flag_url", "capital_flag_file"),
        ):
            url = row.get(url_field, "").strip()
            if not url:
                row[file_field] = ""
                continue

            cached = resolve_cached(url, cache_dir)
            old_png_to_remove = None
            if cached:
                if args.replace_png and cached.endswith(".png"):
                    # Удаляем PNG только если лимит позволяет скачать SVG
                    if args.limit is not None and downloaded >= args.limit:
                        row[file_field] = cached
                        skipped += 1
                        continue
                    old_png_to_remove = cache_dir / cached
                else:
                    row[file_field] = cached
                    skipped += 1
                    continue

            if args.limit is not None and downloaded >= args.limit:
                row[file_field] = ""
                limited += 1
                continue

            try:
                fname = download_flag(url, cache_dir)
                # Удаляем старый PNG только после успешной загрузки
                if old_png_to_remove and old_png_to_remove.exists():
                    old_png_to_remove.unlink()
                row[file_field] = fname
                print(f"  ✓ {fname}  {url.split('/')[-1]}")
                downloaded += 1
                time.sleep(0.5)
            except RuntimeError as e:
                print(f"  ✗ {e}", file=sys.stderr)
                sys.exit(1)

    # Записываем обновлённый CSV с именами файлов
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    # Удаляем флаги, которые не упоминаются в CSV (orphan-файлы)
    referenced = {
        row[f]
        for row in rows
        for f in ("country_flag_file", "capital_flag_file")
        if row.get(f)
    }
    removed = 0
    for fpath in cache_dir.iterdir():
        if fpath.name not in referenced:
            fpath.unlink()
            print(f"  🗑 удалён orphan: {fpath.name}", file=sys.stderr)
            removed += 1

    print(f"\nСкачано: {downloaded}, в кэше: {skipped}, лимит исчерпан: {limited}, удалено orphan: {removed}", file=sys.stderr)
    print(f"CSV обновлён: {csv_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
