"""Fail closed unless the exact public source main revision passed ordinary CI."""
from __future__ import annotations

import json
import re
import urllib.request

SOURCE_REPOSITORY = 'Kyapya/english-dictionary'
WORKFLOW = '.github/workflows/validate.yml'


def require_successful_validation(revision: str, payload: dict) -> None:
    candidates = [run for run in payload.get('workflow_runs', [])
                  if run.get('head_sha') == revision and run.get('head_branch') == 'main'
                  and run.get('event') == 'push' and run.get('path') == WORKFLOW]
    if not candidates:
        raise ValueError('Exact source main revision has no ordinary validation run')
    latest = max(candidates, key=lambda run: (run['id'], run.get('run_attempt', 1)))
    if latest.get('status') != 'completed' or latest.get('conclusion') != 'success':
        raise ValueError('Latest ordinary source validation is not successful; retaining published site')


def verify_source_ci(revision: str) -> None:
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Immutable source SHA required for CI verification')
    # Public read only: no token, secret, extra scope, or source code execution.
    url = (f'https://api.github.com/repos/{SOURCE_REPOSITORY}/actions/workflows/'
           f'validate.yml/runs?head_sha={revision}&event=push&per_page=100')
    request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json',
                                                 'User-Agent': 'KyapyaTango-direct-source-sync'})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    require_successful_validation(revision, payload)
