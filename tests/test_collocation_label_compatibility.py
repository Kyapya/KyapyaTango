import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from notion_parser import parse_dictionary_markdown
from build_site import word_page
from test_notion_parser_lead import MINIMAL_MARKDOWN

class CollocationLabelTests(unittest.TestCase):
    def test_old_and_new_notion_headings_parse_identically(self):
        old = parse_dictionary_markdown(MINIMAL_MARKDOWN, word='epic')
        new = parse_dictionary_markdown(MINIMAL_MARKDOWN.replace('### コロケーション', '### コロケーション・構文例'), word='epic')
        self.assertEqual(old, new)
        self.assertEqual(len(new['senses'][0]['collocations']), 1)

    def test_renderer_uses_canonical_label_without_schema_change(self):
        word = parse_dictionary_markdown(MINIMAL_MARKDOWN, word='epic')
        html = word_page(word, [word])
        self.assertIn('コロケーション・構文例', html)
        self.assertNotIn('コロケーションと例文', html)
        self.assertIn('They completed an epic journey.', html)
