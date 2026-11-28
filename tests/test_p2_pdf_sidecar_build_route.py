"""P2 build-route decision tests; no package install, freeze or font reads."""
from __future__ import annotations

import unittest

from tools import p2_pdf_sidecar_build_route as route
from tools.p2_pdf_sidecar_build_readiness import REQUIRED_RUNTIME


def env(*, runtime=True, freezer=False, name="6.22.3",
        python="3.12.6", bits=64, state="INSPECTED"):
    return {
        "state": state, "python": python, "architecture_bits": bits,
        "runtime_present": list(REQUIRED_RUNTIME) if runtime else ["fastapi"],
        "runtime_missing": [] if runtime else ["reportlab", "scipy"],
        "freezer_present": ["pyinstaller", "pyinstaller-hooks-contrib"] if freezer else [],
        "pyinstaller_version": name if freezer else None,
        "hooks_version": "2026.9" if freezer else None,
    }


class SidecarBuildRouteContracts(unittest.TestCase):
    def test_complete_existing_build_env_is_candidate_not_frozen_pass(self):
        values = {"live": env(), "existing_build": env(freezer=True),
                  "private_freezer": env(runtime=False, freezer=True)}
        result = route.decide_build_route(values, 4 * 1024**3)
        self.assertEqual(result["route"], "EXISTING_SELF_CONTAINED_INTERPRETER_CANDIDATE")
        self.assertEqual(result["primary_self_contained_candidate"], "existing_build")
        self.assertFalse(result["sidecar_built"])
        self.assertEqual(result["production_acceptance"], "NOT_TESTED")

    def test_split_envs_require_new_full_builder_design_not_site_package_merger(self):
        values = {"live": env(), "existing_build": {"state": "ABSENT"},
                  "private_freezer": env(runtime=False, freezer=True)}
        result = route.decide_build_route(values, 4 * 1024**3)
        self.assertEqual(result["route"], "DEDICATED_FULL_BUILD_ENVIRONMENT_DESIGN_REQUIRED")
        self.assertIsNone(result["primary_self_contained_candidate"])
        self.assertTrue(result["private_builder_has_pinned_pyinstaller"])
        self.assertFalse(result["dependencies_installed"])

    def test_missing_backend_runtime_cannot_use_private_tooling(self):
        values = {"live": env(runtime=False), "existing_build": {"state": "ABSENT"},
                  "private_freezer": env(runtime=False, freezer=True)}
        result = route.decide_build_route(values, 4 * 1024**3)
        self.assertEqual(result["route"], "REVIEW_RUNTIME_DEPENDENCIES_BEFORE_BUILD")
        self.assertFalse(result["live_has_complete_runtime_metadata"])

    def test_incomplete_or_wrong_architecture_cannot_be_build_candidate(self):
        for kwargs in ({"runtime": False, "freezer": True},
                       {"runtime": True, "freezer": True, "bits": 32},
                       {"runtime": True, "freezer": True, "name": "5.13.0"},
                       {"runtime": True, "freezer": True, "python": "broken"}):
            with self.subTest(kwargs=kwargs):
                self.assertFalse(route.is_self_contained_candidate(env(**kwargs)))

    def test_blocked_probe_or_insufficient_disk_is_not_green(self):
        values = {"live": env(), "existing_build": {"state": "BLOCKED"},
                  "private_freezer": env(runtime=False, freezer=True)}
        self.assertEqual(route.decide_build_route(values, 4 * 1024**3)["state"], "BLOCKED")
        values["existing_build"] = {"state": "ABSENT"}
        result = route.decide_build_route(values, 1000)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["route"], "INSUFFICIENT_DISK_FOR_BUILD_DESIGN")

    def test_no_implicit_build_permission_and_invalid_inputs_fail(self):
        sample = {"live": env(), "existing_build": {"state": "ABSENT"},
                  "private_freezer": env(runtime=False, freezer=True)}
        result = route.decide_build_route(sample, 4 * 1024**3)
        self.assertFalse(result["dependencies_installed"])
        self.assertFalse(result["sidecar_built"])
        self.assertFalse(result["installer_built"])
        self.assertIn("Wheel/requirement version constraints and full lockfile",
                      result["not_verified"])
        with self.assertRaises(ValueError):
            route.decide_build_route({"live": env()}, 4 * 1024**3)
        with self.assertRaises(ValueError):
            route.decide_build_route(sample, True)


if __name__ == "__main__":
    unittest.main()
