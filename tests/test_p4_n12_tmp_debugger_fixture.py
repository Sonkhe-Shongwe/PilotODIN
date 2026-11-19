import unittest

from qa.p4_research.n12_tmp_debugger_fixture import matches_debugger_tmp


class DebuggerTmpFixtureTests(unittest.TestCase):
    def test_match_requires_one_exact_value_inside_the_environment_section(self):
        expected = r"C:\fixture\launch-tmp"
        self.assertTrue(matches_debugger_tmp(
            "PEB at 00000001\r\n    Environment:  00000002\r\n"
            "        TEMP=C:\\fixture\\fallback-temp\r\n"
            "        Tmp=c:\\FIXTURE\\launch-tmp\r\n0:000> g\r\n", expected,
        ))
        for output in (
            "    TMP=C:\\fixture\\launch-tmp\n",
            "    Environment:  00000002\n    TMP=C:\\fixture\\fallback-temp\n",
            "    Environment:  00000002\n    TMP=C:\\fixture\\launch-tmp\n    tmp=C:\\fixture\\launch-tmp\n",
            "    Environment:  00000002\n0:000> g\n    TMP=C:\\fixture\\launch-tmp\n",
        ):
            with self.subTest(output=output):
                self.assertFalse(matches_debugger_tmp(output, expected))
