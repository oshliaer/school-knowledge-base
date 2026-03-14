#!/usr/bin/env python3
"""Convert countries CSV to Anki .apkg deck.

Reads countries.csv with columns:
    country, capital, country_flag_file, capital_flag_file (и другие)

Generates one card template per note:
    Card 1: Country + flag → Capital

Usage:
    python scripts/csv2anki.py
    python scripts/csv2anki.py --input "География мира/countries.csv"
    python scripts/csv2anki.py --output dist/
"""

import argparse
import csv
import hashlib
import sys
import time
import urllib.request
from pathlib import Path

import genanki
import yaml
from slugify import slugify


def make_id(name: str) -> int:
    return int(hashlib.sha1(name.encode()).hexdigest()[:13], 16)


def resolve_flag(fname: str, cache_dir: Path) -> str | None:
    """Return flag filename if exists in cache, else None."""
    if not fname:
        return None
    return fname if (cache_dir / fname).exists() else None


# Шаблон: Страна + флаг → Столица
# Поля CountryFlag и CapitalFlag содержат готовый HTML: <img src="..."> или пусто
TMPL_COUNTRY_TO_CAPITAL = {
    "name": "Страна → Столица",
    "qfmt": """
<div class="flag">{{CountryFlag}}</div>
<h1>{{Country}}</h1>
""",
    "afmt": """
<div class="flag">{{CountryFlag}}</div>
<h1>{{Country}}</h1>
<div class="flag">{{CapitalFlag}}</div>
<h2>{{Capital}}</h2>
<div class="facts">
  {{#CapitalPopulation}}<span>👥 {{CapitalPopulation}}</span>{{/CapitalPopulation}}
  {{#CapitalArea}}<span>🗺 {{CapitalArea}} км²</span>{{/CapitalArea}}
  {{#CapitalDensity}}<span>📐 {{CapitalDensity}}/км²</span>{{/CapitalDensity}}
  {{#CapitalTimezone}}<span>🕐 {{CapitalTimezone}}</span>{{/CapitalTimezone}}
</div>
""",
}


def build_model(deck_name: str, subject_dir: Path) -> genanki.Model:
    css_file = subject_dir / "styles.css"
    css = css_file.read_text(encoding="utf-8") if css_file.exists() else ""
    return genanki.Model(
        make_id(f"{deck_name}:model:geography-v1"),
        "Geography: Country-Capital",
        fields=[
            {"name": "Country"},
            {"name": "Capital"},
            {"name": "CountryFlag"},
            {"name": "CapitalFlag"},
            {"name": "CapitalPopulation"},
            {"name": "CapitalArea"},
            {"name": "CapitalDensity"},
            {"name": "CapitalTimezone"},
        ],
        templates=[TMPL_COUNTRY_TO_CAPITAL],
        css=css,
    )


def build_deck(csv_path: Path, output_dir: Path, deck_config: dict, args=None) -> Path:
    deck_name = deck_config["name"]
    deck_id = deck_config.get("id") or make_id(deck_name)

    cache_dir = csv_path.parent / "flags"
    cache_dir.mkdir(exist_ok=True)

    model = build_model(deck_name, csv_path.parent)
    deck = genanki.Deck(deck_id, deck_name)
    media_files: list[str] = []

    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Подгружаем flags.csv и мёрджим по wikidata_id
    flags_path = csv_path.parent / "flags.csv"
    if flags_path.exists():
        with flags_path.open(encoding="utf-8", newline="") as f:
            flags_index = {r["wikidata_id"]: r for r in csv.DictReader(f)}
        for row in rows:
            flag_data = flags_index.get(row.get("wikidata_id", ""), {})
            row["country_flag_file"] = flag_data.get("country_flag_file", "")
            row["capital_flag_file"] = flag_data.get("capital_flag_file", "")
    else:
        for row in rows:
            row.setdefault("country_flag_file", "")
            row.setdefault("capital_flag_file", "")

    print(f"  Загружено {len(rows)} стран из {csv_path.name}")

    for i, row in enumerate(rows, 1):
        country = row.get("country", "").strip()
        capital = row.get("capital", "").strip()
        if not country or not capital:
            continue

        print(f"  [{i}/{len(rows)}] {country} / {capital}", end="")

        country_flag_file = resolve_flag(row.get("country_flag_file", "").strip(), cache_dir)
        capital_flag_file = resolve_flag(row.get("capital_flag_file", "").strip(), cache_dir)

        if country_flag_file:
            media_files.append(str(cache_dir / country_flag_file))
        if capital_flag_file:
            media_files.append(str(cache_dir / capital_flag_file))

        print(f" {'🏳' if country_flag_file else '·'}{'' if capital_flag_file else '·'}")

        # GUID = Wikidata ID страны — стабилен даже при смене столицы
        wikidata_id = row.get("wikidata_id", "").strip()
        guid = wikidata_id if wikidata_id else make_id(f"geography:{country}")

        def img(fname: str | None) -> str:
            if fname:
                return f'<img src="{fname}">'
            return '<div class="no-flag">Флаг не предусмотрен</div>'

        def fmt_short(v: str) -> str:
            """Format large numbers as 2.0M / 381K / 4.9K."""
            try:
                n = float(v)
                if n >= 1_000_000:
                    return f"{n / 1_000_000:.1f}M"
                if n >= 1_000:
                    return f"{n / 1_000:.1f}K"
                return str(int(n))
            except ValueError:
                return v

        population = row.get("capital_population", "").strip()
        area = row.get("capital_area", "").strip()
        density = row.get("capital_density", "").strip()
        timezone = row.get("capital_timezone", "").strip()

        note = genanki.Note(
            model=model,
            fields=[
                country,
                capital,
                img(country_flag_file),
                img(capital_flag_file),
                fmt_short(population) if population else "",
                fmt_short(area) if area else "",
                fmt_short(density) if density else "",
                timezone,
            ],
            tags=[],
            guid=guid,
        )
        deck.add_note(note)

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = slugify(deck_name)
    out_path = output_dir / f"{safe_name}.apkg"

    package = genanki.Package([deck])
    package.media_files = list(set(media_files))
    package.write_to_file(str(out_path))

    print(f"  -> {out_path.name} ({len(deck.notes)} карточек, {len(set(media_files))} флагов)")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Build Anki geography deck from CSV")
    parser.add_argument("--input", "-i", default="География мира/countries.csv")
    parser.add_argument("--output", "-o", default="dist")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    csv_path = repo_root / args.input
    output_dir = repo_root / args.output

    if not csv_path.exists():
        print(f"ERROR: не найден {csv_path}", file=sys.stderr)
        print("Сначала запустите: python scripts/fetch_countries.py", file=sys.stderr)
        sys.exit(1)

    deck_yaml_path = csv_path.parent / "deck.yaml"
    if not deck_yaml_path.exists():
        print(f"ERROR: не найден {deck_yaml_path}", file=sys.stderr)
        sys.exit(1)

    deck_config = yaml.safe_load(deck_yaml_path.read_text(encoding="utf-8"))

    print(f"\nBuilding: {deck_config['name']}")
    build_deck(csv_path, output_dir, deck_config, args)


if __name__ == "__main__":
    main()
