import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import validation_witnesses as v


def font_fixture():
    return {'unit': {'state': 'PASS', 'expected': 9, 'executed': 9, 'failures': 0, 'errors': 0, 'skipped': 0},
            'baseline': {'exact': False, 'pixel_sha256': 'a'*64, 'reportlab_version': '4.5.1'},
            'corrected': {'exact': True, 'pixel_sha256': 'a'*64, 'reportlab_version': '4.5.1'},
            'actual': dict.fromkeys(('real_backend_report_pdf', 'legacy_default_report_preserved', 'unicode_title_narrative_table_chart',
                       'chart_metric_values_unchanged', 'immutable_revision_and_html', 'footer_and_pages', 'page_bounds'), True) | {'pages': 2},
            'context': dict.fromkeys(('paragraph_exact', 'vector_label_exact', 'one_page', 'page_bounds_ok'), True) | {'state': 'SCOPED_FONT_CONTEXT_IN_MEMORY_PASS'},
            'coverage': {'scope': 'DEVELOPER_PROBE_NOT_ACCEPTANCE', 'samples': {k: {'state': x} for k,x in v.COVERAGE.items()}},
            'research': {'state': 'RESEARCH_ONLY', 'baseline_matches': False, 'corrected_matches': True, 'same_rendered_pixels': True,
                         'product_acceptance': 'NOT_TESTED', 'visual_acceptance': 'NOT_TESTED'}}


def plan_fixture():
    return {'source_overlay': {'paths': [{}]*29}, 'stage_a': {'test_file': 'tests/a.py', 'expected_node_ids': ['test_'+str(n) for n in range(19)]},
            'stage_b': {'regular_modules': ['tests/r'+str(n)+'.py' for n in range(10)], 'contract_modules': ['tests/c'+str(n)+'.py' for n in range(3)],
                        'selected_nodes': ['tests/s.py::test_'+str(n) for n in range(6)]},
            'profiles': [{'id': platform+'-x64-cp311-source-test', 'wheels': [{'name': 'pypdfium2', 'native': [{'sha256': x*64}]}],
                          'application_bounds': {'archive_uses': 86, 'body_bytes': size}} for platform,x,size in [('windows','a',145308536),('linux','b',156575988)]]}


def terminal_fixture(plan, profile):
    names = ['tests/a.py::'+n for n in plan['stage_a']['expected_node_ids']]
    stage_a = {'profile': profile['id'], 'generation': 'c'*64, 'source': 'd'*40, 'stage': 'A', 'state': 'PASS', 'collected': names, 'passed': names[:],
               'failed': [], 'skipped': [], 'xfailed': [], 'native_sha256': profile['wheels'][0]['native'][0]['sha256'], 'pre_use_disposition_sha256': 'e'*64}
    b = plan['stage_b']; cases = {k: [k+'::test_case'] for k in b['regular_modules']+b['contract_modules']}
    cases.update({k: [k] for k in b['selected_nodes']})
    cases.update({'mixed:contract': ['contract.'+str(n) for n in range(3)], 'mixed:mixed': ['mixed.'+str(n) for n in range(9)],
                  'font:equivalence': list(v.FONT_NODES), 'frontend:compatibility': list(v.FRONTEND_NODES)})
    return {'profile': profile['id'], 'generation': 'c'*64, 'source': 'd'*40, 'attempt': 1, 'state': 'PASS', 'stage_a': stage_a,
            'stage_b': {k: {'collected': x, 'passed': x[:], 'state': 'PASS'} for k,x in cases.items()},
            'archive_uses': 86, 'requests': 86, 'body_bytes': profile['application_bounds']['body_bytes'], 'cleanup': 'OWNED_SCRATCH_REMOVED'}


class WitnessTest(unittest.TestCase):
    def test_live_gate(self):
        with patch.object(v, 'profile_inputs', side_effect=AssertionError('profile read')), self.assertRaisesRegex(ValueError, 'DISARMED'):
            v.stage_fonts(None, None, None, None, None)
        with self.assertRaisesRegex(ValueError, 'DISARMED'):
            v.font_mode('unit', '/not-owned')
        with self.assertRaisesRegex(ValueError, 'DISARMED'):
            v.mixed_witness(None, None, None, None)
        with self.assertRaisesRegex(ValueError, 'DISARMED'):
            v.frontend_witness(*([None]*10))

    def test_plan_pin_and_selectors(self):
        raw = json.dumps(plan_fixture()).encode()
        with self.assertRaisesRegex(ValueError, 'MANIFEST_PIN'):
            v.read_plan(raw)
        with patch.object(v, 'MANIFEST_PIN', v.blob(raw)):
            plan = v.read_plan(raw)
            a, b = v.stage_commands(plan, 'python')
            self.assertEqual(a[-1], 'tests/a.py'); self.assertEqual(len(b), 19)
            self.assertEqual([cmd[-1] for cmd in b], plan['stage_b']['regular_modules']+plan['stage_b']['contract_modules']+plan['stage_b']['selected_nodes'])

    def test_font_positive_and_historical_mapping(self):
        self.assertEqual(v.font_result(font_fixture())['passed'], list(v.FONT_NODES))
        self.assertEqual([k for k,x in v.COVERAGE.items() if x == 'MISMATCH'], ['emoji','mixed'])

    def test_font_refuses_missing_or_changed_evidence(self):
        for mode, field, bad in [('unit','skipped',1), ('baseline','exact',True), ('corrected','pixel_sha256','b'*64),
                                 ('actual','page_bounds',False), ('actual','pages',5), ('context','vector_label_exact',False),
                                 ('research','visual_acceptance','PASS')]:
            e = font_fixture(); e[mode][field] = bad
            with self.subTest(mode=mode, field=field), self.assertRaises(ValueError):
                v.font_result(e)
        e = font_fixture(); e['coverage']['samples']['emoji']['state'] = 'EXTRACTED_EXACT'
        with self.assertRaisesRegex(ValueError, 'FONT_COVERAGE_REGRESSION'):
            v.font_result(e)

    def test_stage_order_and_complete_receipts(self):
        plan = plan_fixture(); windows, linux = [terminal_fixture(plan,p) for p in plan['profiles']]
        v.linux_eligible(plan, windows, 'c'*64, 'd'*40, 'e'*64)
        v.final_eligible(plan, [windows,linux], 'c'*64, 'd'*40, 'e'*64)
        with self.assertRaises(ValueError):
            v.linux_eligible(plan, linux, 'c'*64, 'd'*40, 'e'*64)
        with self.assertRaises(ValueError):
            v.final_eligible(plan, [linux,windows], 'c'*64, 'd'*40, 'e'*64)

    def test_stage_refusal(self):
        plan = plan_fixture(); w = terminal_fixture(plan, plan['profiles'][0])
        for field, value in [('attempt',2), ('requests',87), ('body_bytes',1), ('cleanup','UNKNOWN')]:
            r = copy.deepcopy(w); r[field] = value
            with self.assertRaises(ValueError):
                v.linux_eligible(plan, r, 'c'*64, 'd'*40, 'e'*64)
        for field, value in [('skipped',['x']), ('native_sha256','f'*64), ('pre_use_disposition_sha256','f'*64)]:
            r = copy.deepcopy(w); r['stage_a'][field] = value
            with self.assertRaises(ValueError):
                v.linux_eligible(plan, r, 'c'*64, 'd'*40, 'e'*64)
        r = copy.deepcopy(w); r['stage_b'].pop('font:equivalence')
        with self.assertRaises(ValueError):
            v.linux_eligible(plan, r, 'c'*64, 'd'*40, 'e'*64)
        r = copy.deepcopy(w); r['stage_b']['mixed:contract']['collected'].pop(); r['stage_b']['mixed:contract']['passed'].pop()
        with self.assertRaises(ValueError):
            v.linux_eligible(plan, r, 'c'*64, 'd'*40, 'e'*64)

    def test_graph_exact_and_extra_refusal(self):
        with tempfile.TemporaryDirectory() as root:
            work = Path(root); expected = {'node_modules/demo':'1.0.0','node_modules/@scope/child':'2.0.0'}
            for key, version in expected.items():
                path = work / key; path.mkdir(parents=True); (path/'package.json').write_text(json.dumps({'name':key[13:], 'version':version}))
            self.assertEqual(v.installed_graph(work, expected), expected)
            with self.assertRaisesRegex(ValueError,'INSTALLED_GRAPH'):
                v.installed_graph(work, {'node_modules/demo':'1.0.0'})

    def test_checked_bytes_and_links(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)/'data'; p.write_bytes(b'fixture'); raw = b'fixture'
            self.assertEqual(v.checked_bytes(p,len(raw),hashlib.sha256(raw).hexdigest(),v.blob(raw)),raw)
            with self.assertRaises(ValueError):
                v.checked_bytes(p,len(raw),'0'*64)
            link = Path(root)/'link'; link.symlink_to(p)
            with self.assertRaises(ValueError):
                v.owned(link, root)
            with self.assertRaises(ValueError):
                v.checked_bytes(link,len(raw))

    def test_strict_json(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}'):
            with self.assertRaises(ValueError):
                v.strict_json(raw)


if __name__ == '__main__':
    unittest.main()
