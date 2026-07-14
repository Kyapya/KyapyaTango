from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from notion_parser import _clean_inline, parse_dictionary_markdown


class MarkupCleanupTests(unittest.TestCase):
    def test_unescapes_grammar_brackets(self) -> None:
        self.assertEqual(
            _clean_inline(r"\[場所 / 物\] + be + a mess"),
            "[場所 / 物] + be + a mess",
        )
        self.assertEqual(
            _clean_inline(r"leave \[something\] in a mess"),
            "leave [something] in a mess",
        )

    def test_removes_single_asterisk_emphasis(self) -> None:
        self.assertEqual(_clean_inline("*make a mess of O*"), "make a mess of O")
        self.assertEqual(
            _clean_inline("Use *mess up* carefully."),
            "Use mess up carefully.",
        )

    def test_keeps_unpaired_asterisk_bullet(self) -> None:
        self.assertEqual(_clean_inline("* item"), "* item")

    def test_markup_is_cleaned_before_structural_parsing(self) -> None:
        markdown = r"""# 発音記号
米・英: /mes/
# 語源
語源。
# 語形成
・*mess hall* 名詞: 共同食堂。
# 意味や関連情報の出力（日本語訳）
## 1. 散らかり
### 日本語訳・定義
散らかった状態。
### 頻度
〈9/10〉
### 文法パターン
・\[場所\] + be + a mess
### コロケーション
・*make a mess*<br>用途: 散らかす<br>例: They made a mess.<br>訳: 彼らは散らかした。
"""
        entry = parse_dictionary_markdown(markdown, word="mess")
        self.assertEqual(entry["formation"][0]["term"], "mess hall")
        self.assertEqual(
            entry["senses"][0]["patterns"][0],
            "[場所] + be + a mess",
        )
        self.assertEqual(
            entry["senses"][0]["collocations"][0]["pattern"],
            "make a mess",
        )


if __name__ == "__main__":
    unittest.main()
