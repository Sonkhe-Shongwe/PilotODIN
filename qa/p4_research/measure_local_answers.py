"""Measure the verified-answers API test process using disposable generated data."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'desktop'), str(ROOT / 'tests')]


def memory() -> dict:
    if sys.platform == 'win32':
        from verify_live_bundled_inference import worker_memory

        return worker_memory(os.getpid())

    import resource

    return {'cumulative_peak_working_set_mib': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}


def main() -> int:
    if sys.platform not in ('win32', 'linux'):
        raise SystemExit('Measure the local answers on Windows or Linux.')
    before_import = memory()
    with TemporaryDirectory(prefix='pilotodin-r03-answers-') as home, patch.dict(os.environ, {
        'PILOTODIN_HOME': home, 'PILOTODIN_DESKTOP_SESSION': '',
    }):
        from test_p4_r03_verified_answers import VerifiedAnswersTests
        from backend.resource_policy import memory_status

        before_workload = memory()
        host_memory = memory_status()
        started = perf_counter()
        suite = unittest.TestSuite([VerifiedAnswersTests('test_five_benchmark_answers_are_computed_through_the_api')])
        result = unittest.TextTestRunner().run(suite)
        elapsed = perf_counter() - started
        after_workload = memory()
        loaded_modelling = sorted({'sklearn', 'scipy'} & sys.modules.keys())
        passed = result.wasSuccessful() and result.testsRun == 1 and not loaded_modelling
        print('R03 LOCAL ANSWERS PROFILE: ' + json.dumps({
            'platform': sys.platform, 'scope': 'synthetic_in_process_http_api',
            'host_total_gib': host_memory['total_gib'], 'host_available_gib': host_memory['available_gib'],
            'before_import': before_import, 'before_workload': before_workload, 'after_workload': after_workload,
            'elapsed_seconds': round(elapsed, 3), 'simulated_available_gib': 0.73,
            'expected_scenarios': 5, 'passed': passed, 'modelling_imports': loaded_modelling,
        }, sort_keys=True))
        return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
