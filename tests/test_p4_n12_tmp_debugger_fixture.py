import unittest

from qa.p4_research.n12_tmp_debugger_fixture import debugger_tmp_status


class DebuggerTmpFixtureTests(unittest.TestCase):
    def test_match_requires_one_exact_value_inside_the_environment_section(self):
        expected = r"C:\fixture\launch-tmp"
        self.assertEqual(debugger_tmp_status(
            "PEB at 00000001\r\n    Environment:  00000002\r\n"
            "        TEMP=C:\\fixture\\fallback-temp\r\n"
            "        Tmp=c:\\FIXTURE\\launch-tmp\r\n0:000> g\r\n", expected,
        ), "expected-tmp")
        for output, reason in (
            ("    TMP=C:\\fixture\\launch-tmp\n", "environment-section-missing"),
            ("Type information missing\n", "debugger-symbols-unavailable"),
            ("    Environment: ???\n", "environment-section-unrecognized"),
            ("    Environment:  00000002\n    TMP=C:\\fixture\\fallback-temp\n", "tmp-value-mismatch"),
            ("    Environment:  00000002\n    TMP=D:relative\n", "tmp-path-invalid"),
            ("    Environment:  00000002\n    TMP=C:\\fixture\\launch-tmp\n    tmp=C:\\fixture\\launch-tmp\n",
             "tmp-ambiguous"),
            ("    Environment:  00000002\n0:000> g\n    TMP=C:\\fixture\\launch-tmp\n", "tmp-not-observed"),
        ):
            with self.subTest(reason=reason):
                self.assertEqual(debugger_tmp_status(output, expected), reason)
