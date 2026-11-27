import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import inspection_core as c
import inspection_adapter as a
from test_inspection_core import wheel, npm, row


class AdapterTest(unittest.TestCase):
    def test_strict_zip_and_crc(self):
        raw = wheel([('demo/native.pyd', b'MZfixture')])
        self.assertEqual(a.verified_inspect(raw, row(raw))['native'][0]['format'], 'PE')
        bad = bytearray(raw); bad[14] ^= 1
        for payload in (bytes(bad), raw + b'trailing', b'prefix' + raw, raw[:-1]):
            with self.subTest(payload=payload[:10]), self.assertRaises(c.Refused):
                a.strict_zip(payload)

    def test_hash_before_structure(self):
        raw = wheel(); r = row(raw); r['sha256'] = '0' * 64
        with patch.object(a, 'strict_zip', side_effect=AssertionError('parsed')), self.assertRaisesRegex(c.Refused, 'ARCHIVE_IDENTITY'):
            a.verified_inspect(raw, r)

    def test_native_stage_exclusive(self):
        for raw, kind in [(wheel([('demo/native.pyd', b'MZfixture')]), 'wheel'), (npm([('package/tool', b'\x7fELFfixture')]), 'npm')]:
            r = row(raw, kind); item = a.verified_inspect(raw, r)['native'][0]
            with tempfile.TemporaryDirectory() as scratch:
                f = a.stage_member(raw, r, item, scratch)
                self.assertEqual(c.digest(f.read_bytes()), item['sha256'])
                self.assertEqual(f.stat().st_mode & 0o777, 0o600)
                with self.assertRaises(FileExistsError):
                    a.stage_member(raw, r, item, scratch)
                with self.assertRaisesRegex(c.Refused, 'NATIVE_SCOPE'):
                    a.stage_member(raw, r, {**item, 'sha256': '0' * 64}, scratch)

    def test_process_capture(self):
        with tempfile.TemporaryDirectory() as scratch:
            result = a.bounded_process([sys.executable, '-I', '-c', 'print("fixture")'], scratch, time.monotonic() + 3, 128)
            self.assertEqual(result, (0, b'fixture\n', b''))

    def test_process_output_and_time(self):
        with tempfile.TemporaryDirectory() as scratch:
            for code, seconds, reason in [('print("x"*4096)', 3, 'PROCESS_OUTPUT_CAP'), ('import time; time.sleep(5)', 0.2, 'PROCESS_TIMEOUT')]:
                with self.subTest(reason=reason), self.assertRaisesRegex(c.Refused, reason):
                    a.bounded_process([sys.executable, '-I', '-c', code], scratch, time.monotonic() + seconds, 128)

    def test_linkage(self):
        elf = b'  Machine: Advanced Micro Devices X86-64\n  (NEEDED) Shared library: [libc.so.6]\n  Name: GLIBC_2.17 Flags: none\n'
        pe = b'member: file format pei-x86-64\n DLL Name: KERNEL32.dll\n'
        self.assertEqual(a.linkage('ELF', 0, elf, b'')['versions'], ['GLIBC_2.17'])
        self.assertEqual(a.linkage('PE', 0, pe, b'')['imports'], ['KERNEL32.dll'])
        for malformed in (b'wrong', elf.replace(b'libc.so.6', b'../libc'), elf.replace(b'X86-64', b'ARM')):
            with self.assertRaises(c.Refused):
                a.linkage('ELF', 0, malformed, b'')

    def test_batch_limits_and_partial_receipt(self):
        clock = [0]; b = a.Receipt(lambda: clock[0]); raw = wheel(); r = row(raw)
        b.reserve(r); b.append({'status': 'UNRESOLVED'}); self.assertEqual(b.snapshot()['attempts'], 1)
        with self.assertRaisesRegex(c.Refused, 'BATCH_SCOPE'):
            b.reserve(r)
        with patch.object(a, 'MAX_BODY', len(raw)), self.assertRaisesRegex(c.Refused, 'BATCH_SCOPE'):
            b.reserve({**r, 'url': r['url'].replace('/packages/', '/other/')})
        clock[0] = 1800
        with self.assertRaisesRegex(c.Refused, 'BATCH_STATE_OR_TIME'):
            b.reserve(r)
        b.refuse(); self.assertEqual(len(b.snapshot()['rows']), 1)
        self.assertEqual(b.snapshot()['status'], 'REFUSED_UNRESOLVED')

    def test_aggregate_receipt_cap(self):
        b = a.Receipt(); b.reserve(row(wheel()))
        with patch.object(c, 'MAX_OUTPUT', 1100), self.assertRaisesRegex(c.Refused, 'BATCH_RECEIPT_CAP'):
            b.append({'data': 'x' * 100})
        self.assertEqual(b.snapshot()['rows'], [])


if __name__ == '__main__':
    unittest.main()
