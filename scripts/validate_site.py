#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path

class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self.ids: set[str] = set(); self.duplicates: set[str] = set()
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            if values["id"] in self.ids: self.duplicates.add(values["id"])
            self.ids.add(values["id"])

def main() -> int:
    root = Path("."); errors: list[str] = []; content = sorted((root / "content").glob("*.json"))
    if not content: errors.append("content/*.json is empty")
    slugs: set[str] = set()
    for path in content:
        try: data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc: errors.append(f"{path}: invalid JSON: {exc}"); continue
        slug = data.get("slug")
        if not slug or slug in slugs: errors.append(f"{path}: missing or duplicate slug {slug!r}")
        slugs.add(slug)
        if not data.get("senses"): errors.append(f"{path}: no senses")
        page = root / "words" / f"{slug}.html"
        if not page.exists(): errors.append(f"missing generated page {page}")
    for page in [root / "index.html", *sorted((root / "words").glob("*.html"))]:
        if not page.exists(): errors.append(f"missing {page}"); continue
        parser = Parser(); parser.feed(page.read_text(encoding="utf-8"))
        if parser.duplicates: errors.append(f"{page}: duplicate ids {sorted(parser.duplicates)}")
    try:
        index = json.loads((root / "data/search-index.json").read_text(encoding="utf-8"))
        if len(index) != len(slugs): errors.append("search index count does not match content count")
    except Exception as exc: errors.append(f"invalid search index: {exc}")
    if errors:
        print("\n".join(f"ERROR: {x}" for x in errors), file=sys.stderr); return 1
    print(f"Validated {len(slugs)} words"); return 0

if __name__ == "__main__": raise SystemExit(main())
