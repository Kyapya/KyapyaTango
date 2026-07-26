#!/usr/bin/env python3
"""Normalize generated dictionary JSON before building the static site."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BRACKET_PAIRS = (("【", "】"), ("[", "]"))


def _repair_bracket_pair(value: str, opening: str, closing: str) -> str:
    """Repair only an unmatched leading label bracket or surplus trailing closer."""
    if not value:
        return value

    if value.startswith(opening):
        if closing not in value:
            return value + closing

        # A title such as "【従属接続詞】～だけれども】" already has a
        # complete label. Remove only surplus closing brackets at the very end.
        while value.endswith(closing) and value.count(closing) > value.count(opening):
            value = value[:-len(closing)].rstrip()
        return value

    if opening not in value and closing in value:
        value = opening + value
        while value.endswith(closing) and value.count(closing) > value.count(opening):
            value = value[:-len(closing)].rstrip()
        return value

    return value


def normalize_sense_title(title: Any) -> str:
    """Balance a leading sense-label bracket without changing the title text."""
    value = str(title or "").strip()
    for opening, closing in BRACKET_PAIRS:
        value = _repair_bracket_pair(value, opening, closing)
    return value


def normalize_entry(entry: dict[str, Any]) -> bool:
    changed = False
    for sense in entry.get("senses") or []:
        old_title = sense.get("title", "")
        new_title = normalize_sense_title(old_title)
        if new_title != old_title:
            sense["title"] = new_title
            changed = True
    return changed


def normalize_file(path: Path, dry_run: bool = False) -> bool:
    entry = json.loads(path.read_text(encoding="utf-8"))
    if not normalize_entry(entry):
        return False
    if not dry_run:
        rendered = json.dumps(entry, ensure_ascii=False, indent=2) + "\n"
        path.write_text(rendered, encoding="utf-8")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--content", type=Path, default=Path("content"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    changed = 0
    for path in sorted(args.content.glob("*.json")):
        if normalize_file(path, args.dry_run):
            changed += 1
            action = "Would normalize" if args.dry_run else "Normalized"
            print(f"{action} {path}")
    print(f"Normalized {changed} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
