from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_site import relation_cards


class RelationFrequencyStyleTests(unittest.TestCase):
    def test_frequency_uses_the_same_muted_size_as_card_labels(self) -> None:
        css = (ROOT / "assets/site.css").read_text(encoding="utf-8")
        frequency = re.search(r"\.relation-card>h4\+p:not\(\.ja\):not\(\.relation-definition\)\{([^}]+)\}", css).group(1)
        labels = re.search(r"\.collocation p b,\.relation-card p b\{([^}]+)\}", css).group(1)
        for declaration in ("color:var(--muted)", "font-size:11px"):
            self.assertIn(declaration, frequency)
            self.assertIn(declaration, labels)

    def test_selector_targets_only_optional_frequency_paragraph(self) -> None:
        base = {"word": "near", "difference": "違い", "example": "Example.", "translation": "訳"}
        for score in (1, 6, 10, None, 0, 11, True):
            with self.subTest(score=score):
                html = relation_cards([{**base, "frequency": score}])
                first = re.search(r"</h4>\s*<p([^>]*)>(.*?)</p>", html)
                if type(score) is int and 1 <= score <= 10:
                    self.assertEqual(first.group(1), "")
                    self.assertEqual(first.group(2), f"頻度 {score}/10")
                else:
                    self.assertEqual(first.group(1), ' class="ja"')
                    self.assertEqual(first.group(2), "<b>違い</b>違い")
                self.assertIn('<p><b>例</b>Example.</p>', html)
                self.assertIn('<p class="ja"><b>訳</b>訳</p>', html)


if __name__ == "__main__":
    unittest.main()
