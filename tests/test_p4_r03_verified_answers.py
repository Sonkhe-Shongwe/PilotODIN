"""Exercise the real Local analytics route with generated data and no inference worker."""

import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from backend import ai_context, ai_provider, main, resource_policy, storage


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
        with patch.object(ai_provider, 'respond', return_value={'answer': 'Model answer'}) as respond:
            result = self.ask(project, 'What is the dataset overview?', selected_provider='ollama')
        self.assertEqual(result['answer'], 'Model answer')
        respond.assert_called_once()


if __name__ == '__main__':
    unittest.main()
