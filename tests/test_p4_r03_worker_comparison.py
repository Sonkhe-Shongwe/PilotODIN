"""Synthetic checks for the hosted worker comparison, with no assets or Windows calls."""

import contextlib
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, 'path', [str(ROOT / 'desktop'), *sys.path]):
    import verify_live_bundled_inference as probe


def profile(resident=2000, commit=1050, long_tokens=900, pass_answers=True):
    cases = []
    for name, prompt_tokens in (('overview', 100), ('long_context_overview', long_tokens)):
        cases.append({'case': name, 'passed': pass_answers, 'prompt_tokens': prompt_tokens,
                      'cumulative_peak_working_set_mib': resident, 'cumulative_peak_commit_mib': commit})
    return {'cases': cases, 'idle_release': {'status': 'passed'}}


class WorkerComparisonTests(unittest.TestCase):
    def test_desktop_model_verification_allocates_its_hash_buffer_on_the_heap(self):
        desktop = (ROOT / 'frontend/src-tauri/src/lib.rs').read_text(encoding='utf-8')
        verifier = desktop.split('fn verify_bundled_model(', 1)[1].split('\n}', 1)[0]
        self.assertIn('let mut chunk = vec![0u8; 1024 * 1024];', verifier)

    def test_recommends_a_lower_peak_only_when_answer_and_prompt_checks_pass(self):
        result = probe.compare_worker_profiles(profile(), profile(resident=1850, commit=1000))
        self.assertEqual(result['result'], 'candidate_for_physical_retest')
        self.assertEqual(result['resident_mib_saved'], 150)
        self.assertEqual(result['commit_mib_saved'], 50)
        self.assertEqual(result['answers_correct'], {'baseline': 2, 'reduced': 2})

    def test_retains_baseline_when_measurement_or_quality_is_insufficient(self):
        for baseline, reduced in (
            (profile(), profile(resident=2000)),
            (profile(), profile(resident=1800, commit=1100)),
            (profile(), profile(resident=1800, pass_answers=False)),
            (profile(), profile(resident=1800, long_tokens=899)),
            (profile(long_tokens=512), profile(resident=1800, long_tokens=512)),
            (profile(long_tokens=1921), profile(resident=1800, long_tokens=1921)),
            (profile(long_tokens=None), profile(resident=1800, long_tokens=None)),
        ):
            with self.subTest(baseline=baseline, reduced=reduced):
                result = probe.compare_worker_profiles(baseline, reduced)
                self.assertEqual(result['result'], 'retain_current_profile')

    def test_both_profiles_run_even_if_idle_release_fails(self):
        baseline = profile()
        baseline['idle_release']['status'] = 'failed'
        self.assertEqual(self.run_comparison([baseline, profile(resident=1800)])[0], 1)

    def test_reports_both_profiles_if_one_worker_fails(self):
        status, report = self.run_comparison([RuntimeError('fixture failure'), profile(resident=1800)])
        self.assertEqual(status, 1)
        self.assertEqual(report['result'], 'comparison_incomplete')
        self.assertEqual(report['profiles']['baseline']['status'], 'failed')
        self.assertIn('cases', report['profiles']['reduced'])

    def test_completed_comparison_can_retain_baseline(self):
        status, report = self.run_comparison([profile(), profile(resident=1800, pass_answers=False)])
        self.assertEqual(status, 0)
        self.assertEqual(report['result'], 'retain_current_profile')

    def run_comparison(self, replies):
        options = object()
        output = io.StringIO()
        with (patch.object(probe, 'run_worker', side_effect=replies) as worker,
              contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO())):
            status = probe.run_memory_comparison(ROOT, options)
        self.assertEqual([call.kwargs for call in worker.call_args_list], [
            {'physical_batch': 512, 'check_idle': True}, {'physical_batch': 128, 'check_idle': False},
        ])
        return status, json.loads(output.getvalue().split(': ', 1)[1])

    def test_analytics_comparison_records_token_counts_and_omits_generated_text(self):
        replies = [(200, {'choices': [{'message': {'content': json.dumps(case[3])}, 'finish_reason': 'stop'}],
                          'usage': {'prompt_tokens': 100}}) for case in probe.CASES]
        overview = replies[0][1]
        replies.append((200, {**overview, 'usage': {'prompt_tokens': 900}}))
        with (patch.object(probe, 'send', side_effect=replies) as send,
              patch.object(probe, 'worker_memory', return_value={})):
            cases = probe.evaluate_analytics('http://127.0.0.1:12345', 'synthetic', 'model', 10,
                                             include_long_prompt=True)
        self.assertEqual(len(cases), len(probe.CASES) + 1)
        self.assertTrue(all(case['passed'] and 'answer' not in case for case in cases))
        self.assertEqual(cases[-1]['prompt_tokens'], 900)
        prompt = send.call_args.args[2]['messages'][1]['content']
        self.assertGreater(len(prompt), 4_000)
        self.assertIn('verified_facts', prompt)

    def test_worker_profiles_keep_model_context_and_idle_timeout_fixed_and_close_each_process(self):
        options = SimpleNamespace(memory_profile=False, analytics_eval=False, wording_eval=False,
                                  candidate=None)
        measurements = {'working_set_mib': 1800}
        replies = [(200, {'status': 'ok'}), (401, {}), (200, {'status': 'ok'}), (401, {})]
        with (TemporaryDirectory() as directory,
              patch.object(probe.subprocess, 'Popen') as launch,
              patch.object(probe, 'send', side_effect=replies),
              patch.object(probe, 'worker_memory', return_value=measurements),
              patch.object(probe, 'evaluate_analytics', return_value=profile()['cases']),
              patch.object(probe, 'verify_idle_release', return_value={'resident_mib_released': 1700}) as idle):
            root = Path(directory)
            launch.return_value.poll.side_effect = [None, 0, None, 0]
            baseline = probe.run_worker(root, options, physical_batch=512, check_idle=True)
            reduced = probe.run_worker(root, options, physical_batch=128)
            self.assertFalse((root / 'build' / 'offline-inference-startup.log').exists())
            self.assertEqual(launch.return_value.wait.call_count, 2)
            idle.assert_called_once()
        first, second = (call.args[0] for call in launch.call_args_list)
        for flag in ('--model', '--ctx-size', '--threads', '--sleep-idle-seconds'):
            self.assertEqual(first[first.index(flag) + 1], second[second.index(flag) + 1])
        self.assertEqual(first[first.index('--ubatch-size') + 1], '512')
        self.assertEqual(second[second.index('--ubatch-size') + 1], '128')
        self.assertEqual(baseline['idle_release']['status'], 'passed')
        self.assertNotIn('idle_release', reduced)


if __name__ == '__main__':
    unittest.main()
