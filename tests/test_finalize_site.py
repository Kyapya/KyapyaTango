from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from finalize_site import ASSET_VERSION, finalize_page


class FinalizeSiteTests(unittest.TestCase):
    def test_usage_notes_are_never_study_mode_targets(self) -> None:
        source = (
            '<p class="definition ja">中心定義</p>'
            '<ul class="notes ja"><li>語法・注意</li></ul>'
            '<p class="ja">用途</p>'
        )
        result = finalize_page(source)
        self.assertIn('class="definition ja"', result)
        self.assertIn('class="notes"', result)
        self.assertNotIn('class="notes ja"', result)
        self.assertIn('<p class="ja">用途</p>', result)

    def test_javascript_url_is_cache_busted(self) -> None:
        source = '<script src="../assets/site.js"></script>'
        result = finalize_page(source)
        self.assertEqual(
            result,
            f'<script src="../assets/site.js?v={ASSET_VERSION}"></script>',
        )


if __name__ == "__main__":
    unittest.main()
