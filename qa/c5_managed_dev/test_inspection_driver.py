import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import inspection_core as c
import inspection_adapter as a
import inspection_driver as d
from test_inspection_core import wheel, npm, row


class DriverTest(unittest.TestCase):
    def test_live_refuses_before_projection(self):
        with patch.object(c, 'projection', side_effect=AssertionError('parsed')), self.assertRaisesRegex(c.Refused, 'DISARMED'):
            d.run_live(b'bad', '/not-owned')

    def test_matching_header_crc_refusal(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('fixture', b'abc')
        raw = bytearray(buf.getvalue()); raw[30 + len('fixture')] ^= 1
        with self.assertRaisesRegex(c.Refused, 'ZIP_CRC_SIZE'):
            a.strict_zip(bytes(raw))

    def test_end_to_end_and_cleanup(self):
        raw = wheel([('demo/native.pyd', b'MZfixture')]); r = row(raw)
        def command(argv, scratch, deadline, seconds):
            self.assertEqual(argv[:2], ['/usr/bin/objdump', '-p'])
            self.assertEqual(Path(argv[-1]).read_bytes(), b'MZfixture')
            return 0, b'member: file format pei-x86-64\n DLL Name: KERNEL32.dll\n', b''
        with tempfile.TemporaryDirectory() as root, patch.object(d, 'FLOOR', 0):
            result = d._collect([r], root, lambda *args: raw, command, lambda *args: {})
            self.assertEqual(result['status'], 'INSPECTED_UNRESOLVED_USE_RIGHTS')
            self.assertEqual(result['verified_body_bytes'], len(raw))
            self.assertEqual(result['rows'][0]['native'][0]['linkage']['imports'], ['KERNEL32.dll'])
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_partial_refusal_and_no_retry(self):
        raw = wheel([('demo/native.pyd', b'MZfixture')]); r = row(raw); calls = []
        def acquire(*args):
            calls.append(args[0]); return raw
        with tempfile.TemporaryDirectory() as root, patch.object(d, 'FLOOR', 0):
            result = d._collect([r, r], root, acquire, lambda *args: (1, b'private raw', b'error'), lambda *args: {})
            self.assertEqual(result['status'], 'REFUSED_UNRESOLVED')
            self.assertEqual(result['failure'], 'TOOL_REFUSED')
            self.assertEqual(len(result['rows']), 1)
            self.assertEqual(len(calls), 1)
            self.assertNotIn('private raw', str(result))
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_archive_hash_refusal(self):
        raw = wheel(); r = row(raw)
        with tempfile.TemporaryDirectory() as root, patch.object(d, 'FLOOR', 0):
            result = d._collect([r], root, lambda *args: raw[:-1], None, lambda *args: {})
            self.assertEqual(result['verified_body_bytes'], 0)
            self.assertEqual(result['attempts'], 1)
            self.assertEqual(result['failure'], 'ARCHIVE_IDENTITY')

    def test_outer_deadline(self):
        import time
        raw = wheel(); r = row(raw)
        with tempfile.TemporaryDirectory() as root, patch.object(d, 'FLOOR', 0):
            result = d._collect([r], root, lambda *args: time.sleep(1), None, lambda *args: {}, seconds=0.05)
            self.assertEqual(result['failure'], 'OUTER_DEADLINE')
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_unselected_image_refuses_before_tools(self):
        with patch.object(d, 'run_command', side_effect=AssertionError('tool called')), self.assertRaisesRegex(c.Refused, 'RUNNER_IMAGE'):
            d.observed_tools('/not-owned', 0)

    def test_notice_indicators_no_raw_text(self):
        raw = wheel([('demo/LICENSE.txt', b'MIT License. private notice content')]); r = row(raw)
        with tempfile.TemporaryDirectory() as root, patch.object(d, 'FLOOR', 0):
            result = d._collect([r], root, lambda *args: raw, None, lambda *args: {})
            self.assertEqual(result['status'], 'INSPECTED_UNRESOLVED_USE_RIGHTS')
            self.assertIn('MIT notice title', str(result['rows'][0]['notice_indicators']))
            self.assertNotIn('private notice content', str(result))

    def test_staged_link_refusal(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'link'; path.symlink_to('/dev/null')
            with self.assertRaises(OSError):
                d.file_identity(path, 0, 'sha256')


if __name__ == '__main__':
    unittest.main()
