"""Offline tests for bounded, read-only exact-source CI observation."""
from __future__ import annotations

from collections import deque
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_source_ci import verify_source_ci, require_successful_validation, WORKFLOW
import sync_source

SHA = 'a' * 40


def record(**changes):
    return dict(dict(id=1, run_attempt=1, head_sha=SHA, head_branch='main',
                     event='push', path=WORKFLOW, status='completed', conclusion='success'), **changes)


def payload(*runs):
    return {'workflow_runs': list(runs)}


class Clock:
    def __init__(self):
        self.now = 0
        self.sleeps = []
    def monotonic(self): return self.now
    def sleep(self, delay):
        self.sleeps.append(delay)
        self.now += delay


class SourceCIWaitTests(unittest.TestCase):
    def observe(self, responses, *, timeout=30, interval=10, elapsed=0, revision=SHA):
        self.clock = Clock()
        self.requests = []
        responses = deque(responses)
        def get(request, **kwargs):
            self.requests.append((request, kwargs))
            self.clock.now += elapsed
            value = responses.popleft() if len(responses) > 1 else responses[0]
            if isinstance(value, Exception): raise value
            return io.StringIO(value if isinstance(value, str) else json.dumps(value))
        with patch('verify_source_ci.urllib.request.urlopen', side_effect=get):
            verify_source_ci(revision, timeout=timeout, interval=interval,
                             sleep=self.clock.sleep, monotonic=self.clock.monotonic)

    def test_immediate_success_and_fixed_public_get(self):
        self.observe([payload(record())])
        self.assertEqual(self.clock.sleeps, [])
        self.assertEqual(len(self.requests), 1)
        request, kwargs = self.requests[0]
        self.assertEqual(request.get_method(), 'GET')
        self.assertIsNone(request.data)
        self.assertEqual(request.full_url, 'https://api.github.com/repos/Kyapya/english-dictionary/actions/workflows/validate.yml/runs?head_sha=' + SHA + '&event=push&per_page=100')
        self.assertFalse(request.has_header('Authorization'))
        self.assertEqual(kwargs, {'timeout': 30})

    def test_pending_states_then_success(self):
        states = ['requested', 'queued', 'pending', 'waiting', 'in_progress']
        self.observe([payload(record(status=s, conclusion=None)) for s in states] + [payload(record())], timeout=60)
        self.assertEqual(self.clock.sleeps, [10] * 5)
        self.assertTrue(all(r.get_method() == 'GET' and r.data is None for r, _ in self.requests))

    def test_pending_then_terminal_nonsuccess_is_not_retried(self):
        for conclusion in ['failure', 'cancelled', 'timed_out', 'skipped', 'neutral', 'action_required', 'stale', None]:
            with self.subTest(conclusion=conclusion), self.assertRaises(ValueError):
                self.observe([payload(record(status='in_progress', conclusion=None)),
                              payload(record(conclusion=conclusion)), payload(record())])
            self.assertEqual(len(self.requests), 2)
            self.assertEqual(self.clock.sleeps, [10])

    def test_pending_deadline_and_bounded_sleep_and_http_timeout(self):
        with self.assertRaisesRegex(ValueError, 'deadline'):
            self.observe([payload(record(status='queued', conclusion=None))], timeout=15)
        self.assertEqual(self.clock.sleeps, [10, 5])
        self.assertEqual([kw['timeout'] for _, kw in self.requests], [15, 5])
        self.assertEqual(self.clock.now, 15)

    def test_success_at_or_after_deadline_is_rejected(self):
        for elapsed in [15, 16]:
            with self.subTest(elapsed=elapsed), self.assertRaisesRegex(ValueError, 'deadline'):
                self.observe([payload(record())], timeout=15, elapsed=elapsed)
            self.assertEqual(len(self.requests), 1)
            self.assertEqual(self.clock.sleeps, [])

    def test_wrong_target_is_not_waited_for(self):
        for field, value in [('head_sha', 'b' * 40), ('head_branch', 'other'),
                             ('event', 'pull_request'), ('path', '.github/workflows/other.yml')]:
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'no ordinary'):
                self.observe([payload(record(**{field: value})), payload(record())])
            self.assertEqual(len(self.requests), 1)

    def test_newer_failed_run_or_attempt_cannot_reuse_success(self):
        for changes in [{'id': 2}, {'run_attempt': 2}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.observe([payload(record(), record(**changes, conclusion='failure'))])
            self.assertEqual(len(self.requests), 1)

    def test_newer_pending_attempt_is_waited_for_not_old_success(self):
        self.observe([payload(record(), record(run_attempt=2, status='queued', conclusion=None)),
                      payload(record(run_attempt=2))])
        self.assertEqual(len(self.requests), 2)

    def test_observed_identity_cannot_regress_to_old_success(self):
        with self.assertRaisesRegex(ValueError, 'regressed'):
            self.observe([payload(record(run_attempt=2, status='queued', conclusion=None)), payload(record())])

    def test_missing_malformed_and_unknown_states_fail_immediately(self):
        bad = [None, [], {}, {'workflow_runs': None}, payload(), payload(None),
               payload(record(id=None)), payload(record(id=True)), payload(record(run_attempt=0)),
               payload(record(status='unknown', conclusion=None)), payload(record(status='queued'))]
        missing_conclusion = record(status='queued'); del missing_conclusion['conclusion']
        missing_status = record(); del missing_status['status']
        bad += [payload(missing_conclusion), payload(missing_status)]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.observe([value, payload(record())])
            self.assertEqual(len(self.requests), 1)
            self.assertEqual(self.clock.sleeps, [])

    def test_http_json_and_network_errors_are_not_retried(self):
        for value in [urllib.error.HTTPError('url', 503, 'unavailable', {}, None),
                      urllib.error.URLError('offline'), TimeoutError(), '{invalid']:
            with self.subTest(value=value), self.assertRaises((ValueError, OSError)):
                self.observe([value, payload(record())])
            self.assertEqual(len(self.requests), 1)
            self.assertEqual(self.clock.sleeps, [])

    def test_invalid_sha_and_wait_configuration_never_fetch(self):
        for kwargs in [{'revision': 'main'}, {'timeout': 0}, {'timeout': float('inf')},
                       {'interval': 0}, {'interval': float('nan')}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.observe([payload(record())], **kwargs)
            self.assertEqual(self.requests, [])

    def test_one_shot_contract_still_rejects_pending(self):
        with self.assertRaises(ValueError):
            require_successful_validation(SHA, payload(record(status='queued', conclusion=None)))

    def test_failed_ci_prevents_planning_and_content_state_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); output = root / 'content'; output.mkdir()
            article = output / 'existing.json'; article.write_text('{"keep":true}')
            state = root / 'state.json'; state.write_text('{}')
            before = (article.read_bytes(), state.read_bytes())
            argv = ['sync_source.py', '--source', str(root / 'source'), '--output', str(output),
                    '--state', str(state), '--require-ci']
            with patch.object(sys, 'argv', argv), patch('sync_source.git', side_effect=[SHA, '']), \
                 patch('sync_source.verify_source_ci', side_effect=ValueError('CI failed')), \
                 patch('sync_source.plan_sync') as plan, patch('sync_source.write_json') as write:
                with self.assertRaisesRegex(ValueError, 'CI failed'): sync_source.main()
                plan.assert_not_called(); write.assert_not_called()
            self.assertEqual((article.read_bytes(), state.read_bytes()), before)
            self.assertEqual(list(output.iterdir()), [article])


if __name__ == '__main__': unittest.main()
