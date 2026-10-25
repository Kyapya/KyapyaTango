"""Static document contracts, not mobile/browser scroll verification."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StudyPageShellTests(unittest.TestCase):
    def test_banner_and_its_spacing_are_removed(self):
        html = (ROOT / 'study.html').read_text()
        css = (ROOT / 'assets/study.css').read_text()
        self.assertNotIn('trial-banner', html)
        self.assertNotIn('trial-banner', css)
        self.assertIn('</header><main id="app"', html)
        self.assertIn('この端末・ブラウザだけに学習記録を保存します。', html)
        self.assertIn('他の端末・アカウントとの同期はありません。', html)

    def test_dictionary_documents_do_not_load_study_scroll_lock(self):
        for path in (ROOT / 'words').glob('*.html'):
            html = path.read_text()
            with self.subTest(page=path.name):
                self.assertNotIn('assets/study.', html)
                self.assertNotIn('session-active', html)
                self.assertIn('assets/site.js', html)
                self.assertIn('assets/site.css', html)


if __name__ == '__main__':
    unittest.main()
