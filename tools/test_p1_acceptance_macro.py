"""P1 macro source-safety checks; no actual backend, project or network use."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

module_path = Path(__file__).with_name("Run_P1_Acceptance_Macro.py")
spec = importlib.util.spec_from_file_location("p1safe", module_path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MacroSafetyTest(unittest.TestCase):
    def test_summary_never_closes_p1(self):
        self.assertEqual(m.overall([{"status": "PASS"}]),
                         "AUTOMATED_SUBSET_PASS_NOT_P1_CLOSURE")
        self.assertEqual(m.overall([{"status": "BLOCKED"}]),
                         "AUTOMATED_PARTIAL_WITH_BLOCKERS")
        self.assertEqual(m.overall([{"status": "FAIL"}]),
                         "AUTOMATED_FAILURE_REQUIRES_REVIEW")

    def test_dirty_working_tree_disables_all_checks_but_produces_zip(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(m, "git_preflight",
                              return_value={"status": "BLOCKED", "reason": "dirty"}), \
                 patch.object(m, "occupied_ports",
                              return_value={"8000": "IN_USE", "5174": "IN_USE", "5187": "FREE"}), \
                 patch.object(m, "phase", return_value={"gate": "safety-preflight",
                                                        "status": "BLOCKED"}) as run:
                archive, output = m.main_run(root, root, require_windows=False)
            run.assert_called_once()
            self.assertTrue(archive.is_file())
            self.assertEqual(output["p1_closure"], "OPEN_REQUIRES_OWNER_DECISION")
            self.assertTrue(all(value == "NOT_RUN" for value in
                                output["native_manual_gates"].values()))
            self.assertEqual(json.loads((archive.with_suffix("")/"result.json").read_text())
                             ["source"]["status"], "BLOCKED")

    def test_blocked_tool_never_runs_child_process(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            with patch.object(m.subprocess, "run", side_effect=AssertionError("child process")):
                result = m.phase("offline", None, p, p, p, block="missing")
            self.assertEqual(result["status"], "BLOCKED")

    def test_existing_ports_inspected_without_connecting(self):
        lines = "TCP 127.0.0.1:8000 0.0.0.0:0 LISTENING 100\n"
        mock = type("Result", (), {"returncode": 0, "stdout": lines})()
        with patch.object(m, "command_capture", return_value=mock) as action:
            self.assertEqual(m.occupied_ports(),
                             {"8000": "IN_USE", "5174": "FREE", "5187": "FREE"})
        self.assertEqual(action.call_args.args[0][0], "netstat")

    def test_no_browser_on_occupied_test_port(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/"frontend"/"node_modules"/".bin").mkdir(parents=True)
            (root/"frontend"/"node_modules"/".bin"/"playwright.cmd").touch()
            calls = []
            def capture(name, args, cwd, home, directory, **kwargs):
                calls.append((name, kwargs.get("block")))
                return {"gate": name, "status": "BLOCKED" if kwargs.get("block") else "PASS"}
            with patch.object(m, "git_preflight",
                              return_value={"status": "PASS", "sha": "a"*40}), \
                 patch.object(m, "occupied_ports", return_value={
                     "8000": "IN_USE", "5174": "IN_USE", "5187": "IN_USE"
                 }), patch.object(m, "phase", side_effect=capture), \
                 patch.object(m.shutil, "which", return_value="node"):
                _, result = m.main_run(root, root, require_windows=False)
            blocked = [reason for name, reason in calls if name ==
                       "chromium-isolated-five-cases"]
            self.assertIn("5187", blocked[0])
            self.assertEqual(result["status"], "AUTOMATED_PARTIAL_WITH_BLOCKERS")


if __name__ == "__main__":
    unittest.main()
