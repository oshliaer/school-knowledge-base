#!/usr/bin/env python3
"""Generate Telegram notification message for GitHub Actions.

Usage:
    python .github/scripts/build_tg_message.py <tag> <repo>
"""
import re
import sys
from pathlib import Path

import yaml
from slugify import slugify


def escape_md2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!\\])', r'\\\1', text)


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    tag = sys.argv[1]
    repo = sys.argv[2]

    lines = [f"📦 Новый релиз *{escape_md2(tag)}* опубликован\\!"]

    slug_to_name = {}
    for deck_yaml in Path(".").rglob("deck.yaml"):
        config = yaml.safe_load(deck_yaml.read_text(encoding="utf-8"))
        if name := config.get("name"):
            slug_to_name[slugify(name)] = name

    dist = Path("dist")
    for apkg in sorted(dist.glob("*.apkg")):
        slug = apkg.stem
        if name := slug_to_name.get(slug):
            url = f"https://github.com/{repo}/releases/download/{tag}/{slug}.apkg"
            lines.append(f'[Скачать колоду "{escape_md2(name)}"]({url})')

    print("\n".join(lines))


if __name__ == "__main__":
    main()
