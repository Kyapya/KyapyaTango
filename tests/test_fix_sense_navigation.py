from __future__ import annotations

import sys
from pathlib import Path
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from fix_sense_navigation import navigation_label, repair_navigation  # noqa: E402


class SenseNavigationTests(unittest.TestCase):
    def test_removes_only_decorative_outer_brackets(self) -> None:
        self.assertEqual(navigation_label("【形容詞】"), "形容詞")
        self.assertEqual(
            navigation_label("【形容詞・古風／歴史的用法】"),
            "形容詞・古風／歴史的用法",
        )
        self.assertEqual(navigation_label("形容詞"), "形容詞")

    def test_repairs_number_only_navigation_links(self) -> None:
        html = (
            '<nav class="side-nav sense-nav">'
            '<a href="#sense-1" data-target="sense-1"><span>1</span></a>'
            '<a href="#sense-2" data-target="sense-2"><span>2</span></a>'
            '</nav>'
        )
        senses = [
            {"number": 1, "title": "【形容詞】"},
            {"number": 2, "title": "【形容詞・古風／歴史的用法】"},
        ]

        repaired, changed = repair_navigation(html, senses)

        self.assertEqual(changed, 2)
        self.assertIn('<span>1</span>形容詞</a>', repaired)
        self.assertIn(
            '<span>2</span>形容詞・古風／歴史的用法</a>',
            repaired,
        )

    def test_replaces_an_existing_incorrect_label(self) -> None:
        html = (
            '<a href="#sense-1" data-target="sense-1">'
            '<span>1</span>誤った表示</a>'
        )
        repaired, changed = repair_navigation(
            html,
            [{"number": 1, "title": "【名詞・可算】"}],
        )
        self.assertEqual(changed, 1)
        self.assertEqual(
            repaired,
            '<a href="#sense-1" data-target="sense-1">'
            '<span>1</span>名詞・可算</a>',
        )


if __name__ == "__main__":
    unittest.main()
