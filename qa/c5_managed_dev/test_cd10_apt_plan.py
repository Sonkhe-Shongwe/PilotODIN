import unittest
from cd10_apt_plan import NAMES, OLD, VERSION, exact_plan

# Exact 16 action lines from run 45979167594, job 140438373369.
ACTUAL = '''8 upgraded, 0 newly installed, 0 to remove and 63 not upgraded.
Inst libgprofng0 [2.42-4ubuntu2.10] (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64]) []
Inst libctf0 [2.42-4ubuntu2.10] (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64]) []
Inst libctf-nobfd0 [2.42-4ubuntu2.10] (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64]) []
Inst binutils-x86-64-linux-gnu [2.42-4ubuntu2.10] (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64]) [binutils:amd64 ]
Inst libbinutils [2.42-4ubuntu2.10] (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64]) [binutils:amd64 ]
Inst binutils [2.42-4ubuntu2.10] (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64]) []
Inst binutils-common [2.42-4ubuntu2.10] (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64])
Inst libsframe1 [2.42-4ubuntu2.10] (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64])
Conf libgprofng0 (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64])
Conf libctf0 (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64])
Conf libctf-nobfd0 (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64])
Conf binutils-x86-64-linux-gnu (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64])
Conf libbinutils (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64])
Conf binutils (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64])
Conf binutils-common (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64])
Conf libsframe1 (2.42-4ubuntu2.11 Ubuntu:24.04/noble-security [amd64])'''


class PlanTest(unittest.TestCase):
    def test_retained_transaction(self):
        self.assertEqual(exact_plan(ACTUAL, dict.fromkeys(NAMES, OLD)), ACTUAL.splitlines()[1:])

    def test_refuse_changes(self):
        lines = ACTUAL.splitlines()
        for changed in (ACTUAL.replace(' []', ' [other:amd64 ]', 1),
                        ACTUAL.replace('noble-security', 'noble-updates', 1),
                        ACTUAL.replace('[amd64]', '[arm64]', 1),
                        ACTUAL.replace(VERSION, '2.42-4ubuntu2.12', 1),
                        ACTUAL.replace('0 newly installed', '1 newly installed'),
                        ACTUAL.replace('0 to remove', '1 to remove'),
                        ACTUAL + '\nRemv libc6 [2.39]',
                        ACTUAL + '\nPurg libc6 [2.39]',
                        ACTUAL + '\n' + lines[1],
                        ACTUAL + '\n' + lines[-1],
                        '\n'.join(lines[:-1]),
                        '\n'.join([lines[0], lines[-1], *lines[1:-1]]),
                        ACTUAL.replace('Inst libgprofng0', 'Inst unrelated', 1),
                        ACTUAL.replace('Conf libgprofng0', 'Conf unrelated', 1),
                        ACTUAL.replace('Inst libgprofng0', 'Inst\tlibgprofng0', 1)):
            with self.subTest(changed=changed[:100]), self.assertRaises(ValueError):
                exact_plan(changed, dict.fromkeys(NAMES, OLD))

    def test_already_patched(self):
        self.assertEqual(exact_plan('0 upgraded, 0 newly installed, 0 to remove and 63 not upgraded.', dict.fromkeys(NAMES, VERSION)), [])
        with self.assertRaises(ValueError):
            exact_plan(ACTUAL, dict.fromkeys(NAMES, VERSION))
