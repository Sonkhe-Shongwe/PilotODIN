"""QA-only ambient local redirection candidate, generated source/fixture cases."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_ambient_local_candidate as candidate
from qa.p4_research import n12_app_journey as journey


class AmbientLocalCandidateSourceTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="n12-ambient-fixture-")
        self.addCleanup(temp.cleanup)
        self.runner = Path(temp.name)
        root = self.runner / "pilotodin-n12-build-123-journey"
        root.mkdir()
        self.profile = root / "webview"
        self.profile.mkdir()
        (self.profile / journey.APP_TEMP_DIR).mkdir()
        self.env = {
            "LOCALAPPDATA": str(self.runner / "original-host-local"),
            "APPDATA": str(self.runner / "original-host-roaming"),
            "WEBVIEW2_USER_DATA_FOLDER": str(self.profile),
            "TEMP": str(self.profile / journey.APP_TEMP_DIR),
            "TMP": str(self.profile / journey.APP_TEMP_DIR),
            "TMPDIR": str(self.profile / journey.APP_TEMP_DIR),
        }

    def opt_in(self):
        self.env[candidate.FLAG] = candidate.CANDIDATE
        candidate.prepare(self.profile, self.runner)

    def test_baseline_keeps_original_app_data_locations(self):
        app = journey.app_environment(self.env, self.profile, "first")
        self.assertEqual(app["LOCALAPPDATA"], self.env["LOCALAPPDATA"])
        self.assertEqual(app["APPDATA"], self.env["APPDATA"])
        self.assertEqual(app["WEBVIEW2_USER_DATA_FOLDER"], str(self.profile))
        self.assertFalse((self.profile / candidate.LOCAL_DIR).exists())
        self.assertEqual(candidate.public_receipt(self.env)["variant"], "unchanged-baseline")

    def test_opt_in_redirects_only_local_and_roaming_inside_permitted_profile(self):
        self.opt_in()
        app = journey.app_environment(self.env, self.profile, "first")
        self.assertEqual(app["LOCALAPPDATA"], str(self.profile / candidate.LOCAL_DIR))
        self.assertEqual(app["APPDATA"], str(self.profile / candidate.ROAMING_DIR))
        for key in ("TEMP", "TMP", "TMPDIR", "WEBVIEW2_USER_DATA_FOLDER"):
            self.assertEqual(app[key], self.env[key])
        receipt = candidate.public_receipt(self.env)
        self.assertEqual(receipt["native_filesystem_containment"], "NOT_VERIFIED")
        self.assertNotIn("original-host-local", str(receipt))

    def test_nonempty_unknown_variant_refuses(self):
        for variant in ("1", "true", "ISOLATED_QA_ROOT", "candidate"):
            with self.subTest(variant=variant):
                env = {**self.env, candidate.FLAG: variant}
                with self.assertRaisesRegex(trace.EvidenceValidationError,
                                            "variant-unrecognised"):
                    journey.app_environment(env, self.profile, "first")
        self.assertFalse(candidate.enabled({**self.env, candidate.FLAG: ""}))

    def test_unprepared_candidate_directory_refuses(self):
        self.env[candidate.FLAG] = candidate.CANDIDATE
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "directory-unverified"):
            journey.app_environment(self.env, self.profile, "first")

    def test_host_temp_for_any_app_variable_refuses(self):
        self.opt_in()
        for key in ("TEMP", "TMP", "TMPDIR"):
            with self.subTest(variable=key):
                env = {**self.env, key: self.env["LOCALAPPDATA"]}
                with self.assertRaisesRegex(trace.EvidenceValidationError,
                                            "temp-unverified"):
                    journey.app_environment(env, self.profile, "first")

    def test_profile_outside_runner_refuses(self):
        other = self.runner / "unrelated-runner"
        other.mkdir()
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "outside-runner"):
            candidate.prepare(self.profile, other)

    def test_existing_candidate_target_cannot_be_overwritten(self):
        (self.profile / candidate.LOCAL_DIR).mkdir()
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "already-exists"):
            candidate.prepare(self.profile, self.runner)

    def test_unexpected_webview_profile_argument_refuses(self):
        self.opt_in()
        env = {**self.env, "WEBVIEW2_USER_DATA_FOLDER":
               str(self.runner / "wrong-profile")}
        with self.assertRaisesRegex(trace.EvidenceValidationError,
                                    "profile-unverified"):
            candidate.apply_to_app_env(env, self.profile)

    def test_synthetic_symlink_flag_refuses_without_creating_host_symlink(self):
        self.opt_in()
        local = self.profile / candidate.LOCAL_DIR
        original = Path.is_symlink
        with patch.object(Path, "is_symlink",
                          lambda obj: obj == local or original(obj)):
            with self.assertRaisesRegex(trace.EvidenceValidationError,
                                        "directory-unverified"):
                candidate.apply_to_app_env(self.env, self.profile)

    def test_backend_and_driver_do_not_inherit_candidate_overrides(self):
        self.opt_in()
        app = journey.app_environment(self.env, self.profile, "first")
        backend = journey.backend_environment(self.env)
        driver = journey.driver_environment(self.env, self.profile.parent)
        self.assertNotEqual(app["LOCALAPPDATA"], backend["LOCALAPPDATA"])
        self.assertEqual(backend["LOCALAPPDATA"], driver["LOCALAPPDATA"])
        self.assertNotEqual(app["APPDATA"], backend["APPDATA"])
        self.assertEqual(backend["APPDATA"], driver["APPDATA"])

    def test_global_os_environment_stays_untouched(self):
        self.opt_in()
        before = dict(os.environ)
        app = candidate.apply_to_app_env(self.env, self.profile)
        self.assertEqual(before, dict(os.environ))
        self.assertNotEqual(app["LOCALAPPDATA"], self.env["LOCALAPPDATA"])


if __name__ == "__main__":
    unittest.main()
