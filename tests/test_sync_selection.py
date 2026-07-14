from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_notion import normalize_cutoff, select_pages


def page(word: str, edited: str, tags: list[str] | None = None) -> dict:
    return {
        "id": word + edited,
        "last_edited_time": edited,
        "properties": {
            "ALL": {"type": "title", "title": [{"plain_text": word}]},
            "タグ": {
                "type": "multi_select",
                "multi_select": [{"name": tag} for tag in (tags or [])],
            },
        },
    }


class SelectionTests(unittest.TestCase):
    def test_normalizes_date_only_cutoff(self) -> None:
        self.assertEqual(
            normalize_cutoff("2026-07-11"), "2026-07-11T00:00:00Z"
        )

    def test_full_sync_excludes_legacy_and_untagged_pages(self) -> None:
        pages, skipped = select_pages(
            [
                page("old", "2026-07-10T23:59:59Z", ["英単語"]),
                page("new", "2026-07-11T00:00:00Z", ["英単語"]),
                page("memo", "2026-07-12T00:00:00Z", ["メモ"]),
            ],
            title_property="ALL",
            tag_property="タグ",
            tag_value="英単語",
            requested=set(),
            minimum_last_edited_time="2026-07-11",
        )
        words = [
            item["properties"]["ALL"]["title"][0]["plain_text"]
            for item in pages
        ]
        self.assertEqual(words, ["new"])
        self.assertEqual(skipped, 1)

    def test_requested_word_can_sync_legacy_page(self) -> None:
        pages, skipped = select_pages(
            [page("legacy", "2026-06-01T00:00:00Z", ["英単語"])],
            title_property="ALL",
            tag_property="タグ",
            tag_value="英単語",
            requested={"legacy"},
            minimum_last_edited_time="2026-07-11",
        )
        self.assertEqual(len(pages), 1)
        self.assertEqual(skipped, 0)

    def test_newest_duplicate_is_selected(self) -> None:
        pages, _ = select_pages(
            [
                page("mess", "2026-07-11T00:00:00Z", ["英単語"]),
                page("mess", "2026-07-12T00:00:00Z", ["英単語"]),
            ],
            title_property="ALL",
            tag_property="タグ",
            tag_value="英単語",
            requested=set(),
            minimum_last_edited_time="2026-07-11",
        )
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["last_edited_time"], "2026-07-12T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
