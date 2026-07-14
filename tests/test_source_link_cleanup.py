from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from notion_parser import _clean_inline, parse_dictionary_markdown


class SourceLinkCleanupTests(unittest.TestCase):
    def test_removes_parenthesized_domain_source_link(self) -> None:
        value = (
            "米・英: /mes/ "
            "([dictionary.cambridge.org]"
            "(https://dictionary.cambridge.org/dictionary/english/mess))"
        )
        self.assertEqual(_clean_inline(value), "米・英: /mes/")

    def test_removes_full_width_parenthesized_domain_source_link(self) -> None:
        value = (
            "語源の説明。"
            "（[oxfordlearnersdictionaries.com]"
            "(https://www.oxfordlearnersdictionaries.com/definition/english/mess_2)）"
        )
        self.assertEqual(_clean_inline(value), "語源の説明。")

    def test_preserves_normal_link_text(self) -> None:
        value = (
            "詳しくは [Cambridge Dictionary]"
            "(https://dictionary.cambridge.org/) を参照。"
        )
        self.assertEqual(
            _clean_inline(value),
            "詳しくは Cambridge Dictionary を参照。",
        )

    def test_preserves_meaningful_parenthetical_link(self) -> None:
        value = "説明（[公式ガイド](https://example.com/guide)を参照）"
        self.assertEqual(
            _clean_inline(value),
            "説明（公式ガイドを参照）",
        )

    def test_parser_cleans_source_domains_across_fields(self) -> None:
        markdown = """# 発音記号
米・英: /mes/ ([dictionary.cambridge.org](https://dictionary.cambridge.org/))
# 語源
語源説明。 ([collinsdictionary.com](https://collinsdictionary.com/))
# 意味や関連情報の出力（日本語訳）
## 1. 意味
### 日本語訳・定義
定義本文。 ([dictionary.cambridge.org](https://dictionary.cambridge.org/))
### 頻度
〈9/10〉
### 文法パターン
・make a mess
### コロケーション
・make a mess<br>用途: 散らかす<br>例: Do not make a mess.<br>訳: 散らかさないで。
"""
        entry = parse_dictionary_markdown(markdown, word="mess")
        self.assertEqual(entry["ipa"], "米・英: /mes/")
        self.assertEqual(entry["etymology"], ["語源説明。"])
        self.assertEqual(entry["senses"][0]["definition"], "定義本文。")


if __name__ == "__main__":
    unittest.main()
