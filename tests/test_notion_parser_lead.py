from __future__ import annotations

import sys
from pathlib import Path
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from notion_parser import (  # noqa: E402
    _lead_from_definition,
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

    def test_preserves_a_curated_lead(self) -> None:
        entry = parse_dictionary_markdown(
            MINIMAL_MARKDOWN,
            word="epic",
            existing={"lead": "通常の尺度を超えるほど壮大な"},
        )
        self.assertEqual(entry["lead"], "通常の尺度を超えるほど壮大な")

    def test_validation_rejects_number_only_lead(self) -> None:
        entry = parse_dictionary_markdown(MINIMAL_MARKDOWN, word="epic")
        entry["lead"] = "1."
        self.assertIn(
            "lead contains only a sense number: '1.'",
            validate_entry(entry),
        )


if __name__ == "__main__":
    unittest.main()
