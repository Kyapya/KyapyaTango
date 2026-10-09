import json
import sys
import unittest
from html import escape
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_site import core_html, relation_cards, word_page
from finalize_site import finalize_page
from notion_parser import _parse_core, _parse_entries, blocks_to_markdown, parse_dictionary_markdown
from test_build_site import entry


class SharedDisplayTests(unittest.TestCase):
    def test_definition_escaping_frequency_order_and_js_isolation(self):
        base = dict(word='near', difference='違い', example='Example.', translation='訳')
        for score in (None, 5):
            html = relation_cards([{**base, 'definition': '1. <tag> & "定義"', 'frequency': score}])
            expected = '<p class="relation-definition"><b>定義</b>1. &lt;tag&gt; &amp; &quot;定義&quot;</p>'
            self.assertIn(expected, html)
            self.assertNotIn('class="definition', html)
            self.assertNotIn('relation-definition ja', html)
            if score:
                self.assertLess(html.index('頻度 5/10'), html.index(expected))
            else:
                self.assertNotIn('頻度', html)
        for definition in ('', '  '):
            self.assertNotIn('<b>定義</b>', relation_cards([{**base, 'definition': definition}]))
        self.assertNotIn('<b>定義</b>', relation_cards([base]))

    def test_optional_panels_and_sources(self):
        for populated in (False, True):
            data = entry()
            if populated:
                data['formation'] = [dict(term='a&b', description='<description>')]
                data['sources'] = [dict(name='A&B', url='https://example.org/?a=1&b=2')]
            html = finalize_page(word_page(data, [data]))
            for marker in ('id="formation"', 'href="#formation"', '<b>参照:</b>'):
                self.assertEqual(marker in html, populated)
            self.assertIn('Notionの原本を開く', html)
            self.assertIn(data['notion_url'], html)
            if populated:
                self.assertIn('&lt;description&gt;', html)
                self.assertIn('https://example.org/?a=1&amp;b=2', html)

    def test_core_boundaries_punctuation_and_continuations(self):
        lines = ['導入: a b → c', '続く文章。', '', '- 枝 → 意味: 説明',
                 '  続く枝。', '- 従来: 説明', '後の段落。', '', '・旧ラベル 説明']
        expected = [dict(type='paragraph', text='導入: a b → c\n続く文章。'),
                    dict(type='item', text='枝 → 意味: 説明\n続く枝。'),
                    dict(type='item', text='従来: 説明'),
                    dict(type='paragraph', text='後の段落。'),
                    dict(type='item', text='旧ラベル 説明')]
        self.assertEqual(_parse_core(lines), expected)
        self.assertEqual(_parse_core([]), [])
        self.assertEqual(_parse_core(['*導入* a b']), [dict(type='paragraph', text='導入 a b')])
        html = core_html(json.loads(json.dumps(expected)))
        self.assertIn('<p class="core-paragraph">導入: a b → c\n続く文章。</p>', html)
        self.assertEqual(html.count('<li class="core-item">'), 3)
        self.assertEqual(html.count('<ul '), html.count('</ul>'))
        self.assertIn('従来: 説明', html)
        self.assertIn('旧ラベル 説明', html)

    def test_blocks_parse_json_final_html(self):
        blocks = []
        for kind, text in [('heading_1', 'コアイメージ'), ('paragraph', '導入: a & b'),
                           ('bulleted_list_item', '枝 → 意味'), ('paragraph', '次の段落。')]:
            blocks.append({'type': kind, kind: {'rich_text': [{'plain_text': text}]}})
        data = parse_dictionary_markdown(blocks_to_markdown(blocks), word='test')
        word = entry()
        word['core'] = json.loads(json.dumps(data['core']))
        html = finalize_page(word_page(word, [word]))
        for item in data['core']:
            self.assertIn(escape(item['text']), html)
        self.assertIn('<p class="core-paragraph">導入: a &amp; b</p>', html)
        self.assertIn('href="#core"', html)

    def test_legacy_core_does_not_invent_separator(self):
        html = core_html([dict(label='導入', description='分割済み & 不明')])
        self.assertIn('<b>導入</b><span class="ja">分割済み &amp; 不明</span>', html)
        self.assertNotIn('core-paragraph', html)
        self.assertIn('<div class="core-grid">', html)
        self.assertIn('&lt;unsafe&gt;', core_html([dict(type='paragraph', text='<unsafe>')]))

    def test_legacy_relation_numbered_labels_without_spaces(self):
        for separator in ('.', '．'):
            with self.subTest(separator=separator):
                lines = ['・near', f'1{separator}定義: 近い',
                         f'2{separator}頻度: 6/10', f'3{separator}違い: 距離が近い',
                         f'4{separator}例: Stay near.', f'5{separator}訳: 近くにいて。']
                parsed = _parse_entries(lines, relation=True)
                self.assertEqual(parsed, [dict(word='near', definition='近い',
                    frequency=6, difference='距離が近い', example='Stay near.',
                    translation='近くにいて。')])
                html = relation_cards(json.loads(json.dumps(parsed)))
                self.assertIn('<h4>near</h4>', html)
                self.assertIn('<p>頻度 6/10</p>', html)
                self.assertIn('<p class="relation-definition"><b>定義</b>近い</p>', html)
