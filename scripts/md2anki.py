#!/usr/bin/env python3
"""Convert markdown card files to Anki .apkg decks.

Usage:
    python scripts/build.py                          # build all subjects
    python scripts/build.py "Вероятность и статистика 7-9"
    python scripts/build.py --output dist/
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

import genanki
import markdown
import yaml
from slugify import slugify


def make_id(name: str) -> int:
    """Generate stable integer ID from string.

    Limited to 13 hex chars (52 bits, max ~4.5e15) to stay within IEEE 754
    double precision safe integer range (2^53). Java's JSONObject parses JSON
    numbers as double, so IDs exceeding 2^53 lose precision and break lookups
    in AnkiDroid's importer.
    """
    return int(hashlib.sha1(name.encode()).hexdigest()[:13], 16)


_md = markdown.Markdown(extensions=["tables", "fenced_code", "nl2br"])


def md_to_html(text: str) -> str:
    _md.reset()
    return _md.convert(text)


def resolve_images(html: str, base_dir: Path, media_map: dict) -> str:
    """Replace local image src paths with flat filenames, collect media files."""

    def replace_src(m):
        src = m.group(1)
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        img_path = (base_dir / src).resolve()
        if not img_path.exists():
            print(f"  WARNING: image not found: {img_path}", file=sys.stderr)
            return m.group(0)
        # Hash-prefixed filename to avoid conflicts between subdeck folders
        fname = hashlib.md5(str(img_path).encode()).hexdigest()[:8] + img_path.suffix
        media_map[fname] = img_path
        return f'<img src="{fname}"'

    return re.sub(r'<img src="([^"]+)"', replace_src, html)


def parse_cards(md_file: Path, media_map: dict) -> list[dict]:
    """Parse a markdown card file into a list of card dicts.

    File format:
        ---
        type: basic          # type по умолчанию: basic | basic-reversed | cloze
        tags: [tag1, tag2]   # теги по умолчанию для всех карточек файла
        ---

        ## Card with simple id

        Answer text.

        ---

        ---
        id: my-card-id       # явный id (обязательно!)
        type: basic-reversed # переопределение типа
        tags: [extra-tag]    # дополнительные теги (добавляются к общим)
        ---

        ## Card with frontmatter

        Answer text.

        ---

        ## {{c1::Cloze}} card example

        Extra info (optional)
    """
    content = md_file.read_text(encoding="utf-8")

    # Extract YAML frontmatter
    meta = {}
    if content.startswith("---\n"):
        try:
            end = content.index("\n---\n", 4)
            meta = yaml.safe_load(content[4:end]) or {}
            content = content[end + 5:].strip()
        except ValueError:
            pass

    default_type = meta.get("type", "basic")
    default_tags = [str(t) for t in meta.get("tags", [])]

    cards = []
    # Split by card separator (--- on its own line between blank lines)
    raw_cards = re.split(r"\n\n---\n\n", content)

    for raw in raw_cards:
        raw = raw.strip()
        if not raw:
            continue

        card_type = default_type
        tags = default_tags[:]
        card_id = None

        # Проверяем, есть ли frontmatter у карточки (перед ## заголовком)
        # Формат: ---\nid: ...\ntype: ...\ntags: [...]\n---
        if raw.startswith("---\n"):
            try:
                end = raw.index("\n---\n", 4)
                card_meta = yaml.safe_load(raw[4:end]) or {}
                if "id" in card_meta:
                    card_id = card_meta["id"]
                if "type" in card_meta:
                    card_type = card_meta["type"]
                if "tags" in card_meta:
                    # Теги карточки дополняют теги файла
                    card_tags = [str(t) for t in card_meta["tags"]]
                    tags = tags + card_tags if tags else card_tags
                raw = raw[end + 5:].strip()
            except ValueError:
                pass
        else:
            # Проверяем, есть ли id: в начале карточки (перед ## заголовком)
            id_match = re.match(r"^id:\s*(\S+)\s*\n", raw)
            if id_match:
                card_id = id_match.group(1)
                raw = raw[id_match.end():].strip()

        # Auto-detect cloze by {{c1::...}} syntax
        if re.search(r"\{\{c\d+::", raw):
            card_type = "cloze"

        if card_type == "cloze":
            html = resolve_images(md_to_html(raw), md_file.parent, media_map)
            cards.append({"type": "cloze", "text": html, "extra": "", "tags": tags, "id": card_id})
        else:
            # First paragraph (usually ## Heading) = front, rest = back
            parts = re.split(r"\n\n", raw, maxsplit=1)
            front_md = re.sub(r"^#{1,6}\s+", "", parts[0].strip())
            back_md = parts[1].strip() if len(parts) > 1 else ""

            front_html = resolve_images(md_to_html(front_md), md_file.parent, media_map)
            back_html = resolve_images(md_to_html(back_md), md_file.parent, media_map)

            cards.append({
                "type": card_type,
                "front": front_html,
                "back": back_html,
                "tags": tags,
                "id": card_id,
            })

    return cards


def build_models(deck_name: str) -> dict:
    """Create genanki models with stable IDs scoped to this deck."""
    # CSS для базового оформления
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600&display=swap');
    .card {
        font-family: 'Open Sans', Arial, sans-serif;
        font-size: 20px;
        padding: 20px;
    }
    hr {
        border: none;
        border-top: 1px solid #ccc;
        margin: 15px 0;
    }
    """
    return {
        "basic": genanki.Model(
            make_id(f"{deck_name}:model:basic"),
            "Basic",
            fields=[{"name": "Front"}, {"name": "Back"}],
            templates=[{
                "name": "Card 1",
                "qfmt": "{{Front}}",
                "afmt": "{{FrontSide}}<hr id=answer>{{Back}}",
            }],
            css=css,
        ),
        "basic-reversed": genanki.Model(
            make_id(f"{deck_name}:model:basic-reversed"),
            "Basic (and reversed card)",
            fields=[{"name": "Front"}, {"name": "Back"}],
            templates=[
                {
                    "name": "Card 1",
                    "qfmt": "{{Front}}",
                    "afmt": "{{FrontSide}}<hr id=answer>{{Back}}",
                },
                {
                    "name": "Card 2",
                    "qfmt": "{{Back}}",
                    "afmt": "{{BackSide}}<hr id=answer>{{Front}}",
                },
            ],
            css=css,
        ),
        "cloze": genanki.Model(
            make_id(f"{deck_name}:model:cloze"),
            "Cloze",
            fields=[{"name": "Text"}, {"name": "Extra"}],
            templates=[{
                "name": "Cloze",
                "qfmt": "{{cloze:Text}}",
                "afmt": "{{cloze:Text}}<br>{{Extra}}",
            }],
            model_type=genanki.Model.CLOZE,
            css=css,
        ),
    }


def build_subject(subject_dir: Path, output_dir: Path) -> Path:
    """Build a single .apkg from a subject directory."""
    deck_config_path = subject_dir / "deck.yaml"
    if not deck_config_path.exists():
        raise FileNotFoundError(f"deck.yaml not found in {subject_dir}")

    config = yaml.safe_load(deck_config_path.read_text(encoding="utf-8"))
    deck_name = config["name"]
    deck_id = config.get("id") or make_id(deck_name)

    models = build_models(deck_name)

    top_deck = genanki.Deck(deck_id, deck_name)
    all_decks = [top_deck]
    media_map: dict[str, Path] = {}

    decks_dir = subject_dir / "decks"
    if not decks_dir.exists():
        raise FileNotFoundError(f"decks/ directory not found in {subject_dir}")

    # Поддерживаем оба формата:
    # 1. Файлы напрямую в decks/ (decks/01-тема.md)
    # 2. Папки с карточками (decks/01-тема/cards.md)
    md_files = sorted(decks_dir.glob("*.md"))
    subdeck_dirs = sorted(d for d in decks_dir.iterdir() if d.is_dir())

    if md_files and subdeck_dirs:
        print("  WARNING: смешанный формат (файлы и папки). Используем файлы.", file=sys.stderr)

    total_cards = 0

    if md_files:
        # Формат: файлы напрямую в decks/
        for md_file in md_files:
            print(f"  {md_file.relative_to(subject_dir)}")
            try:
                cards = parse_cards(md_file, media_map)
            except Exception as e:
                print(f"  ERROR in {md_file}: {e}", file=sys.stderr)
                continue

            for card in cards:
                ctype = card["type"]
                model = models.get(ctype, models["basic"])
                tags = card.get("tags", [])

                # Требуем явный id для каждой карточки
                if not card.get("id"):
                    front_preview = card.get("front", card.get("text", "???"))[:60].replace("\n", " ")
                    print(f"  WARNING: пропущена карточка без id: {front_preview}...", file=sys.stderr)
                    continue

                if ctype == "cloze":
                    note = genanki.Note(
                        model=model,
                        fields=[card["text"], card.get("extra", "")],
                        tags=tags,
                        guid=str(card["id"]),
                    )
                else:
                    note = genanki.Note(
                        model=model,
                        fields=[card["front"], card["back"]],
                        tags=tags,
                        guid=str(card["id"]),
                    )
                top_deck.add_note(note)
                total_cards += 1
    else:
        # Формат: папки с карточками (старый стиль)
        for subdeck_dir in subdeck_dirs:
            subdeck_name = f"{deck_name}::{subdeck_dir.name}"
            subdeck = genanki.Deck(make_id(subdeck_name), subdeck_name)
            all_decks.append(subdeck)

            for md_file in sorted(subdeck_dir.glob("*.md")):
                print(f"  {md_file.relative_to(subject_dir)}")
                try:
                    cards = parse_cards(md_file, media_map)
                except Exception as e:
                    print(f"  ERROR in {md_file}: {e}", file=sys.stderr)
                    continue

                for card in cards:
                    ctype = card["type"]
                    model = models.get(ctype, models["basic"])
                    tags = card.get("tags", [])

                    # Требуем явный id для каждой карточки
                    if not card.get("id"):
                        front_preview = card.get("front", card.get("text", "???"))[:60].replace("\n", " ")
                        print(f"  WARNING: пропущена карточка без id: {front_preview}...", file=sys.stderr)
                        continue

                    if ctype == "cloze":
                        note = genanki.Note(
                            model=model,
                            fields=[card["text"], card.get("extra", "")],
                            tags=tags,
                            guid=str(card["id"]),
                        )
                    else:
                        note = genanki.Note(
                            model=model,
                            fields=[card["front"], card["back"]],
                            tags=tags,
                            guid=str(card["id"]),
                        )
                    subdeck.add_note(note)
                    total_cards += 1

    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = slugify(deck_name)
    out_path = output_dir / f"{safe_name}.apkg"

    package = genanki.Package(all_decks)
    package.media_files = [str(p) for p in media_map.values()]
    package.write_to_file(str(out_path))

    print(f"  -> {out_path.name} ({total_cards} cards, {len(media_map)} media files)")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Build Anki decks from markdown")
    parser.add_argument("subjects", nargs="*", help="Subject directories (default: all)")
    parser.add_argument("--output", "-o", default="dist", help="Output directory")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    output_dir = repo_root / args.output

    if args.subjects:
        subject_dirs = [repo_root / s for s in args.subjects]
    else:
        subject_dirs = sorted(
            p.parent for p in repo_root.rglob("deck.yaml") if p.parent != repo_root
        )

    if not subject_dirs:
        print("No subjects found (no deck.yaml files).", file=sys.stderr)
        sys.exit(1)

    for subject_dir in subject_dirs:
        print(f"\nBuilding: {subject_dir.name}")
        try:
            build_subject(subject_dir, output_dir)
        except Exception as e:
            print(f"FAILED: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
