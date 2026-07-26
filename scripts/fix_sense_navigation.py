#!/usr/bin/env python3
"""Repair sense navigation labels in generated dictionary pages."""
from __future__ import annotations

from html import escape
import json
from pathlib import Path
import re
from typing import Any

from normalize_content import normalize_sense_title

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
WORDS = ROOT / "words"


def navigation_label(title: Any) -> str:
    """Return the complete normalized sense title for the navigation."""
    return normalize_sense_title(title)


def repair_navigation(html: str, senses: list[dict[str, Any]]) -> tuple[str, int]:
    """Replace each generated sense-link label using its source sense title."""
    repaired = html
    changed = 0
    for sense in senses:
        number = str(sense.get("number", "")).strip()
        label = navigation_label(sense.get("title", ""))
        if not number or not label:
            continue

        escaped_number = re.escape(number)
        pattern = re.compile(
            rf'(<a href="#sense-{escaped_number}" '
            rf'data-target="sense-{escaped_number}"><span>{escaped_number}</span>)'
            r'(.*?)'
            r'(</a>)'
        )
        replacement = rf'\1{escape(label)}\3'
        repaired, replacements = pattern.subn(replacement, repaired, count=1)
        changed += replacements
    return repaired, changed


def repair_file(content_path: Path) -> int:
    entry = json.loads(content_path.read_text(encoding="utf-8"))
    slug = str(entry.get("slug") or content_path.stem)
    page_path = WORDS / f"{slug}.html"
    if not page_path.exists():
        return 0

    original = page_path.read_text(encoding="utf-8")
    repaired, changed = repair_navigation(original, entry.get("senses") or [])
    if changed and repaired != original:
        page_path.write_text(repaired, encoding="utf-8")
    return changed


def main() -> int:
    changed = 0
    for content_path in sorted(CONTENT.glob("*.json")):
        changed += repair_file(content_path)
    print(f"Repaired {changed} sense navigation label(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
