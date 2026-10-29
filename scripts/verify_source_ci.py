"""Fail closed unless the exact public source main revision passed ordinary CI."""
from __future__ import annotations

import json
import math
import re
import time
import urllib.request

SOURCE_REPOSITORY = 'Kyapya/english-dictionary'
WORKFLOW = '.github/workflows/validate.yml'
PENDING = {'queued', 'in_progress', 'waiting', 'pending', 'requested'}


def _latest_validation(revision: str, payload: dict) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get('workflow_runs'), list):
        raise ValueError('Malformed source validation response')
    runs = payload['workflow_runs']
    if any(not isinstance(run, dict) for run in runs):
        raise ValueError('Malformed source validation run')
    candidates = [run for run in runs
                  if run.get('head_sha') == revision and run.get('head_branch') == 'main'
                  and run.get('event') == 'push' and run.get('path') == WORKFLOW]
    if not candidates:
        raise ValueError('Exact source main revision has no ordinary validation run')
    for run in candidates:
        if any(type(value) is not int or value < 1
               for value in (run.get('id'), run.get('run_attempt', 1))):
            raise ValueError('Malformed source validation identity')
    return max(candidates, key=lambda run: (run['id'], run.get('run_attempt', 1)))


def require_successful_validation(revision: str, payload: dict) -> None:
    latest = _latest_validation(revision, payload)
    if latest.get('status') != 'completed' or latest.get('conclusion') != 'success':
        raise ValueError('Latest ordinary source validation is not successful; retaining published site')


def verify_source_ci(revision: str, *, timeout: float = 300, interval: float = 10,
                     sleep=time.sleep, monotonic=time.monotonic) -> None:
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Immutable source SHA required for CI verification')
    if not math.isfinite(timeout) or timeout <= 0 or not math.isfinite(interval) or interval <= 0:
        raise ValueError('Positive finite CI wait timeout and interval required')
    # Public GET only: no token, secret, workflow retry, or source code execution.
    url = (f'https://api.github.com/repos/{SOURCE_REPOSITORY}/actions/workflows/'
           f'validate.yml/runs?head_sha={revision}&event=push&per_page=100')
    request = urllib.request.Request(url, method='GET', headers={'Accept': 'application/vnd.github+json',
                                                               'User-Agent': 'KyapyaTango-direct-source-sync'})
    deadline = monotonic() + timeout
    observed = None
    while monotonic() < deadline:
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        # HTTP/JSON errors remain terminal; only observed pending CI is polled.
        with urllib.request.urlopen(request, timeout=min(30, remaining)) as response:
            payload = json.load(response)
        if monotonic() >= deadline:
            break
        latest = _latest_validation(revision, payload)
        identity = (latest['id'], latest.get('run_attempt', 1))
        if observed is not None and identity < observed:
            raise ValueError('Source validation identity regressed; retaining published site')
        observed = identity
        if latest.get('status') == 'completed':
            require_successful_validation(revision, payload)
            if monotonic() >= deadline:
                break
            return
        if latest.get('status') not in PENDING or 'conclusion' not in latest or latest['conclusion'] is not None:
            raise ValueError('Unknown or malformed source validation state; retaining published site')
        sleep(min(interval, max(0, deadline - monotonic())))
    raise ValueError('Exact source validation did not succeed before deadline; retaining published site')
