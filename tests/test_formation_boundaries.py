from __future__ import annotations

import sys
import unittest
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from notion_parser import blocks_to_markdown, parse_dictionary_markdown
from build_site import word_page
from finalize_site import finalize_page
from test_build_site import entry


def formation(line):
    return parse_dictionary_markdown('# 語形成\n' + line, word='test')['formation'][0]


class FormationBoundariesTests(unittest.TestCase):
    def test_heading_colon_precedes_spaces(self):
        for head in (
            'feasibility study', 'antimicrobial susceptibility', 'new compound phrase',
            'acknowledgment / acknowledgement', 'wise guy / wiseguy',
            'in- + exact → inexact', 'begin – began – begun',
            'epic【形容詞】→ epic【名詞】', 'takeoff / take-off（名詞）',
            'unfamiliar compound【複合名詞】',
            'wartime、peacetime', 'sensitive、sensibility', 'pre-war、post-war',
            '〈名詞〉-specific（複合形容詞）', '[名詞]-deprived【複合形容詞】',
        ):
            for colon in (':', '：'):
                with self.subTest(head=head, colon=colon):
                    self.assertEqual(formation(f'・{head}{colon} 説明: 続き。'),
                                     dict(term=head, description='説明: 続き。'))

    def test_japanese_before_colon_is_not_a_heading(self):
        for head, description in (
            ('entire【形容詞】', '全体の、完全な：通常は名詞の前。'),
            ('entirely【副詞】', '完全に：程度の全部。'),
            ('enormous + -ly → enormously', '「非常に、莫大に」：修飾する。'),
            ('a new compound', '「日本語の訳」: 説明。'),
            ('alpha', '"日本語の訳": 説明。'),
            ('alpha', '“日本語の訳”: 説明。'),
            ('alpha', '（日本語の訳）: 説明。'),
            ('alpha', '【名詞「日本語の訳」】: 説明。'),
            ('alpha', 'は説明を導く。例: a new compound。'),
        ):
            with self.subTest(description=description):
                self.assertEqual(formation(f'・{head} {description}'),
                                 dict(term=head, description=description))
        self.assertEqual(formation('・説明だけの文: 日本語の引用。'),
                         dict(term='', description='説明だけの文: 日本語の引用。'))

    def test_no_colon_labels_and_legacy_forms(self):
        for head in ('post office', 'mess hall', 'mess kit', 'mess tin', 'new noun phrase'):
            with self.subTest(head=head):
                self.assertEqual(formation(f'・{head} 名詞 説明。'),
                                 dict(term=head, description='名詞 説明。'))
        for line, head, description in (
            ('word は説明。', 'word', 'は説明。'),
            ('word legacy explanation', 'word', 'legacy explanation'),
            ('word — 説明。', 'word', '— 説明。'),
            ('absolute + -ly → absolutely', 'absolute + -ly → absolutely', ''),
            ('alpha【形容詞】→ beta【名詞】', 'alpha【形容詞】→ beta【名詞】', ''),
            ('alpha + beta = gamma', 'alpha + beta = gamma', ''),
            ('where + ever → wherever「どこでも」', 'where + ever → wherever', '「どこでも」'),
            ('entire【形容詞】全体の', 'entire【形容詞】', '全体の'),
            ('complied、complying は活用形。', 'complied、complying', 'は活用形。'),
        ):
            with self.subTest(line=line):
                self.assertEqual(formation('・' + line), dict(term=head, description=description))

    def test_one_bullet_removed_through_all_section_paths(self):
        blocks = []
        def block(kind, text):
            blocks.append({'type': kind, kind: {'rich_text': [{'plain_text': text}]}})
        for heading in ('発音記号', '語源', '語形成', 'コアイメージ'):
            block('heading_1', heading)
            block('bulleted_list_item', '-ever は説明。')
        block('heading_1', '意味や関連情報の出力（日本語訳）')
        block('heading_2', '1. 名詞')
        for heading in ('日本語訳・定義', '頻度', 'レジスター/領域', '文法パターン',
                        'コロケーション・構文例', '語法・注意', '類義語', '反意語'):
            block('heading_3', heading)
            if heading == '頻度':
                block('paragraph', '6/10')
            else:
                block('bulleted_list_item', '-ever は説明。')
        parsed = parse_dictionary_markdown(blocks_to_markdown(blocks), word='test')
        self.assertEqual(parsed['formation'], [dict(term='-ever', description='は説明。')])
        for key in ('pronunciation', 'etymology'):
            self.assertEqual(parsed[key], ['-ever は説明。'])
        self.assertEqual(parsed['core'], [dict(type='item', text='-ever は説明。')])
        sense = parsed['senses'][0]
        self.assertIn('-ever', sense['definition'])
        for key in ('register', 'patterns', 'notes'):
            self.assertEqual(sense[key], ['-ever は説明。'])
        self.assertEqual(sense['collocations'][0]['pattern'], '-ever は説明。')
        for key in ('synonyms', 'antonyms'):
            self.assertEqual(sense[key][0]['word'], '-ever は説明。')
        for bullet in ('・', '- ', '* ', '+ ', '1. '):
            self.assertEqual(formation(bullet + '-ever は説明。')['term'], '-ever')

    def test_description_stays_inside_japanese_mask_in_built_html(self):
        data = entry()
        lines = ['・feasibility study: 可算名詞「調査」。',
                 '・enormous + -ly → enormously「非常に」：説明。',
                 '・entire【形容詞】全体の：説明。']
        data['formation'] = parse_dictionary_markdown(
            '# 語形成\n' + '\n'.join(lines), word=data['word'])['formation']
        html = finalize_page(word_page(data, [data]))
        for row in data['formation']:
            self.assertIn(f'<b>{escape(row["term"])}</b><span class="ja">'
                          f'{escape(row["description"])}</span>', html)


if __name__ == '__main__':
    unittest.main()
