"""Run the Ask ODIN smoke workload on an already running Live Dev backend."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
API = 'http://127.0.0.1:8000/api'
FIXTURE = [
    {'id': '1', 'outcome': 'Yes', 'premium': 20},
    {'id': '2', 'outcome': 'No', 'premium': None},
    {'id': '3', 'outcome': 'Yes', 'premium': 40},
    {'id': '4', 'outcome': None, 'premium': 50},
]
CASES = (
    ('grouped_missingness', 'Which outcomes have the most missing premiums?', 'grouped_missingness',
     {'groups': [
         {'group': 'No', 'matching_rows': 1, 'missing_rows': 1, 'percent': 100},
         {'group': 'Yes', 'matching_rows': 2, 'missing_rows': 0, 'percent': 0},
     ], 'blank_group': {'group': None, 'matching_rows': 1, 'missing_rows': 0, 'percent': 0}},
     {'measure': 'premium', 'group_by': 'outcome'}),
    ('labelled_rate', 'What percentage of labelled outcomes are Yes?', 'rate',
     {'positives': 2, 'denominator': 3, 'percent': 66.6667},
     {'measure': 'outcome', 'denominator': 'labelled', 'filter_value': 'Yes'}),
    ('all_rows_rate', 'What percentage of all rows have a Yes outcome?', 'rate',
     {'positives': 2, 'denominator': 4, 'percent': 50},
     {'measure': 'outcome', 'denominator': 'all_rows', 'filter_value': 'Yes'}),
    ('filtered_median', 'What is the median premium for Yes outcomes?', 'median',
     {'value': 30, 'matching_rows': 2, 'usable_rows': 2, 'excluded_rows': 0},
     {'measure': 'premium', 'filter_column': 'outcome', 'filter_value': 'Yes'}),
    ('filter_follow_up', 'What about No?', 'median',
     {'value': None, 'matching_rows': 1, 'usable_rows': 0, 'excluded_rows': 1},
     {'measure': 'premium', 'filter_column': 'outcome', 'filter_value': 'No'}),
)


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(opener, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(API + path, data=data, headers={'Content-Type': 'application/json'} if data else {})
    with opener.open(req, timeout=10) as response:
        return json.load(response)


def insist(condition, message: str) -> None:
    if not condition:
        raise ValueError(message)


def checkout() -> dict:
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(
        ['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True,
    )
    return {'checkout_git_sha': sha, 'checkout_tracked_changes': bool(status.strip())}


def measure(opener, path: str) -> list[dict]:
    checks = []
    follow_up = None
    for name, question, operation, facts, fields in CASES:
        body = {'context': 'assistant', 'selected_provider': 'local', 'question': question}
        if name == 'filter_follow_up':
            insist(follow_up is not None, 'The median response did not provide follow-up context.')
            body['local_follow_up'] = follow_up
        started = perf_counter()
        answer = request(opener, path + '/ai/insight', body)
        elapsed = round((perf_counter() - started) * 1000, 1)
        insist(answer.get('dataset_version') == 0, f'{name}: select the unedited four-row fixture at working version 0.')
        insist(answer.get('source') == 'local_computed_rules' and answer.get('local_status') == 'not_requested',
               f'{name}: expected a Local analytics answer without inference.')
        plan = answer.get('analysis') or {}
        insist(plan.get('operation') == operation and all(plan.get(key) == value for key, value in fields.items()),
               f'{name}: unexpected interpretation. Check the checkout and restart both Live Dev consoles.')
        insist(answer.get('facts') == facts, f'{name}: unexpected aggregate result.')
        follow_up = answer.get('follow_up')
        checks.append({'case': name, 'http_round_trip_ms': elapsed})
    insist(follow_up is None, 'The single follow-up should consume the carried context.')
    return checks


def run(project_name: str) -> dict:
    source = checkout()
    opener = build_opener(ProxyHandler({}), NoRedirects())
    matches = [item['id'] for item in request(opener, '/projects') if item['name'] == project_name]
    insist(len(matches) == 1, 'Expected one matching project. Pass the exact name of your existing smoke project.')
    project_id = matches[0]
    insist(re.fullmatch(r'[0-9a-f]{32}', project_id), 'Unexpected project identifier.')
    path = f'/projects/{project_id}'
    profile = request(opener, path)['profile']
    columns = [column['name'] for column in profile['columns']]
    insist(profile['rows'] == 4 and columns == ['id', 'outcome', 'premium'] and profile['preview'] == FIXTURE,
           'The selected project does not match the four-row synthetic acceptance fixture.')
    before = request(opener, '/resource/status')['memory']
    checks = measure(opener, path)
    after = request(opener, '/resource/status')['memory']
    return {
        'status': 'PASS',
        'scope': 'live_dev_loopback_api',
        **source,
        'checks': checks,
        'system_memory_before': before,
        'system_memory_after': after,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', nargs='?', default='r03-local-answers', help='Existing four-row Live Dev project name')
    args = parser.parse_args()
    try:
        result = run(args.project)
    except HTTPError as error:
        print(f'Live Dev check failed with HTTP {error.code}. Check that the development backend is running.', file=sys.stderr)
        return 1
    except (URLError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Live Dev check failed: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
