#!/usr/bin/env python3
"""Request and verify the existing branch Pages build for one exact commit.

Uses only the current repository's temporary GITHUB_TOKEN. Never changes Pages
settings, creates credentials, deploys an artifact, or retries a mutating request.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request

API = 'https://api.github.com/repos/Kyapya/KyapyaTango'
ACTIVE = {'queued', 'building'}


class PagesError(RuntimeError):
    pass


class PagesClient:
    def __init__(self, token: str):
        if not token:
            raise PagesError('GITHUB_TOKEN is required for the approved Pages build')
        self.token = token

    def request(self, method: str, path: str) -> dict:
        # Fixed host/repository/endpoints; never forward credentials to returned URLs.
        allowed = {('GET', '/pages'), ('GET', '/pages/builds/latest'),
                   ('GET', '/git/ref/heads/main'), ('POST', '/pages/builds')}
        if (method, path) not in allowed:
            raise PagesError('Unsupported Pages operation')
        request = urllib.request.Request(API + path, method=method,
            data=b'{}' if method == 'POST' else None,
            headers={'Accept': 'application/vnd.github+json',
                     'Authorization': 'Bearer ' + self.token,
                     'Content-Type': 'application/json',
                     'User-Agent': 'KyapyaTango-branch-pages-sync'})
        # No redirects: a moved repository requires operator review, not token forwarding.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            return json.load(response)


def require_current_head(client, commit: str) -> None:
    if client.request('GET', '/git/ref/heads/main').get('object', {}).get('sha') != commit:
        raise PagesError('Publication commit superseded on main; refusing stale build/success')


def latest_build(client) -> dict:
    try:
        return client.request('GET', '/pages/builds/latest')
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {}
        raise


def publish(client, commit: str, *, timeout: float = 900, sleep=time.sleep,
            monotonic=time.monotonic) -> str:
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise PagesError('An immutable full publication commit SHA is required')
    if timeout <= 0:
        raise PagesError('A positive verification timeout is required')
    require_current_head(client, commit)
    site = client.request('GET', '/pages')
    if site.get('build_type') != 'legacy' or site.get('source') != {'branch': 'main', 'path': '/'}:
        raise PagesError('Pages publishing mode/source changed; no settings will be modified')
    latest = latest_build(client)
    require_current_head(client, commit)
    if latest.get('commit') == commit and latest.get('status') == 'built':
        return 'already-built'
    # Resume a previously accepted request rather than create duplicate builds.
    active = latest.get('commit') == commit and latest.get('status') in ACTIVE
    uncertain = False
    previous_failed = latest.get('commit') == commit and latest.get('status') == 'errored'
    previous_identity = (latest.get('url'), latest.get('created_at'))
    build_started = active
    if not active:
        try:
            client.request('POST', '/pages/builds')
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                raise PagesError(f'Pages build request rejected (HTTP {exc.code}); not retried') from exc
            uncertain = True
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            # Acceptance is unknown. Observe only; never replay this POST.
            uncertain = True
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        require_current_head(client, commit)
        try:
            latest = latest_build(client)
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504}:
                raise
            sleep(min(10, max(0, deadline - monotonic())))
            continue
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            sleep(min(10, max(0, deadline - monotonic())))
            continue
        if latest.get('commit') == commit:
            identity = (latest.get('url'), latest.get('created_at'))
            if latest.get('status') in ACTIVE:
                build_started = True
            if latest.get('status') == 'built':
                require_current_head(client, commit)
                return 'built'
            if latest.get('status') == 'errored' and (not previous_failed or build_started or identity != previous_identity):
                raise PagesError('Exact publication commit Pages build failed; not retried')
        # A built/queued older commit is not evidence that this request completed.
        sleep(min(10, max(0, deadline - monotonic())))
    suffix = ' (POST acceptance uncertain)' if uncertain else ''
    raise PagesError('Exact-commit Pages build not confirmed before deadline' + suffix)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--timeout', type=float, default=900)
    args = parser.parse_args()
    status = publish(PagesClient(os.environ.get('GITHUB_TOKEN', '')), args.commit, timeout=args.timeout)
    print(json.dumps({'repository': 'Kyapya/KyapyaTango', 'commit': args.commit, 'pages': status}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
