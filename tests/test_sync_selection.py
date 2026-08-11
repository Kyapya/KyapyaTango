from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_notion import normalize_cutoff, select_pages


def page(
    word: str,
    edited: str,
    tags: list[str] | None = None,
    status: str = "完了",
) -> dict:
    return {
        "id": word + edited,
        "last_edited_time": edited,
        "properties": {
            "ALL": {"type": "title", "title": [{"plain_text": word}]},
            "タグ": {
                "type": "multi_select",
                "multi_select": [{"name": tag} for tag in (tags or [])],
            },
            "Status": {"type": "status", "status": {"name": status}},
        },
    }


class SelectionTests(unittest.TestCase):
    def test_normalizes_date_only_cutoff(self) -> None:
        self.assertEqual(
            normalize_cutoff("2026-07-11"), "2026-07-11T00:00:00Z"
        )

    def test_full_sync_excludes_legacy_and_untagged_pages(self) -> None:
        pages, skipped, incomplete = select_pages(
            [
                page("old", "2026-07-10T23:59:59Z", ["英単語"]),
                page("new", "2026-07-11T00:00:00Z", ["英単語"]),
                page("memo", "2026-07-12T00:00:00Z", ["メモ"]),
            ],
            title_property="ALL",
            tag_property="タグ",
            tag_value="英単語",
            status_property="Status",
            complete_status="完了",
            requested=set(),
            minimum_last_edited_time="2026-07-11",
        )
        words = [
            item["properties"]["ALL"]["title"][0]["plain_text"]
            for item in pages
        ]
        self.assertEqual(words, ["new"])
        self.assertEqual(skipped, 1)
        self.assertEqual(incomplete, 0)

    def test_requested_word_can_sync_legacy_page(self) -> None:
        pages, skipped, incomplete = select_pages(
            [page("legacy", "2026-06-01T00:00:00Z", ["英単語"])],
            title_property="ALL",
            tag_property="タグ",
            tag_value="英単語",
            status_property="Status",
            complete_status="完了",
            requested={"legacy"},
            minimum_last_edited_time="2026-07-11",
        )
        self.assertEqual(len(pages), 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(incomplete, 0)

    def test_newest_duplicate_is_selected(self) -> None:
        pages, _, incomplete = select_pages(
            [
                page("mess", "2026-07-11T00:00:00Z", ["英単語"]),
                page("mess", "2026-07-12T00:00:00Z", ["英単語"]),
            ],
            title_property="ALL",
            tag_property="タグ",
            tag_value="英単語",
            status_property="Status",
            complete_status="完了",
            requested=set(),
            minimum_last_edited_time="2026-07-11",
        )
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["last_edited_time"], "2026-07-12T00:00:00Z")
        self.assertEqual(incomplete, 0)

    def test_in_progress_page_is_excluded_even_when_requested(self) -> None:
        pages, skipped, incomplete = select_pages(
            [page("abandon", "2026-08-12T00:00:00Z", ["英単語"], "進行中")],
            title_property="ALL",
            tag_property="タグ",
            tag_value="英単語",
            status_property="Status",
            complete_status="完了",
            requested={"abandon"},
            minimum_last_edited_time="2026-07-11",
        )
        self.assertEqual(pages, [])
        self.assertEqual(skipped, 0)
        self.assertEqual(incomplete, 1)

    def test_newer_in_progress_duplicate_blocks_older_completed_page(self) -> None:
        pages, skipped, incomplete = select_pages(
            [
                page("abandon", "2026-08-11T00:00:00Z", ["英単語"], "完了"),
                page("abandon", "2026-08-12T00:00:00Z", ["英単語"], "進行中"),
            ],
            title_property="ALL",
            tag_property="タグ",
            tag_value="英単語",
            status_property="Status",
            complete_status="完了",
            requested=set(),
            minimum_last_edited_time="2026-07-11",
        )
        self.assertEqual(pages, [])
        self.assertEqual(skipped, 0)
        self.assertEqual(incomplete, 1)

    def test_missing_status_is_not_treated_as_complete(self) -> None:
        candidate = page("abandon", "2026-08-12T00:00:00Z", ["英単語"])
        del candidate["properties"]["Status"]
        pages, _, incomplete = select_pages(
            [candidate],
            title_property="ALL",
            tag_property="タグ",
            tag_value="英単語",
            status_property="Status",
            complete_status="完了",
            requested=set(),
            minimum_last_edited_time="2026-07-11",
        )
        self.assertEqual(pages, [])
        self.assertEqual(incomplete, 1)


if __name__ == "__main__":
    unittest.main()
