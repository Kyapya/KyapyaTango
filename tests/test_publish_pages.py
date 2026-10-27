"""Offline publication safety tests: no live API mutation or credentials."""
from __future__ import annotations

from collections import deque
from pathlib import Path
import sys
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publish_pages import publish, PagesClient, PagesError

SHA = 'a' * 40
OTHER = 'b' * 40
SITE = {'build_type': 'legacy', 'source': {'branch': 'main', 'path': '/'}}


def build(commit=SHA, status='built', id=1):
    return {'commit': commit, 'status': status, 'url': f'https://api.github.com/repos/Kyapya/KyapyaTango/pages/builds/{id}', 'created_at': str(id)}


class Clock:
    now = 0
    def monotonic(self): return self.now
    def sleep(self, delay): self.now += delay


class FakeClient:
    def __init__(self, builds, heads=None, site=None, post_error=None):
        self.builds = deque(builds)
        self.heads = deque(heads or [SHA])
        self.site = site if site is not None else SITE
        self.calls = []; self.post_error = post_error
    def request(self, method, path):
        self.calls.append((method, path))
        if path == '/git/ref/heads/main':
            head = self.heads.popleft() if len(self.heads)>1 else self.heads[0]
            return {'object': {'sha': head}}
        if path == '/pages': return self.site
        if method == 'POST':
            if self.post_error: raise self.post_error
            return {'status':'queued'}
        value = self.builds.popleft() if len(self.builds)>1 else self.builds[0]
        if isinstance(value, Exception): raise value
        return value
    @property
    def posts(self): return sum(method=='POST' for method,_ in self.calls)


class PagesPublicationTests(unittest.TestCase):
    def run_publish(self, client, **kwargs):
        clock = Clock()
        return publish(client, SHA, sleep=clock.sleep, monotonic=clock.monotonic, timeout=kwargs.get('timeout', 30))

    def test_existing_exact_build_is_noop(self):
        client=FakeClient([build()])
        self.assertEqual(self.run_publish(client),'already-built'); self.assertEqual(client.posts,0)

    def test_requests_once_and_checks_exact_commit(self):
        client=FakeClient([build(OTHER),build(OTHER),build(status='queued'),build(status='building'),build(id=2)])
        self.assertEqual(self.run_publish(client,timeout=50),'built'); self.assertEqual(client.posts,1)

    def test_resume_active_build_without_duplicate_request(self):
        for status in ('queued','building'):
            client=FakeClient([build(status=status),build()])
            self.assertEqual(self.run_publish(client),'built'); self.assertEqual(client.posts,0)

    def test_older_success_never_counts_as_new_success(self):
        client=FakeClient([build(OTHER)])
        with self.assertRaisesRegex(PagesError,'not confirmed'): self.run_publish(client)
        self.assertEqual(client.posts,1)

    def test_main_advanced_before_start_prevents_request(self):
        client=FakeClient([build()],heads=[OTHER])
        with self.assertRaisesRegex(PagesError,'superseded'): self.run_publish(client)
        self.assertEqual(client.posts,0)

    def test_main_advanced_before_post_prevents_request(self):
        client=FakeClient([build(OTHER)],heads=[SHA,OTHER])
        with self.assertRaisesRegex(PagesError,'superseded'): self.run_publish(client)
        self.assertEqual(client.posts,0)

    def test_main_advanced_after_post_cannot_claim_success(self):
        client=FakeClient([build(OTHER),build(OTHER,id=2)],heads=[SHA,SHA,OTHER])
        with self.assertRaisesRegex(PagesError,'superseded'): self.run_publish(client)
        self.assertEqual(client.posts,1)

    def test_main_advanced_after_exact_build_cannot_claim_success(self):
        client=FakeClient([build(OTHER),build()],heads=[SHA,SHA,SHA,OTHER])
        with self.assertRaisesRegex(PagesError,'superseded'): self.run_publish(client)

    def test_existing_mode_or_branch_change_rejected_without_mutation(self):
        for site in ({'build_type':'workflow','source':SITE['source']},
                     {'build_type':'legacy','source':{'branch':'other','path':'/'}},
                     {'build_type':'legacy','source':{'branch':'main','path':'/docs'}}):
            client=FakeClient([build()],site=site)
            with self.assertRaisesRegex(PagesError,'settings'): self.run_publish(client)
            self.assertEqual(client.posts,0)

    def test_failed_build_does_not_report_success_or_retry(self):
        client=FakeClient([build(OTHER),build(status='errored')])
        with self.assertRaisesRegex(PagesError,'failed'): self.run_publish(client)
        self.assertEqual(client.posts,1)

    def test_previous_failed_same_commit_may_be_retried_once(self):
        client=FakeClient([build(status='errored'),build(status='errored'),build(status='building',id=2),build(id=2)])
        self.assertEqual(self.run_publish(client),'built'); self.assertEqual(client.posts,1)

    def test_new_failed_retry_is_terminal(self):
        client=FakeClient([build(status='errored'),build(status='errored',id=2)])
        with self.assertRaisesRegex(PagesError,'failed'): self.run_publish(client)
        self.assertEqual(client.posts,1)

    def test_uncertain_post_is_observed_not_replayed(self):
        for exc in (urllib.error.URLError('connection lost'),TimeoutError(),
                    urllib.error.HTTPError('url',502,'gateway',{},None)):
            client=FakeClient([build(OTHER),build(status='queued'),build()],post_error=exc)
            self.assertEqual(self.run_publish(client),'built'); self.assertEqual(client.posts,1)

    def test_uncertain_unobserved_post_fails_without_retry(self):
        client=FakeClient([build(OTHER)],post_error=TimeoutError())
        with self.assertRaisesRegex(PagesError,'uncertain'): self.run_publish(client)
        self.assertEqual(client.posts,1)

    def test_permission_rejection_fails_without_retry(self):
        client=FakeClient([build(OTHER)],post_error=urllib.error.HTTPError('url',403,'forbidden',{},None))
        with self.assertRaisesRegex(PagesError,'403'): self.run_publish(client)
        self.assertEqual(client.posts,1)

    def test_transient_poll_failure_only_retries_reads(self):
        client=FakeClient([build(OTHER),urllib.error.HTTPError('url',503,'unavailable',{},None),build()])
        self.assertEqual(self.run_publish(client),'built'); self.assertEqual(client.posts,1)

    def test_no_previous_build_and_invalid_commit(self):
        missing=urllib.error.HTTPError('url',404,'none',{},None)
        client=FakeClient([missing,build()])
        self.assertEqual(self.run_publish(client),'built'); self.assertEqual(client.posts,1)
        client=FakeClient([build()])
        with self.assertRaisesRegex(PagesError,'immutable'): publish(client,'main')
        self.assertEqual(client.calls,[])

    def test_client_rejects_unapproved_endpoints_and_absent_token(self):
        with self.assertRaises(PagesError): PagesClient('')
        client=PagesClient('test-only-not-a-credential')
        with patch('publish_pages.urllib.request.build_opener') as opener:
            for method,path in [('PATCH','/pages'),('POST','/pages'),('POST','/actions/workflows/sync-notion.yml/dispatches'),('GET','https://example.com')]:
                with self.assertRaisesRegex(PagesError,'Unsupported'): client.request(method,path)
            opener.assert_not_called()


if __name__=='__main__': unittest.main()
