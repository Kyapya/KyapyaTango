from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_site import relation_cards, word_page


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
    def test_relation_frequencies_are_sense_specific_for_both_groups(self) -> None:
        word = entry()
        base = {"word": "near", "definition": "近い", "difference": "違い", "example": "Example.", "translation": "訳"}
        word["senses"][0]["synonyms"] = [{**base, "frequency": 3}]
        word["senses"][0]["antonyms"] = [{**base, "word": "exact", "frequency": 7}]
        result = word_page(word, [word])
        cards = result.split('<article class="relation-card searchable">')[1:]
        self.assertEqual(len(cards), 2)
        for card, score in zip(cards, (3, 7)):
            card = card.split('</article>', 1)[0]
            self.assertIn(f'この語義の頻度 {score}/10', card)
            self.assertNotIn('頻度 8/10', card)
            self.assertIn('class="frequency relation-frequency"', card)
            self.assertIn('<p class="ja"><b>訳</b>', card)

    def test_missing_or_invalid_relation_frequency_does_not_invent_score(self) -> None:
        base = {"word": "near", "difference": "違い", "example": "Example.", "translation": "訳"}
        for value in (None, "", 0, 11, True, 2.5, "<script>alert(1)</script>"):
            with self.subTest(value=value):
                result = relation_cards([{**base, "frequency": value}])
                self.assertNotIn('relation-frequency', result)
                self.assertNotIn('<script>', result)
                self.assertIn('Example.', result)
        self.assertNotIn('relation-frequency', relation_cards([base]))

    def test_relation_frequency_accepts_scale_boundaries(self) -> None:
        base = {"word": "near", "difference": "", "example": "", "translation": ""}
        for score in (1, 10):
            self.assertIn(f'この語義の頻度 {score}/10', relation_cards([{**base, "frequency": score}]))

    def test_hero_omits_repeated_details_but_keeps_overview_and_sense(self) -> None:
        word = entry()
        result = word_page(word, [word])

        hero = result.split('<section class="word-hero">', 1)[1].split('</section>', 1)[0]
        self.assertIn('<h1>approximately</h1>', hero)
        self.assertNotIn('class="hero-ipa"', hero)
        self.assertNotIn(word["ipa"], hero)
        self.assertNotIn(word["lead"], hero)
        self.assertIn(f'<p class="big-ipa">{word["ipa"]}</p>', result)
        self.assertIn(word["senses"][0]["definition"], result)

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
