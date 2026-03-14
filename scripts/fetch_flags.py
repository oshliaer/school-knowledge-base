#!/usr/bin/env python3
"""Download missing flags from countries.csv into the flags/ cache.
Writes flag filenames into flags.csv (separate from countries.csv).

Usage:
    python scripts/fetch_flags.py
    python scripts/fetch_flags.py --limit 10   # скачать не более 10 новых флагов
    python scripts/fetch_flags.py --input "География мира/countries.csv"
"""

import argparse
import csv
import hashlib
import io
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Self

from PIL import Image


FLAGS_FIELDNAMES = ["wikidata_id", "country_flag_file", "capital_flag_file"]


class _Oversized:
    """Sentinel: SVG есть в кэше, но превышает MAX_FLAG_SIZE — нужно скачать PNG."""
    _instance: Self | None = None

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "OVERSIZED"


OVERSIZED = _Oversized()


def resolve_cached(url: str, cache_dir: Path) -> str | None | _Oversized:
    """Return cached filename, OVERSIZED sentinel, or None.
    OVERSIZED означает: SVG есть локально, но превышает MAX_FLAG_SIZE — нужно скачать PNG."""
    if not url:
        return None
    hash_ = hashlib.md5(url.encode()).hexdigest()[:12]
    for ext in ("svg", "png", "jpg"):
        fpath = cache_dir / f"{hash_}.{ext}"
        if fpath.exists():
            if ext == "svg" and fpath.stat().st_size > MAX_FLAG_SIZE:
                return OVERSIZED
            return f"{hash_}.{ext}"
    return None


MAX_FLAG_SIZE = 100 * 1024  # 100 КБ — геральдические SVG могут весить десятки МБ
PNG_FALLBACK_WIDTH = 300    # ширина PNG-рендера при fallback (карточки отображают флаги 150px высотой)
MAX_RASTER_HEIGHT = 300     # макс. высота PNG/JPEG (2x retina; CSS показывает 150px)


def _fetch_url(url: str) -> tuple[bytes, str]:
    """Fetch URL, return (data, extension). Raises RuntimeError on bad Content-Type."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "school-knowledge-base/1.0 (https://github.com/oshliaer/school-knowledge-base)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        content_type = resp.headers.get("Content-Type", "")
        if "svg" in content_type:
            ext = "svg"
        elif "png" in content_type:
            ext = "png"
        elif "jpeg" in content_type or "jpg" in content_type:
            ext = "jpg"
        else:
            raise RuntimeError(f"Неизвестный Content-Type '{content_type}' для {url}")
        return resp.read(), ext


def _resize_raster(data: bytes, ext: str) -> bytes:
    """Resize PNG/JPEG to MAX_RASTER_HEIGHT if taller, preserving aspect ratio."""
    img = Image.open(io.BytesIO(data))
    if img.height <= MAX_RASTER_HEIGHT:
        return data
    new_w = round(img.width * MAX_RASTER_HEIGHT / img.height)
    img = img.resize((new_w, MAX_RASTER_HEIGHT), Image.LANCZOS)
    buf = io.BytesIO()
    fmt = "JPEG" if ext == "jpg" else "PNG"
    img.save(buf, format=fmt, optimize=True)
    return buf.getvalue()


def _png_fallback_url(svg_url: str) -> str:
    """Return Wikimedia PNG-render URL for a Special:FilePath SVG URL."""
    return f"{svg_url}{'&' if '?' in svg_url else '?'}width={PNG_FALLBACK_WIDTH}"


def download_flag(url: str, cache_dir: Path, key_url: str | None = None) -> str:
    """Download flag to cache, return filename. Extension determined from Content-Type.
    If SVG exceeds MAX_FLAG_SIZE, falls back to PNG render from Wikimedia. Raises on failure.
    key_url: URL для вычисления имени файла (по умолчанию = url)."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError(f"Неподдерживаемая схема URL: {url}")
    hash_ = hashlib.md5((key_url or url).encode()).hexdigest()[:12]
    for attempt in range(5):
        try:
            data, ext = _fetch_url(url)
            if ext == "svg" and len(data) > MAX_FLAG_SIZE:
                svg_kb = len(data) // 1024
                data, ext = _fetch_url(_png_fallback_url(key_url or url))
                print(f"    SVG слишком большой ({svg_kb} КБ → PNG {PNG_FALLBACK_WIDTH}px, {len(data) // 1024} КБ)", file=sys.stderr)
            if ext in ("png", "jpg"):
                data = _resize_raster(data, ext)
            fname = f"{hash_}.{ext}"
            (cache_dir / fname).write_bytes(data)
            return fname
        except Exception as e:
            if attempt == 4:
                raise RuntimeError(f"Не удалось скачать {url}: {e}") from e
            wait = (2 ** attempt) * (10 if "429" in str(e) else 2)
            print(f"    повтор через {wait}с: {e}", file=sys.stderr)
            time.sleep(wait)


def main():
    parser = argparse.ArgumentParser(description="Download missing flags, write flags.csv")
    parser.add_argument("--input", "-i", default="География мира/countries.csv")
    def positive_int(value: str) -> int:
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError("--limit должен быть > 0")
        return ivalue
    parser.add_argument("--limit", type=positive_int, default=None, help="Максимум новых скачиваний")
    parser.add_argument("--replace-png", action="store_true",
                        help="Заменить PNG в кэше на SVG (скачать заново)")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    csv_path = repo_root / args.input
    flags_path = csv_path.parent / "flags.csv"
    cache_dir = csv_path.parent / "flags"
    cache_dir.mkdir(exist_ok=True)

    with csv_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    # Загружаем существующий flags.csv чтобы сохранить кэш
    existing: dict[str, dict] = {}
    if flags_path.exists():
        with flags_path.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                existing[r["wikidata_id"]] = r

    # Строим записи флагов
    flag_rows: list[dict] = []
    downloaded = 0
    skipped = 0
    limited = 0

    for i, row in enumerate(rows, 1):
        wikidata_id = row.get("wikidata_id", "").strip()
        country = row.get("country", wikidata_id)
        flag_row = {"wikidata_id": wikidata_id, "country_flag_file": "", "capital_flag_file": ""}

        # Берём сохранённые значения из предыдущего flags.csv
        prev = existing.get(wikidata_id, {})
        flag_row["country_flag_file"] = prev.get("country_flag_file", "")
        flag_row["capital_flag_file"] = prev.get("capital_flag_file", "")

        for url_field, file_field in (
            ("country_flag_url", "country_flag_file"),
            ("capital_flag_url", "capital_flag_file"),
        ):
            url = row.get(url_field, "").strip()
            label = "флаг страны" if url_field == "country_flag_url" else "флаг столицы"
            if not url:
                flag_row[file_field] = ""
                continue

            cached = resolve_cached(url, cache_dir)
            old_png_to_remove = None

            if cached is OVERSIZED:
                # SVG уже есть локально и слишком большой — качаем PNG напрямую
                hash_ = hashlib.md5(url.encode()).hexdigest()[:12]
                svg_kb = (cache_dir / f"{hash_}.svg").stat().st_size // 1024
                print(f"  [{i}/{len(rows)}] {country}: {label} — SVG {svg_kb} КБ > {MAX_FLAG_SIZE // 1024} КБ, скачиваем PNG", file=sys.stderr)
                fetch_url = _png_fallback_url(url)
            elif cached:
                if args.replace_png and cached.endswith(".png"):
                    if args.limit is not None and downloaded >= args.limit:
                        flag_row[file_field] = cached
                        skipped += 1
                        continue
                    print(f"  [{i}/{len(rows)}] {country}: {label} — заменяем PNG→SVG", file=sys.stderr)
                    old_png_to_remove = cache_dir / cached
                else:
                    skipped += 1
                    flag_row[file_field] = cached
                    continue
                fetch_url = url
            else:
                print(f"  [{i}/{len(rows)}] {country}: {label} — скачиваем", file=sys.stderr)
                fetch_url = url

            if args.limit is not None and downloaded >= args.limit:
                limited += 1
                continue

            try:
                key_url = url if fetch_url != url else None
                fname = download_flag(fetch_url, cache_dir, key_url=key_url)
                if old_png_to_remove and old_png_to_remove.exists() and old_png_to_remove.name != fname:
                    old_png_to_remove.unlink()
                flag_row[file_field] = fname
                size_kb = (cache_dir / fname).stat().st_size // 1024
                print(f"  [{i}/{len(rows)}] {country}: {label} — ✓ {fname} ({size_kb} КБ)")
                downloaded += 1
                time.sleep(0.5)
            except RuntimeError as e:
                print(f"  [{i}/{len(rows)}] {country}: {label} — ✗ {e}", file=sys.stderr)
                sys.exit(1)

        flag_rows.append(flag_row)

    # Записываем flags.csv
    with flags_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FLAGS_FIELDNAMES)
        writer.writeheader()
        writer.writerows(flag_rows)

    # Удаляем флаги, которые не упоминаются в flags.csv (orphan-файлы)
    referenced = {
        r[f]
        for r in flag_rows
        for f in ("country_flag_file", "capital_flag_file")
        if r.get(f)
    }
    removed = 0
    for fpath in cache_dir.iterdir():
        if not fpath.is_file() or fpath.suffix not in (".svg", ".png", ".jpg"):
            continue
        if fpath.name not in referenced:
            fpath.unlink()
            print(f"  удалён orphan: {fpath.name}", file=sys.stderr)
            removed += 1

    print(f"\nСкачано: {downloaded}, в кэше: {skipped}, лимит исчерпан: {limited}, удалено orphan: {removed}", file=sys.stderr)
    print(f"flags.csv обновлён: {flags_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
