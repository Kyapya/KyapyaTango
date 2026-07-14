#!/usr/bin/env python3
"""Apply final HTML fixes that must be present in every generated word page."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORDS = ROOT / "words"
ASSET_VERSION = "20260714-3"


def finalize_page(html: str) -> str:
    """Keep usage notes visible and force browsers to load the latest study-mode JS."""
    html = html.replace('class="notes ja"', 'class="notes"')
    html = html.replace(
        'src="../assets/site.js"',
        f'src="../assets/site.js?v={ASSET_VERSION}"',
    )
    return html


def main() -> None:
    changed = 0
    for path in sorted(WORDS.glob("*.html")):
        original = path.read_text(encoding="utf-8")
        updated = finalize_page(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    print(f"Finalized {changed} word page(s).")


if __name__ == "__main__":
    main()
