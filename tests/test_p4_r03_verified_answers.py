"""Exercise the real Local analytics route with generated data and no inference worker."""

import io
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from backend import ai_context, ai_provider, main, quality, resource_policy, storage


ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, 'path', [str(ROOT / 'desktop'), *sys.path]):
    from offline_analytics_cases import CASES


class VerifiedAnswersTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def import_frame(self, frame):
        stream = io.StringIO()
        frame.to_csv(stream, index=False)
        response = self.client.post('/api/projects', files={'file': ('synthetic.csv', stream.getvalue(), 'text/csv')})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['id']

    def ask(self, project, question, **kwargs):
        response = self.client.post(f'/api/projects/{project}/ai/insight', json={
            'question': question, 'selected_provider': 'local', **kwargs,
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_five_benchmark_answers_are_computed_through_the_api(self):
        clean = pd.DataFrame({name: range(80) for name in ['id', 'x', 'y', 'z', 'premium']})
        complete = self.import_frame(clean)
        varied = clean.assign(premium=[None] * 7 + list(range(73)), outcome=['Yes'] * 12 + ['No'] * 48 + [None] * 20)
        incomplete = self.import_frame(varied)
        answers = (
            (complete, 'Report the dataset dimensions and quality counts', CASES[0][3]),
            (incomplete, 'Positive rate for "outcome" = "Yes"', CASES[1][3]),
            (incomplete, 'Why are values missing in "premium"?', CASES[2][3]),
            (complete, 'Report whether training started and the validation score', CASES[3][3]),
            (complete, (' \n' * 400) + 'What is the dataset overview?', CASES[0][3]),
        )
        dataset = Path(storage.get_project(incomplete)['dataset_path'])
        before = dataset.read_bytes()
        with (patch.object(resource_policy, 'read_policy', return_value={'mode': 'low_memory'}),
              patch.object(resource_policy, '_physical_memory_bytes', return_value=(8 * 1024**3, int(0.73 * 1024**3), 'synthetic')),
              patch.object(ai_context, 'build', side_effect=AssertionError('Loaded provider context')),
              patch.object(ai_provider, 'respond', side_effect=AssertionError('Entered provider routing'))):
            preflight = self.client.get('/api/resource/preflight', params={'operation': 'local_inference'})
            self.assertEqual(preflight.status_code, 200, preflight.text)
            self.assertEqual(preflight.json()['decision'], 'defer')
            for project, question, expected in answers:
                with self.subTest(question=question.strip()):
                    result = self.ask(project, question)
                    self.assertEqual(result['facts'], expected)
                    self.assertEqual(result['source'], 'local_computed_rules')
                    self.assertEqual(result['local_status'], 'not_requested')
                    self.assertEqual(result['dataset_version'], 0)
                    self.assertTrue(result['answer'])
        self.assertEqual(dataset.read_bytes(), before)
        self.assertEqual(storage.recent_experiments(complete), [])

    def test_unknown_column_and_label_do_not_invent_a_rate_or_count(self):
        project = self.import_frame(pd.DataFrame({'id': range(3), 'outcome': ['Yes', 'No', None]}))
        for question in ('Positive rate for "outcome" = "YES"', 'Why are values missing in "other"?'):
            result = self.ask(project, question)
            self.assertEqual(result['facts'], {})
            self.assertIn('Use an', result['answer'])

    def test_grouped_missingness_and_denominators_on_owner_smoke_csv(self):
        project = self.import_frame(pd.DataFrame({
            'id': [1, 2, 3, 4], 'outcome': ['Yes', 'No', 'Yes', None], 'premium': [20, None, 40, 50],
        }))
        dataset = Path(storage.get_project(project)['dataset_path'])
        before = dataset.read_bytes()
        with (patch.object(ai_context, 'build', side_effect=AssertionError('Loaded provider context')),
              patch.object(ai_provider, 'respond', side_effect=AssertionError('Entered provider routing'))):
            result = self.ask(project, 'Which outcomes have the most missing premiums?')
            self.assertEqual(result['analysis']['operation'], 'grouped_missingness')
            self.assertEqual((result['analysis']['measure'], result['analysis']['group_by']), ('premium', 'outcome'))
            self.assertEqual(result['facts']['groups'], [
                {'group': 'No', 'matching_rows': 1, 'missing_rows': 1, 'percent': 100},
                {'group': 'Yes', 'matching_rows': 2, 'missing_rows': 0, 'percent': 0},
            ])
            self.assertEqual(result['facts']['blank_group'],
                             {'group': None, 'matching_rows': 1, 'missing_rows': 0, 'percent': 0})
            for question, basis, denominator, percent in (
                ('What percentage of labelled outcomes are Yes?', 'labelled', 3, 66.6667),
                ('What percentage of all rows have a Yes outcome?', 'all_rows', 4, 50),
            ):
                with self.subTest(question=question):
                    result = self.ask(project, question)
                    self.assertEqual(result['analysis']['measure'], 'outcome')
                    self.assertEqual(result['analysis']['filter_value'], 'Yes')
                    self.assertEqual(result['analysis']['denominator'], basis)
                    self.assertEqual(result['facts'], {'positives': 2, 'denominator': denominator, 'percent': percent})
            for question, text in (
                ('What percent of outcomes are Yes?', 'all rows or only labelled rows'),
                ('Why are premiums missing?', 'The cause is unknown'),
                ('Show every record in the dataset', 'could not interpret'),
            ):
                self.assertIn(text, self.ask(project, question)['answer'])
        self.assertEqual(dataset.read_bytes(), before)
        self.assertEqual(quality.current_version(project), 0)
        self.assertEqual(storage.recent_experiments(project), [])

    def test_follow_up_changes_only_one_filter_for_the_same_version(self):
        data = pd.DataFrame({'stage': ['Opened', 'Closed', 'Opened', None], 'net_cost': [0, None, 90, 70]})
        project = self.import_frame(data)
        peer = self.import_frame(data)
        first = self.ask(project, 'Calculate the median net cost for Opened stages.')
        self.assertEqual(first['analysis']['operation'], 'median')
        self.assertEqual(first['analysis']['measure'], 'net_cost')
        self.assertEqual(first['analysis']['filter_column'], 'stage')
        self.assertEqual(first['analysis']['filter_value'], 'Opened')
        self.assertEqual(first['facts'], {'value': 45, 'matching_rows': 2, 'usable_rows': 2, 'excluded_rows': 0})
        previous = first['follow_up']
        follow = self.ask(project, 'How about closed?', local_follow_up=previous)
        self.assertEqual(follow['analysis'], {**first['analysis'], 'filter_value': 'Closed'})
        self.assertEqual(follow['facts'], {'value': None, 'matching_rows': 1, 'usable_rows': 0, 'excluded_rows': 1})
        self.assertIsNone(follow['follow_up'])
        self.assertEqual(quality.restore(project, target_version=0, expected_version=0)['version'], 1)
        for target, context in ((peer, previous), (project, previous), (project, None)):
            result = self.ask(target, 'What about Closed?', local_follow_up=context)
            self.assertIn('Which calculation', result['answer'])
            self.assertIsNone(result['analysis'])
            self.assertEqual(result['facts'], {})

    def test_held_out_schema_paraphrases_and_ambiguous_short_names(self):
        project = self.import_frame(pd.DataFrame({
            'claim status': ['In review', 'Paid', 'Paid', '(Missing)', None],
            'insured cost': [0, 80, None, 30, 50], 'actual cost': [None, 60, 10, 20, 40],
        }))
        checks = (
            ('Show missing values in "insured cost" grouped by claim status', 'grouped_missingness', 'insured cost', 'claim status'),
            ('Show the average insured cost by "claim status"', 'mean', 'insured cost', 'claim status'),
            ('How many records are there where "claim status" is "In review"?', 'count', None, None),
            ('Share of all records with an "In review" claim status', 'rate', 'claim status', None),
        )
        answers = []
        for question, op, measure, group in checks:
            with self.subTest(question=question):
                result = self.ask(project, question)
                self.assertEqual((result['analysis']['operation'], result['analysis']['measure'],
                                  result['analysis']['group_by']), (op, measure, group))
                answers.append(result)
        self.assertEqual(answers[0]['facts']['groups'][0],
                         {'group': 'Paid', 'matching_rows': 2, 'missing_rows': 1, 'percent': 50})
        self.assertEqual(answers[1]['facts']['blank_group']['value'], 50)
        self.assertEqual({group['group']: group['value'] for group in answers[1]['facts']['groups']},
                         {'In review': 0, 'Paid': 80, '(Missing)': 30})
        self.assertEqual(answers[2]['facts']['matching_rows'], 1)
        self.assertEqual(answers[3]['facts'], {'positives': 1, 'denominator': 5, 'percent': 20})
        ambiguous = self.ask(project, 'Count missing costs by claim status')
        self.assertIsNone(ambiguous['analysis'])
        self.assertIn("Possible columns include 'insured cost', 'actual cost'", ambiguous['answer'])
        self.assertIsNone(self.ask(project, 'Median claim status')['analysis'])
        self.assertIsNone(self.ask(project, 'Median insured cost for Rejected claim status')['analysis'])

    def test_training_status_uses_execution_evidence_and_current_project_version(self):
        frame = pd.DataFrame({'id': range(4), 'value': range(4)})
        project = self.import_frame(frame)
        peer = self.import_frame(frame)
        stale = storage.new_experiment(project, {'quality_version': 1})
        other = storage.new_experiment(peer, {'quality_version': 0})
        self.assertTrue(storage.claim_queued_experiment(stale))
        self.assertTrue(storage.claim_queued_experiment(other))
        pending = storage.new_experiment(project, {'quality_version': 0})
        self.assertEqual(storage.request_training_cancel(pending), 'cancelled')
        question = 'Has training started?'
        self.assertEqual(self.ask(project, question)['facts'], {'training_started': False, 'validation_score': None})

        legacy = storage.new_experiment(project, {})
        self.assertTrue(storage.claim_queued_experiment(legacy))
        self.assertEqual(self.ask(project, question)['facts'], {'training_started': True, 'validation_score': None})
        storage.finish_running_experiment(legacy, 'completed', results={
            'primary_metric': 'Accuracy', 'models': [{'key': 'chosen', 'status': 'ready', 'cv_metric': .75}],
        })
        storage.select_model(legacy, 'chosen', {})
        self.assertEqual(self.ask(project, question)['facts'], {'training_started': True, 'validation_score': .75})

    def test_explicit_model_requests_keep_provider_routing(self):
        project = self.import_frame(pd.DataFrame({'id': range(4), 'value': range(4)}))
        model_result = {'answer': 'Model answer', 'fallback': False}
        with (patch.object(ai_provider, 'respond', return_value=model_result) as respond,
              patch.object(main.verified_answers, 'answer', side_effect=AssertionError('Computed rules after model success')),
              patch.object(quality, '_materialize', wraps=quality._materialize) as materialize):
            result = self.ask(project, 'What is the dataset overview?', selected_provider='ollama')
        self.assertEqual(result['answer'], 'Model answer')
        self.assertFalse(result['fallback'])
        self.assertNotIn('facts', result)
        respond.assert_called_once()
        self.assertEqual(materialize.call_count, 1, 'A provider request should materialize one working version')

    def test_offline_model_deferral_preserves_the_verified_filtered_answer(self):
        project = self.import_frame(pd.DataFrame({
            'outcome': ['Yes', 'No', 'Yes', None], 'premium': [20, None, 40, 50],
        }))
        dataset = Path(storage.get_project(project)['dataset_path'])
        before = dataset.read_bytes()
        question = 'What is the median premium for Yes outcomes?'
        verified = self.ask(project, question)
        with (patch.object(resource_policy, 'read_policy', return_value={'mode': 'low_memory'}),
              patch.object(resource_policy, '_physical_memory_bytes', return_value=(8 * 1024**3, int(0.936 * 1024**3), 'synthetic')),
              patch.object(ai_provider, '_read_config', return_value={**ai_provider.DEFAULTS, 'intelligence_mode': 'local'}),
              patch.object(ai_provider.bundled_inference, 'generate') as bundled,
              patch.object(ai_provider, '_call_ollama') as ollama,
              patch.object(ai_provider, '_call_provider') as cloud):
            result = self.ask(project, question, selected_provider='ollama')
            for call in (bundled, ollama, cloud):
                call.assert_not_called()
        self.assertTrue(result['fallback'])
        self.assertEqual(result['local_status'], 'resource_limited')
        self.assertEqual(result['provider'], 'local')
        self.assertIn('Low-memory', result['reason'])
        self.assertEqual(result['dataset_version'], 0)
        self.assertEqual(result['answer'], verified['answer'])
        self.assertEqual(result['facts'], {'value': 30, 'matching_rows': 2, 'usable_rows': 2, 'excluded_rows': 0})
        self.assertEqual(result['analysis'], verified['analysis'])
        self.assertEqual(dataset.read_bytes(), before)

    def test_provider_fallback_preserves_investigations_and_unrecognised_questions(self):
        project = self.import_frame(pd.DataFrame({'id': range(4), 'premium': [20, None, 40, 50]}))
        with patch.object(ai_provider, '_read_config', return_value={**ai_provider.DEFAULTS, 'local_model_enabled': False}):
            missing = self.ask(project, 'Why are premiums missing?', selected_provider='ollama')
            general = self.ask(project, 'What features should I investigate?', selected_provider='ollama')
        self.assertEqual(missing['investigation']['column'], 'premium')
        self.assertTrue(missing['investigation_steps'])
        self.assertIn('Inspected 1 missing values in premium', missing['answer'])
        self.assertIn('Model choice depends on your confirmed target', general['answer'])
        self.assertNotIn('facts', general)

    def test_provider_context_keeps_its_findings_when_quality_advances(self):
        project = self.import_frame(pd.DataFrame({'id': range(4), 'premium': [20, None, 40, 50]}))
        issue = next(item for item in quality.snapshot(project)['issues'] if item['kind'] == 'missing')
        original_build = ai_context.build

        def build_after_imputation(*args, **kwargs):
            quality.approve_imputation(project, 'premium', issue['id'], expected_version=0)
            return original_build(*args, **kwargs)

        with patch.object(ai_provider, 'respond', return_value={'answer': 'Model answer'}) as respond:
            with patch.object(ai_context, 'build', side_effect=build_after_imputation):
                result = self.ask(project, 'What is the dataset overview?', selected_provider='ollama')
            sent = respond.call_args.args[0]
            self.assertEqual((result['dataset_version'], sent['dataset_version'], sent['missing_cells']), (0, 0, 1))
            self.assertIn({'kind': 'missing', 'column': 'premium', 'affected_rows': 1,
                           'decision': 'pending', 'severity': issue['severity']}, sent['quality_findings'])

            newer = self.ask(project, 'What is the dataset overview?', selected_provider='ollama')
            sent = respond.call_args.args[0]
            self.assertEqual((newer['dataset_version'], sent['dataset_version'], sent['missing_cells']), (1, 1, 0))
            self.assertFalse(any(item['kind'] == 'missing' for item in sent['quality_findings']))

    def test_qa_candidate_floor_requires_the_isolated_desktop_profile(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {
            'PILOTODIN_R03_BENCHMARK': 'candidate', 'PILOTODIN_DESKTOP_SESSION': 'qa-test',
        }), patch.object(resource_policy.sys, 'platform', 'win32'):
            root = Path(tmp)
            candidate = root / 'com.pilotodin.p4r03benchmark' / 'data' / 'candidate'
            for home, floor in ((root, 2.0), (candidate, 1.5)):
                with self.subTest(floor=floor), patch.object(storage, 'HOME', home), patch.object(
                    resource_policy, '_physical_memory_bytes', return_value=(8 * 1024**3, 1536 * 1024**2, 'test'),
                ):
                    resource_policy.save_policy('low_memory')
                    decision = resource_policy.admit_new_work('local_inference')
                    self.assertEqual(decision['decision'], 'allow' if floor == 1.5 else 'defer')
                    self.assertEqual(decision['required_free_gib'], floor)
                    self.assertEqual(resource_policy.status()['low_memory_local_inference_min_free_gib'], floor)
                    self.assertEqual(resource_policy.admit_new_work('training')['required_free_gib'], 0.75)
                    resource_policy.record_r03_event('desktop_preflight', **decision)
                    self.assertEqual((home / 'r03-benchmark.jsonl').exists(), floor == 1.5)
            with patch.object(storage, 'HOME', candidate), patch.dict(os.environ, {'PILOTODIN_DESKTOP_SESSION': ''}):
                self.assertEqual(resource_policy._minimum_free_gib('local_inference'), 2.0)
            baseline = candidate.with_name('baseline')
            with patch.object(storage, 'HOME', baseline), patch.dict(os.environ, {'PILOTODIN_R03_BENCHMARK': 'baseline'}):
                self.assertEqual(resource_policy._r03_profile(), 'baseline')
                self.assertEqual(resource_policy._minimum_free_gib('local_inference'), 2.0)

    def test_qa_records_distinct_preflight_and_generation_observations(self):
        project = self.import_frame(pd.DataFrame({'premium': [10, None, 30, 40], 'outcome': ['Yes', 'No', 'Yes', 'No']}))
        headers = {'Origin': 'http://tauri.localhost', 'X-PilotODIN-Session': 'qa-test'}
        prompt = 'What is the dataset overview?'
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {
            'PILOTODIN_R03_BENCHMARK': 'candidate', 'PILOTODIN_DESKTOP_SESSION': 'qa-test',
        }), patch.object(resource_policy.sys, 'platform', 'win32'):
            home = Path(tmp) / 'com.pilotodin.p4r03benchmark' / 'data' / 'candidate'
            with patch.object(storage, 'HOME', home), patch.object(
                ai_provider, '_read_config', return_value={**ai_provider.DEFAULTS, 'intelligence_mode': 'local'},
            ), patch.object(resource_policy, '_physical_memory_bytes', side_effect=[
                (8 * 1024**3, 1536 * 1024**2, 'test'), (8 * 1024**3, 1536 * 1024**2 - 4096, 'test'),
            ]), patch.object(ai_provider.bundled_inference, 'generate') as generate:
                resource_policy.save_policy('low_memory')
                preflight = self.client.get('/api/resource/preflight', headers=headers, params={
                    'operation': 'local_inference', 'insight_context': 'assistant', 'selected_provider': 'ollama',
                })
                self.assertEqual(preflight.json()['decision'], 'allow')
                result = self.client.post(f'/api/projects/{project}/ai/insight', headers=headers, json={
                    'question': prompt, 'selected_provider': 'ollama',
                })
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.json()['local_status'], 'resource_limited')
                generate.assert_not_called()
            log_text = (home / 'r03-benchmark.jsonl').read_text(encoding='utf-8')
        preflight, generation, result = map(json.loads, log_text.splitlines())
        self.assertEqual([preflight['stage'], generation['stage'], result['stage']],
                         ['desktop_preflight', 'before_generation', 'insight_result'])
        self.assertEqual((preflight['decision'], preflight['available_gib']), ('allow', 1.50))
        self.assertEqual((generation['decision'], generation['code']), ('defer', 'low_memory_headroom'))
        self.assertEqual(generation['available_gib'], generation['required_free_gib'])
        self.assertEqual(preflight['available_bytes'], 1536 * 1024**2)
        self.assertEqual(generation['available_bytes'], preflight['available_bytes'] - 4096)
        self.assertEqual(result['provider'], 'local')
        for private in (prompt, project, headers['X-PilotODIN-Session']):
            self.assertNotIn(private, log_text)


if __name__ == '__main__':
    unittest.main()
