#!/usr/bin/env python3
"""Fetch countries and capitals from Wikidata SPARQL, save to countries.csv.

Usage:
    python scripts/fetch_countries.py
    python scripts/fetch_countries.py --output "География мира/countries.csv"
    python scripts/fetch_countries.py --limit 10   # для тестирования
"""

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yaml


SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# Запрос: страны (независимые государства) + столицы + флаги
# - P297 = ISO 3166-1 код (только реальные государства)
# - P576 = дата роспуска (исключаем исторические государства)
# - P36 = столица
# - P41 = флаг страны / флаг столицы
# - rdfs:label на русском
SPARQL_QUERY = """
SELECT DISTINCT
  ?country
  ?countryLabel
  ?capitalLabel
  ?countryFlag
  ?capitalFlag
  ?capitalPopulation
  ?capitalPopDate
  ?capitalArea
  ?capitalAreaUnit
  ?tzLabel
WHERE {
  # Только страны с ISO 3166-1 кодом (реальные государства)
  ?country wdt:P297 ?isoCode .
  # Исключаем исторические государства (имеющие дату роспуска P576)
  FILTER NOT EXISTS { ?country wdt:P576 [] }
  ?country wdt:P36 ?capital .

  OPTIONAL { ?country wdt:P41 ?countryFlag . }
  OPTIONAL { ?capital wdt:P41 ?capitalFlag . }
  OPTIONAL {
    ?capital p:P2046 ?areaSt .
    ?areaSt psv:P2046 ?areaVal .
    ?areaVal wikibase:quantityAmount ?capitalArea .
    ?areaVal wikibase:quantityUnit ?capitalAreaUnit .
  }
  OPTIONAL { ?capital wdt:P421 ?tz . }
  # Население с датой — берём последнее по дате в Python
  OPTIONAL {
    ?capital p:P1082 ?popSt .
    ?popSt ps:P1082 ?capitalPopulation .
    OPTIONAL { ?popSt pq:P585 ?capitalPopDate . }
  }

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "ru,en" .
  }
}
ORDER BY ?countryLabel
"""


def fetch_wikidata(query: str, limit: int | None = None) -> list[dict]:
    if limit:
        query = query.rstrip() + f"\nLIMIT {limit}"

    params = urllib.parse.urlencode({
        "query": query,
        "format": "json",
    })
    url = f"{SPARQL_ENDPOINT}?{params}"

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/sparql-results+json",
            "User-Agent": "school-knowledge-base/1.0 (https://github.com/oshliaer/school-knowledge-base)",
        },
    )

    print("Запрашиваем данные из Wikidata...", file=sys.stderr)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                break
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  Попытка {attempt + 1} неудачна: {e}. Повтор...", file=sys.stderr)
            time.sleep(5)

    bindings = data["results"]["bindings"]
    rows = []
    for b in bindings:
        # Wikidata ID страны (Q-номер) — стабильный идентификатор
        country_uri = b.get("country", {}).get("value", "")
        wikidata_id = country_uri.rsplit("/", 1)[-1] if country_uri else ""

        # Флаги приходят как прямые URL на Wikimedia Commons, только меняем http→https
        country_flag = b.get("countryFlag", {}).get("value", "").replace("http://", "https://")
        capital_flag = b.get("capitalFlag", {}).get("value", "").replace("http://", "https://")

        population = b.get("capitalPopulation", {}).get("value", "")
        pop_date = b.get("capitalPopDate", {}).get("value", "")
        area_raw = b.get("capitalArea", {}).get("value", "")
        area_unit = b.get("capitalAreaUnit", {}).get("value", "")
        # Q25343 = m², Q712226 = km²; конвертируем всё в км²
        try:
            area_val = float(area_raw) if area_raw else None
            if area_val is not None and "Q25343" in area_unit:
                area_val = area_val / 1_000_000
            area = str(round(area_val, 2)) if area_val is not None else ""
        except ValueError:
            area = ""
        try:
            density = round(float(population) / float(area)) if population and area else ""
        except (ValueError, ZeroDivisionError):
            density = ""

        timezone = b.get("tzLabel", {}).get("value", "")

        rows.append({
            "wikidata_id":        wikidata_id,
            "country":            b.get("countryLabel", {}).get("value", ""),
            "capital":            b.get("capitalLabel", {}).get("value", ""),
            "country_flag_url":   country_flag,
            "capital_flag_url":   capital_flag,
            "capital_population": population,
            "capital_pop_date":   pop_date,
            "capital_area":       area,
            "capital_density":    density,
            "capital_timezone":   timezone,
        })
    return rows


def deduplicate(rows: list[dict]) -> list[dict]:
    """Оставить по одной записи на страну.

    При нескольких строках (разные исторические значения населения)
    берём значение с наиболее поздней датой квалификатора P585.
    Записи без даты используются только если датированных нет.
    """
    best: dict[str, dict] = {}
    for row in rows:
        key = row["wikidata_id"]
        if not key:
            continue
        if key not in best:
            best[key] = row
        else:
            cur_date = best[key].get("capital_pop_date", "")
            new_date = row.get("capital_pop_date", "")
            # Обновляем если новая дата позже (ISO строки сравниваются лексикографически)
            if new_date > cur_date:
                best[key]["capital_population"] = row["capital_population"]
                best[key]["capital_pop_date"] = new_date
                best[key]["capital_density"] = row["capital_density"]
    return list(best.values())


def main():
    parser = argparse.ArgumentParser(description="Fetch countries from Wikidata")
    parser.add_argument("--output", "-o", default="География мира/countries.csv")
    def positive_int(value: str) -> int:
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError("--limit должен быть > 0")
        return ivalue
    parser.add_argument("--limit", type=positive_int, default=None, help="Ограничить число записей (для теста)")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    output_path = repo_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = fetch_wikidata(SPARQL_QUERY, limit=args.limit)
    rows = deduplicate(rows)

    # Фильтруем строки без страны или столицы
    rows = [r for r in rows if r["country"] and r["capital"]]

    # Применяем ручные исправления из overrides.yaml
    overrides_path = output_path.parent / "overrides.yaml"
    if overrides_path.exists():
        overrides = yaml.safe_load(overrides_path.read_text(encoding="utf-8")) or {}
        for row in rows:
            patch = overrides.get(row["wikidata_id"])
            if patch:
                row.update(patch)
                print(f"  override: {row['country']} ({row['wikidata_id']})", file=sys.stderr)

    fieldnames = ["wikidata_id", "country", "capital", "country_flag_url", "capital_flag_url", "capital_population", "capital_area", "capital_density", "capital_timezone"]
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Сохранено {len(rows)} стран → {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
