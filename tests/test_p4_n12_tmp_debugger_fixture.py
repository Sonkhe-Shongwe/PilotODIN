import unittest

from qa.p4_research.n12_tmp_debugger_fixture import debugger_tmp_status


class DebuggerTmpFixtureTests(unittest.TestCase):
    def read_output(self, output, expected):
        return debugger_tmp_status(
            "PILOTODIN_TMP_BEGIN\r\n" + output + "PILOTODIN_TMP_END\r\n", expected,
        )

    def test_match_requires_one_exact_value_inside_the_environment_section(self):
        expected = r"C:\fixture\launch-tmp"
        self.assertEqual(self.read_output(
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
                self.assertEqual(self.read_output(output, expected), reason)

    def test_documented_environment_pointer_formats(self):
        expected = r"C:\fixture\launch-tmp"
        for address in ("0x10000", "00007ffa`01234567", "00010000"):
            with self.subTest(address=address):
                output = f"    Environment: {address}\r\n        TMP={expected}\r\n"
                self.assertEqual(self.read_output(output, expected), "expected-tmp")

    def test_rejects_ambiguous_headers_and_unbounded_output(self):
        expected = r"C:\fixture\launch-tmp"
        output = f"    Environment: 0x10000\n        TMP={expected}\n"
        self.assertEqual(self.read_output("    Environment: ???\n" + output, expected),
                         "environment-section-ambiguous")
        for transcript, reason in (
            (output, "initial-break-output-missing"),
            ("PILOTODIN_TMP_END\n" + output, "initial-break-output-incomplete"),
            ("PILOTODIN_TMP_BEGIN\n" + output, "initial-break-output-incomplete"),
            ("PILOTODIN_TMP_END\n" + output + "PILOTODIN_TMP_BEGIN\n", "initial-break-output-incomplete"),
            ("PILOTODIN_TMP_BEGIN\nPILOTODIN_TMP_END\n" + output, "environment-section-missing"),
        ):
            with self.subTest(transcript=transcript):
                self.assertEqual(debugger_tmp_status(transcript, expected), reason)
