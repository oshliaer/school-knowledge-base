#!/usr/bin/env python3
"""Generate Telegram notification message for GitHub Actions.

Usage:
    python scripts/build_tg_message.py <tag> <repo>
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
    tag = sys.argv[1]
    repo = sys.argv[2]

    lines = [f"📦 Новый релиз *{escape_md2(tag)}* опубликован\\!"]

    dist = Path("dist")
    for apkg in sorted(dist.glob("*.apkg")):
        slug = apkg.stem
        # Find matching deck by slugified name
        for deck_yaml in Path(".").rglob("deck.yaml"):
            config = yaml.safe_load(deck_yaml.read_text(encoding="utf-8"))
            name = config.get("name", "")
            if slugify(name) == slug:
                url = f"https://github.com/{repo}/releases/latest/download/{slug}.apkg"
                lines.append(f'[Скачать колоду "{escape_md2(name)}"]({url})')
                break

    print("\n".join(lines))


if __name__ == "__main__":
    main()
