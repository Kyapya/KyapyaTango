from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from finalize_site import ASSET_VERSION, MOBILE_TOOLBAR_STYLE, finalize_page


class FinalizeSiteTests(unittest.TestCase):
    def test_usage_notes_are_never_study_mode_targets(self) -> None:
        source = (
            '<html><head></head><body>'
            '<p class="definition ja">中心定義</p>'
            '<ul class="notes ja"><li>語法・注意</li></ul>'
            '<p class="ja">用途</p>'
            '</body></html>'
        )
        result = finalize_page(source)
        self.assertIn('class="definition ja"', result)
        self.assertIn('class="notes"', result)
        self.assertNotIn('class="notes ja"', result)
        self.assertIn('<p class="ja">用途</p>', result)

    def test_javascript_url_is_cache_busted_and_old_versions_are_replaced(self) -> None:
        for source in (
            '<html><head></head><script src="../assets/site.js"></script></html>',
            '<html><head></head><script src="../assets/site.js?v=old"></script></html>',
        ):
            with self.subTest(source=source):
                result = finalize_page(source)
                self.assertIn(
                    f'<script src="../assets/site.js?v={ASSET_VERSION}"></script>',
                    result,
                )

    def test_mobile_toolbar_style_is_injected_once(self) -> None:
        source = '<html><head></head><body></body></html>'
        result = finalize_page(source)
        self.assertIn(MOBILE_TOOLBAR_STYLE, result)
        self.assertEqual(result.count('id="mobile-toolbar-style"'), 1)
        self.assertEqual(
            finalize_page(result).count('id="mobile-toolbar-style"'),
            1,
        )
        self.assertIn('mobile-tools-open', result)
        self.assertIn('mobile-toolbar-hidden', result)


if __name__ == "__main__":
    unittest.main()
