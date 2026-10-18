"""Exercise the sync write boundary with a fake Notion client (no network)."""
import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sync_notion
from test_notion_parser_lead import MINIMAL_MARKDOWN
from test_sync_selection import page


class LeadSyncTests(unittest.TestCase):
    def test_refresh_or_reject_without_losing_existing_file(self):
        for markdown, expected_status in [(MINIMAL_MARKDOWN, 0), ('# 語源\n本文が欠落。', 1)]:
            with self.subTest(status=expected_status), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                target = root / 'epic.json'
                original = {'lead': '古い概要', 'slug': 'epic', 'ipa': '/epik/', 'sources': ['retained']}
                target.write_text(json.dumps(original))
                before = target.read_bytes()
                args = argparse.Namespace(output=root, config=root/'missing.json', word=['epic'], dry_run=False, allow_partial=False)
                with patch.object(sync_notion, 'parse_args', return_value=args), patch.dict('os.environ', {'NOTION_TOKEN': 'test-only'}, clear=True), patch.object(sync_notion, 'NotionClient') as client, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    client.return_value.query_all_pages.return_value = [page('epic', '2026-10-18T00:00:00Z', ['英単語'])]
                    client.return_value.page_markdown.return_value = (markdown, False)
                    self.assertEqual(sync_notion.main(), expected_status)
                if expected_status:
                    self.assertEqual(target.read_bytes(), before)
                else:
                    result = json.loads(target.read_text())
                    self.assertEqual(result['lead'], '長期にわたる、困難を伴う、壮大な、途方もない規模の')
                    self.assertEqual(result['sources'], original['sources'])
                    self.assertEqual(result['senses'][0]['collocations'][0]['example'], 'They completed an epic journey.')
