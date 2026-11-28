"""Synthetic coordinator contracts; no subprocess or product/native execution."""
import copy
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from qa.c5_managed_dev import validation_coordinator as c, validation_witnesses as w


def plan():
    return w.read_plan((Path(__file__).parent/'pdfium_use_candidate_20261127.json').read_bytes())


def report(nodes, mode):
    return dict(collected=nodes, passed=nodes if mode=='EXECUTION' else [],
                failed=[], skipped=[], xfailed=[], exitstatus=0, mode=mode)


class CoordinatorTest(unittest.TestCase):
    def test_exact_split(self):
        p = plan()
        for i, profile in enumerate(p['profiles']):
            a, b = c.split_inputs(p, profile)
            self.assertEqual((len(a), len(b)), (8-i, 41+i))
            self.assertEqual(len(c.smoke_lock(a).splitlines()), 8-i)
            self.assertEqual(len(a+b), 49)
        bad = copy.deepcopy(p)
        bad['profiles'][0]['application_bounds']['body_bytes'] += 1
        with self.assertRaisesRegex(ValueError, 'INPUT_BUDGET'):
            c.split_inputs(bad, bad['profiles'][0])

    def test_collection_execution_binding(self):
        selector = 'tests/test_example.py'
        nodes = [selector+'::test_a', selector+'::test_b']
        collected, executed = report(nodes, 'COLLECTION'), report(nodes, 'EXECUTION')
        self.assertEqual(c.receipt_pair(collected, executed, selector, nodes)['passed'], nodes)
        for bad in (dict(executed, passed=nodes[:1]), dict(executed, skipped=nodes[:1]),
                    dict(executed, exitstatus=True), dict(executed, xfailed=nodes[:1]),
                    dict(executed, collected=nodes[::-1], passed=nodes[::-1])):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                c.receipt_pair(collected, bad, selector, nodes)
        with self.assertRaises(ValueError):
            c.receipt_pair(collected, executed, selector, nodes[:1])

    def test_foreign_and_duplicate_nodes(self):
        for nodes in (['other.py::test_a'], ['a.py::test_a']*2, []):
            with self.assertRaises(ValueError):
                c.receipt_pair(report(nodes, 'COLLECTION'), report(nodes, 'EXECUTION'), 'a.py')

    def test_disarm_before_operations(self):
        ops = Mock()
        with self.assertRaisesRegex(ValueError, 'DISARMED'):
            c.run_profile(None, None, None, None, None, None, ops)
        self.assertEqual(ops.mock_calls, [])

    def test_stage_a_failure_stops_b(self):
        p = plan(); profile = p['profiles'][0]; ops = Mock()
        ops.verify_native.return_value = '0'*64
        ops.pytest.return_value = {'state':'PASS','collected':[],'passed':[]}
        with patch.object(c, 'LIVE_ENABLED', True), patch.object(w, 'require_live'), self.assertRaises(ValueError):
            c.run_profile(p, profile, '1'*64, '2'*40, '3'*64, None, ops)
        ops.prepare_a.assert_called_once()
        ops.prepare_b.assert_not_called()

    def test_windows_first(self):
        p = plan(); ops = Mock()
        with patch.object(c, 'LIVE_ENABLED', True), patch.object(w, 'require_live'), self.assertRaises((TypeError, ValueError)):
            c.run_profile(p, p['profiles'][1], '1'*64, '2'*40, '3'*64, None, ops)
        self.assertEqual(ops.mock_calls, [])
