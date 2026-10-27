"""Exercise the direct-source write boundary without network or Notion."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sync_source import source_to_entry, write_json
from test_notion_parser_lead import MINIMAL_MARKDOWN


class LeadSyncTests(unittest.TestCase):
    def test_refresh_or_reject_without_losing_existing_file(self):
        for markdown, invalid in [(MINIMAL_MARKDOWN, False), ('# 語源\n本文が欠落。', True)]:
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as temp:
                target = Path(temp) / 'epic.json'
                original = {'lead': '古い概要', 'slug': 'epic', 'ipa': '/epik/', 'sources': ['retained']}
                target.write_text(json.dumps(original))
                before = target.read_bytes()
                if invalid:
                    with self.assertRaises(ValueError):
                        source_to_entry(markdown, 'epic', original)
                    self.assertEqual(target.read_bytes(), before)
                else:
                    result = source_to_entry(markdown, 'epic', original)
                    write_json(target, result)
                    result = json.loads(target.read_text())
                    self.assertEqual(result['lead'], '長期にわたる、困難を伴う、壮大な、途方もない規模の')
                    self.assertEqual(result['sources'], original['sources'])
                    self.assertEqual(result['senses'][0]['collocations'][0]['example'], 'They completed an epic journey.')
