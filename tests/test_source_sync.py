from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from sync_source import plan_sync, source_to_entry, SOURCE_REPOSITORY, main
from source_markdown import _split_front_matter
from source_entry_validation import validate_text
from build_site import word_page
from verify_source_ci import require_successful_validation, WORKFLOW
import sync_notion

REV = 'a' * 40
FIXTURE = (ROOT / 'tests/fixtures/source-entry.md').read_text(encoding='utf-8')


class SourceSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'; self.output = self.root / 'content'
        (self.source / 'entries/r').mkdir(parents=True)
        (self.source / 'queue').mkdir()
        self.output.mkdir()
        self.article = self.source / 'entries/r/refulgent.md'
        self.article.write_text(FIXTURE, encoding='utf-8')
        self.row = {'headword':'refulgent', 'file':'entries/r/refulgent.md', 'checked':'true', 'status':'checked'}
        self.queue([self.row])

    def queue(self, rows):
        with (self.source / 'queue/words.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(self.row)); writer.writeheader(); writer.writerows(rows)

    def plan(self, previous=None, **kwargs):
        return plan_sync(self.source, self.output, previous or {}, REV, **kwargs)

    def seed(self):
        changes, state = self.plan()
        self.assertEqual(len(changes), 1)
        path, entry = next(iter(changes.items()))
        path.write_text(json.dumps(entry, ensure_ascii=False), encoding='utf-8')
        return path, entry, state

    def test_fixture_passes_real_pinned_source_validator(self):
        self.assertEqual(validate_text(FIXTURE), [])

    def test_new_entry_without_notion_has_source_date_and_no_empty_link(self):
        changes, _ = self.plan(date_for_path=lambda _: '2026-10-27')
        entry = next(iter(changes.values()))
        self.assertEqual(entry['updated'], '2026-10-27')
        self.assertEqual(entry['notion_url'], '')
        page = word_page(entry, [entry])
        self.assertNotIn('Notionの原本を開く', page)
        self.assertNotIn('href=""', page)

    def test_idempotence_and_metadata_preserved(self):
        path, old, state = self.seed()
        old.update(slug='original-url', updated='2020-01-02', notion_url='https://notion.so/example', sources=['source'], custom_metadata={'keep':True})
        path.unlink(); path = self.output / 'original-url.json'; path.write_text(json.dumps(old), encoding='utf-8')
        changes, new_state = self.plan(state, date_for_path=lambda _: self.fail('unchanged article must not change date'))
        self.assertEqual(changes, {})
        self.assertEqual(new_state, state)
        self.assertEqual(json.loads(path.read_text()), old)

    def test_changed_body_updates_date_but_preserves_metadata(self):
        path, old, state = self.seed()
        old.update(notion_url='https://notion.so/example', custom_metadata='keep', sources=['s'])
        path.write_text(json.dumps(old))
        self.article.write_text(FIXTURE.replace('/rɪˈfʌldʒənt/', '/rɪˈfʌldʒənt2/'))
        # Change a parsed field irrespective of the fixture's exact IPA spelling.
        raw = self.article.read_text(); self.article.write_text(raw.replace('＃語源', '＃語源\n\n追加のテスト用文。  '))
        changes, _ = self.plan(state, date_for_path=lambda _: '2026-10-28')
        new = changes[path]
        self.assertEqual(new['updated'], '2026-10-28')
        for key in ('slug','notion_url','sources','custom_metadata'):
            self.assertEqual(new[key], old[key])

    def test_both_review_gates_required(self):
        path, old, state = self.seed()
        for gate in ('queue', 'frontmatter'):
            with self.subTest(gate=gate):
                self.queue([{**self.row, 'checked':'false'}] if gate=='queue' else [self.row])
                self.article.write_text(FIXTURE.replace('checked: true', 'checked: false') if gate=='frontmatter' else FIXTURE)
                changes, result = self.plan(state)
                self.assertEqual(changes, {})
                self.assertTrue(result['retained'])
                self.assertEqual(json.loads(path.read_text()), old)

    def test_missing_source_keeps_last_known_good(self):
        path, old, state = self.seed(); self.article.unlink()
        changes, result = self.plan(state)
        self.assertEqual(changes, {}); self.assertTrue(result['retained'])
        self.assertEqual(json.loads(path.read_text()), old)

    def test_removed_queue_row_never_deletes(self):
        path, old, state = self.seed()
        self.queue([{**self.row, 'headword':'other', 'file':'entries/o/other.md'}])
        changes, result = self.plan(state)
        self.assertEqual(changes, {}); self.assertEqual(len(result['retained']), 2)
        self.assertTrue(path.exists())

    def test_empty_queue_fails_closed(self):
        self.queue([])
        with self.assertRaisesRegex(ValueError, 'Empty source queue'): self.plan()

    def test_invalid_source_causes_no_writes(self):
        path, old, state = self.seed()
        self.article.write_text(FIXTURE.replace('＃発音記号', '＃不正'))
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'source validation failed'): self.plan(state)
        self.assertEqual(path.read_bytes(), before)

    def test_duplicate_queue_is_rejected(self):
        self.queue([self.row, self.row])
        with self.assertRaisesRegex(ValueError, 'duplicate'): self.plan()

    def test_wrong_headword_is_rejected(self):
        self.article.write_text(FIXTURE.replace('headword: refulgent', 'headword: wrong'))
        with self.assertRaisesRegex(ValueError, 'mismatch'): self.plan()

    def test_traversal_and_symlinks_are_rejected(self):
        for name in ('../outside.md','/tmp/outside.md','entries/../../outside.md'):
            self.queue([{**self.row,'file':name}])
            with self.assertRaisesRegex(ValueError, 'Unsafe'): self.plan()
        self.queue([self.row]); self.article.unlink(); self.article.symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError, 'escapes'): self.plan()

    def test_unknown_word_fails_without_changes(self):
        with self.assertRaisesRegex(ValueError, 'absent'): self.plan(word='not-in-queue')

    def test_non_sha_and_wrong_repository_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'immutable'):
            plan_sync(self.source, self.output, {}, 'main')
        with self.assertRaisesRegex(ValueError, 'repository'):
            self.plan({'repository':'other/repo'})

    def test_legacy_notion_writer_disabled_without_any_network(self):
        with patch.object(sync_notion.NotionClient, 'request', side_effect=AssertionError('No Notion calls')):
            self.assertEqual(sync_notion.main(), 2)

    def test_dirty_and_rollback_checkouts_rejected(self):
        state_path=self.root/'state.json'
        state_path.write_text(json.dumps({'repository': SOURCE_REPOSITORY, 'revision':'b'*40}))
        args=['sync_source.py','--source',str(self.source),'--output',str(self.output),'--state',str(state_path)]
        with patch.object(sys,'argv',args), patch('sync_source.git',side_effect=[REV,'dirty']):
            with self.assertRaisesRegex(ValueError,'dirty'): main()
        with patch.object(sys,'argv',args), patch('sync_source.git',side_effect=[REV,'']), patch('sync_source.subprocess.run',return_value=subprocess.CompletedProcess([],1)):
            with self.assertRaisesRegex(ValueError,'rollback'): main()

    def test_dry_run_never_writes(self):
        state_path=self.root/'state.json'
        args=['sync_source.py','--source',str(self.source),'--output',str(self.output),'--state',str(state_path),'--dry-run']
        with patch.object(sys,'argv',args), patch('sync_source.git',side_effect=[REV,'','2026-10-27T00:00:00Z']):
            self.assertEqual(main(),0)
        self.assertFalse(state_path.exists()); self.assertEqual(list(self.output.iterdir()),[])


class SourceCIContractTests(unittest.TestCase):
    def run_record(self, **changes):
        return dict(id=1, head_sha=REV, head_branch='main', event='push', path=WORKFLOW,
                    status='completed', conclusion='success', **changes)

    def test_exact_success(self):
        require_successful_validation(REV, {'workflow_runs':[self.run_record()]})

    def test_pending_failed_wrong_sha_and_wrong_workflow_are_rejected(self):
        for changes in ({'status':'in_progress'}, {'conclusion':'failure'}, {'head_sha':'b'*40},
                        {'path':'.github/workflows/sync-notion.yml'}, {'event':'pull_request'}):
            record=self.run_record(); record.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                require_successful_validation(REV, {'workflow_runs':[record]})

    def test_newer_failed_run_cannot_reuse_old_success(self):
        newer=self.run_record(); newer.update(id=2,conclusion='failure')
        with self.assertRaises(ValueError):
            require_successful_validation(REV, {'workflow_runs':[self.run_record(),newer]})


class WorkflowContractTests(unittest.TestCase):
    def test_existing_schedule_dispatch_and_privileges_preserved(self):
        workflow=(ROOT/'.github/workflows/sync-notion.yml').read_text()
        self.assertIn("cron: '17 */6 * * *'",workflow)
        self.assertIn('workflow_dispatch:',workflow)
        self.assertNotIn('secrets.',workflow)
        self.assertNotIn('pages: write',workflow)
        self.assertNotIn('id-token: write',workflow)
        self.assertNotIn('python scripts/sync_notion.py',workflow)
        self.assertIn('cancel-in-progress: false',workflow)
        self.assertIn('git push origin HEAD:main',workflow)
        self.assertIn('SOURCE_SHA',workflow); self.assertIn('SITE_BASE',workflow)
        self.assertIn('pull_request:',workflow)
        self.assertIn('--require-ci',workflow)


if __name__=='__main__': unittest.main()
