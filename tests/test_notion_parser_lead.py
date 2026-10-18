from __future__ import annotations

import sys
from pathlib import Path
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from notion_parser import (  # noqa: E402
    _lead_from_definition,
    _resolve_lead,
    parse_dictionary_markdown,
    validate_entry,
)


MINIMAL_MARKDOWN = """# 発音記号
米・英: /ˈepɪk/

# 意味や関連情報の出力（日本語訳）
## 形容詞
### 日本語訳・定義
1. 長期にわたる、困難を伴う、壮大な、途方もない規模の
旅や闘争が通常の尺度を超えていることを表す。

### 頻度
〈7/10〉

### 文法パターン
・epic + 名詞＝壮大な～

### コロケーション
・an epic journey<br>用途: 壮大な旅を表す<br>例: They completed an epic journey.<br>訳: 彼らは壮大な旅を成し遂げた。
"""


class LeadGenerationTests(unittest.TestCase):
    def test_uses_first_definition_line_without_sense_number(self) -> None:
        self.assertEqual(
            _lead_from_definition(
                "1. 長期にわたる、困難を伴う、壮大な\n詳しい定義。"
            ),
            "長期にわたる、困難を伴う、壮大な",
        )

    def test_repairs_legacy_number_only_lead(self) -> None:
        entry = parse_dictionary_markdown(
            MINIMAL_MARKDOWN,
            word="epic",
            existing={"lead": "1."},
        )
        self.assertEqual(
            entry["lead"],
            "長期にわたる、困難を伴う、壮大な、途方もない規模の",
        )

    def test_replaces_nonempty_stale_lead(self) -> None:
        entry = parse_dictionary_markdown(
            MINIMAL_MARKDOWN,
            word="epic",
            existing={"lead": "通常の尺度を超えるほど壮大な"},
        )
        self.assertEqual(entry["lead"], "長期にわたる、困難を伴う、壮大な、途方もない規模の")

    def test_skips_blank_and_number_only_definition_lines(self) -> None:
        self.assertEqual(_lead_from_definition("\n1.\n\n新しい定義。\n補足。"), "新しい定義。")

    def test_limits_summary_to_180_characters(self) -> None:
        self.assertEqual(_lead_from_definition("あ" * 200), "あ" * 180)

    def test_refuses_unextractable_definition(self) -> None:
        for senses in ([], [{"definition": ""}], [{"definition": "1."}], [{"definition": None}]):
            with self.subTest(senses=senses):
                self.assertEqual(_resolve_lead(senses), "")

    def test_stale_lead_does_not_mask_missing_definition(self) -> None:
        markdown = MINIMAL_MARKDOWN.replace(
            "1. 長期にわたる、困難を伴う、壮大な、途方もない規模の\n旅や闘争が通常の尺度を超えていることを表す。", ""
        )
        entry = parse_dictionary_markdown(markdown, word="epic", existing={"lead": "古い概要"})
        self.assertIn("lead is empty", validate_entry(entry))

    def test_existing_lead_cannot_change_other_body_fields(self) -> None:
        fresh = parse_dictionary_markdown(MINIMAL_MARKDOWN, word="epic")
        refreshed = parse_dictionary_markdown(MINIMAL_MARKDOWN, word="epic", existing={"lead": "古い概要"})
        self.assertEqual(refreshed, fresh)

    def test_validation_rejects_number_only_lead(self) -> None:
        entry = parse_dictionary_markdown(MINIMAL_MARKDOWN, word="epic")
        entry["lead"] = "1."
        self.assertIn(
            "lead contains only a sense number: '1.'",
            validate_entry(entry),
        )


if __name__ == "__main__":
    unittest.main()
