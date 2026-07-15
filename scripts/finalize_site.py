#!/usr/bin/env python3
"""Apply final HTML fixes that must be present in every generated word page."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORDS = ROOT / "words"
ASSET_VERSION = "20260715-2"

MOBILE_TOOLBAR_STYLE = """<style id="mobile-toolbar-style">
.mobile-toolbar-toggle{display:none}
@media(max-width:720px){
  .word-toolbar.mobile-tools-ready{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:7px 12px;max-height:calc(100vh - 78px);overflow-y:auto;transition:transform .2s ease,box-shadow .2s ease}
  .word-toolbar.mobile-tools-ready.mobile-toolbar-hidden{transform:translateY(calc(-100% - 2px))}
  .word-toolbar.mobile-tools-ready .mobile-toolbar-toggle{display:flex;grid-column:1/-1;width:100%;min-height:44px;align-items:center;justify-content:space-between;font-weight:850;letter-spacing:.02em}
  .word-toolbar.mobile-tools-ready:not(.mobile-tools-open)>:not(.mobile-toolbar-toggle){display:none!important}
  .word-toolbar.mobile-tools-ready.mobile-tools-open{box-shadow:0 14px 30px rgba(20,40,75,.16)}
  .word-toolbar.mobile-tools-ready.mobile-tools-open .search-box,.word-toolbar.mobile-tools-ready.mobile-tools-open #freqFilter{grid-column:1/-1;width:100%}
  .word-toolbar.mobile-tools-ready.mobile-tools-open>button:not(.mobile-toolbar-toggle){width:100%;min-height:44px}
  .word-toolbar.mobile-tools-ready.mobile-tools-open #collapseAll{grid-column:1/-1}
  .mobile-toolbar-chevron{font-size:18px;line-height:1;color:var(--primary)}
}
@media(prefers-reduced-motion:reduce){.word-toolbar.mobile-tools-ready{transition:none}}
</style>"""

STYLE_RE = re.compile(
    r"\s*<style id=\"mobile-toolbar-style\">.*?</style>",
    re.DOTALL,
)
SCRIPT_RE = re.compile(r'src="\.\./assets/site\.js(?:\?v=[^"]+)?"')


def finalize_page(html: str) -> str:
    """Finalize study-mode visibility, mobile toolbar layout and asset caching."""
    html = html.replace('class="notes ja"', 'class="notes"')
    html = SCRIPT_RE.sub(
        f'src="../assets/site.js?v={ASSET_VERSION}"',
        html,
    )
    if STYLE_RE.search(html):
        html = STYLE_RE.sub("\n" + MOBILE_TOOLBAR_STYLE, html)
    else:
        html = html.replace("</head>", MOBILE_TOOLBAR_STYLE + "\n</head>")
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
