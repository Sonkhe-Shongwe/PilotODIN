"""Focused regression for the inspection adapter's group settlement."""
import os
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

import inspection_core as c
from inspection_adapter import bounded_process


class ProcessTest(unittest.TestCase):
    def test_capture_and_kill_before_reap(self):
        real = os.killpg
        def kill(pid, sig):
            self.assertEqual(os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT).si_pid, pid)
            return real(pid, sig)
        with tempfile.TemporaryDirectory() as d, patch.object(os, 'killpg', side_effect=kill) as k:
            self.assertEqual(bounded_process([sys.executable, '-I', '-c', 'print("fixture")'], d, time.monotonic()+3, 128), (0,b'fixture\n',b''))
            k.assert_called_once()

    def test_failure_settlement(self):
        with tempfile.TemporaryDirectory() as d:
            for script, reason in [('print("x"*4096)', 'PROCESS_OUTPUT_CAP'), ('import time; time.sleep(5)', 'PROCESS_TIMEOUT')]:
                with self.subTest(reason=reason), self.assertRaisesRegex(c.Refused, reason):
                    bounded_process([sys.executable, '-I', '-c', script], d, time.monotonic()+(3 if reason=='PROCESS_OUTPUT_CAP' else 1), 128)

    def test_same_group_descendant(self):
        with tempfile.TemporaryDirectory() as d:
            script = 'import os,time; pid=os.fork();\nif pid==0:\n os.close(1); os.close(2); time.sleep(.4); open("escaped", "w").close(); os._exit(0)\nelse:\n print("leader")'
            self.assertEqual(bounded_process([sys.executable, '-I', '-W', 'ignore::DeprecationWarning', '-c', script], d, time.monotonic()+3, 128), (0,b'leader\n',b''))
            time.sleep(.6)
            self.assertFalse(Path(d,'escaped').exists())

    def test_lost_ownership_no_signal(self):
        child = Mock(pid=12345)
        with tempfile.TemporaryDirectory() as d, patch.object(subprocess, 'Popen', return_value=child), patch.object(selectors, 'DefaultSelector') as sel, patch.object(os, 'waitid', side_effect=ChildProcessError), patch.object(os,'killpg') as k:
            sel.return_value.__enter__.return_value.get_map.return_value = {}
            with self.assertRaisesRegex(c.Refused, 'PROCESS_REAPER'):
                bounded_process([sys.executable, '-I', '-c', 'pass'], d, time.monotonic()+3, 128)
            k.assert_not_called(); child.wait.assert_not_called()
            child.stdout.close.assert_called_once(); child.stderr.close.assert_called_once()
