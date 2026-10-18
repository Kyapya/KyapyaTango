from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from notion_parser import _restore_literal_punctuation, parse_dictionary_markdown
from build_site import word_page
from sync_notion import NotionClient
from unittest.mock import Mock


class LiteralPunctuationTests(unittest.TestCase):
    def entry(self, text: str, **kwargs):
        return parse_dictionary_markdown(
            "# 発音記号\n米・英: /test/\n# 語源\n語源。\n"
            "# 意味や関連情報の出力（日本語訳）\n"
            "## 1. テスト\n### 日本語訳・定義\n定義。\n"
            "### 頻度\n〈5/10〉\n### 語法・注意\n" + text,
            word="test", **kwargs,
        )

    def test_currency_and_prompt_characters(self):
        text = r"The store took \$10 off the price. The 〈\$/\>〉 prompt."
        entry = self.entry(text)
        expected = "The store took $10 off the price. The 〈$/>〉 prompt."
        self.assertEqual(entry["senses"][0]["notes"], [expected])
        rendered = word_page(entry, [entry])
        self.assertIn("The store took $10 off the price.", rendered)
        self.assertNotIn(r"\$", rendered)
        self.assertIn("〈$/&gt;〉", rendered)

    def test_multiple_literal_error_markers_survive_emphasis_cleanup(self):
        text = r"誤: \*both A as well as B、\*another example。正: *both A and B*。"
        expected = "誤: *both A as well as B、*another example。正: both A and B。"
        self.assertEqual(self.entry(text)["senses"][0]["notes"], [expected])

    def test_all_nested_body_fields_and_numbers(self):
        value = {"text": r"\$10", "items": [r"\*bad", r"\>"], "frequency": 7}
        expected = {"text": "$10", "items": ["*bad", ">"], "frequency": 7}
        self.assertEqual(_restore_literal_punctuation(value), expected)

    def test_decode_once_preserves_intended_backslash_and_unknown_sequences(self):
        self.assertEqual(_restore_literal_punctuation(r"\\\$10"), r"\$10")
        self.assertEqual(_restore_literal_punctuation(r"C:\temp\word"), r"C:\temp\word")

    def test_preserved_metadata_not_decoded(self):
        existing = {"lead": r"stored \$ lead", "sources": [r"C:\\sources"]}
        entry = self.entry(r"\$10", existing=existing, page_url=r"https://example.test/\$10")
        self.assertEqual(entry["lead"], "定義。")
        self.assertEqual(entry["sources"], existing["sources"])
        self.assertEqual(entry["notion_url"], r"https://example.test/\$10")

    def test_existing_ipa_not_decoded_on_repeated_import(self):
        original = {"ipa": r"/literal\\\$/", "slug": "test"}
        for _ in range(3):
            entry = parse_dictionary_markdown("# 語源\n語源。", word="test", existing=original)
            self.assertEqual(entry["ipa"], original["ipa"])
            original = entry

    def test_inline_code_preserves_literal_escapes(self):
        entry = self.entry(r"Code `\$HOME` stays literal; normal \$10.")
        self.assertEqual(entry["senses"][0]["notes"],
                         [r"Code \$HOME stays literal; normal $10."])

    def test_backslash_code_keeps_ipa_detection(self):
        entry = parse_dictionary_markdown(
            r"# 発音記号" + "\n" + r"`/literal\$/`", word="test"
        )
        self.assertEqual(entry["ipa"], r"/literal\$/")
        self.assertEqual(entry["pronunciation"], [])

    def test_plain_block_fallback_preserves_literal_backslashes(self):
        text = r"Literal \$10 and C:\\path and \*marker."
        entry = self.entry(text, decode_literal_escapes=False)
        self.assertEqual(entry["senses"][0]["notes"], [text])

    def test_client_distinguishes_markdown_and_plain_block_fallback(self):
        client = NotionClient("test-token-not-used")
        client.request = Mock(return_value=Mock(ok=True, json=lambda: {"markdown": r"\$10"}))
        self.assertEqual(client.page_markdown("test-page"), (r"\$10", True))
        client.request = Mock(return_value=Mock(ok=False))
        client.block_tree = Mock(return_value=[
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": r"\$10"}]}}
        ])
        self.assertEqual(client.page_markdown("test-page"), (r"\$10" + "\n", False))


if __name__ == "__main__":
    unittest.main()
