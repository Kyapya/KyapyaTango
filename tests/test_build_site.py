from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_site import word_page


def entry(core: list[dict] | None = None) -> dict:
    data = {
        "word": "approximately",
        "slug": "approximately",
        "ipa": "/əˈprɑːksəmətli/",
        "lead": "約、およそ",
        "updated": "2026-08-12",
        "notion_url": "https://notion.so/approximately",
        "pronunciation": [],
        "etymology": [],
        "formation": [],
        "sources": [],
        "senses": [
            {
                "number": 1,
                "title": "【副詞】約、およそ",
                "frequency": 8,
                "register": [],
                "definition": "数値が厳密には一致しないことを表す。",
                "patterns": [],
                "collocations": [],
                "notes": [],
                "synonyms": [],
                "antonyms": [],
            }
        ],
    }
    if core is not None:
        data["core"] = core
    return data


class BuildSiteTests(unittest.TestCase):
    def test_omits_core_image_navigation_and_panel_when_core_is_missing(self) -> None:
        word = entry()
        result = word_page(word, [word])

        self.assertNotIn('href="#core"', result)
        self.assertNotIn('id="core"', result)
        self.assertNotIn("コアイメージ", result)

    def test_omits_core_image_navigation_and_panel_when_core_is_empty(self) -> None:
        word = entry([])
        result = word_page(word, [word])

        self.assertNotIn('href="#core"', result)
        self.assertNotIn('id="core"', result)
        self.assertNotIn("コアイメージ", result)

    def test_renders_core_image_navigation_and_panel_when_core_has_content(self) -> None:
        word = entry(
            [{"label": "近さ", "description": "厳密値の近くにある。"}]
        )
        result = word_page(word, [word])

        self.assertIn('<a href="#core">コアイメージ</a>', result)
        self.assertIn('id="core"', result)
        self.assertIn("厳密値の近くにある。", result)


if __name__ == "__main__":
    unittest.main()
