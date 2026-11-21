"""Synthetic API resolution controls: no real token creation or ACL operations."""
import json
import unittest
from unittest.mock import patch

from qa.p4_research import n12_token_capability_preflight as capability


class Module:
    def __init__(self, symbols, *, calls):
        self.symbols = symbols
        self.calls = calls

    def __getattr__(self, symbol):
        if symbol not in self.symbols:
            raise AttributeError("private-symbol-data")
        def forbidden_call(*args):
            self.calls.append(symbol)
            raise AssertionError("No Win32 API may be invoked in this preflight")
        return forbidden_call


def loader_for(symbols=None, *, calls=None, unavailable=()):
    if symbols is None:
        symbols = capability.EXPORTS
    if calls is None:
        calls = []
    def load(dll):
        if dll in unavailable:
            raise OSError("private-host-path")
        return Module(symbols.get(dll, ()), calls=calls)
    return load


class TokenCapabilityTests(unittest.TestCase):
    def test_no_windows_host_is_blocked_without_loading_any_dlls(self):
        calls = []
        def forbidden_loader(_dll):
            calls.append(_dll)
            raise AssertionError("must not be invoked")
        result = capability.inspect_api_surface(platform="posix", loader=forbidden_loader)
        self.assertEqual(result["api_surface_status"], "BLOCKED")
        self.assertEqual(result["issues"], ["windows-host-required"])
        self.assertEqual(calls, [])
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")

    def test_api_presence_never_certifies_token_creation_or_file_protection(self):
        calls = []
        result = capability.inspect_api_surface(platform="nt", loader=loader_for(calls=calls))
        self.assertEqual(result["api_surface_status"], "PRESENT")
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["exports_observed"], result["exports_expected"])
        self.assertEqual(calls, [])
        for key in ("native_token_created", "token_attributes_verified",
                    "restricted_writer_launched", "acl_modified",
                    "file_access_attempted", "file_protection_verified",
                    "api_evidence_proves_security", "owner_native_execution_authorized"):
            self.assertIs(result[key], False)
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")

    def test_missing_required_symbols_block_and_explain_exact_export(self):
        for dll, functions in capability.EXPORTS.items():
            for missing in functions:
                with self.subTest(dll=dll, missing=missing):
                    selected = {name: set(exports) for name, exports in capability.EXPORTS.items()}
                    selected[dll].remove(missing)
                    r = capability.inspect_api_surface(platform="nt", loader=loader_for(selected))
                    self.assertEqual(r["api_surface_status"], "BLOCKED")
                    self.assertEqual(r["issues"], [dll.removesuffix(".dll") + "-api-unavailable:" + missing])
                    self.assertEqual(r["exports_observed"], r["exports_expected"] - 1)

    def test_dll_load_failure_is_redacted_and_does_not_stop_other_checks(self):
        result = capability.inspect_api_surface(
            platform="nt", loader=loader_for(unavailable=("advapi32.dll",)))
        self.assertEqual(result["api_surface_status"], "BLOCKED")
        self.assertEqual(result["issues"], ["advapi32-load-unverified"])
        self.assertEqual(result["exports_observed"], len(capability.EXPORTS["kernel32.dll"]))
        self.assertNotIn("private-host-path", json.dumps(result))

    def test_non_callable_symbol_and_no_loader_fail_closed(self):
        def loader(dll):
            if dll == "advapi32.dll":
                class BadModule:
                    def __getattr__(self, name):
                        if name == "AccessCheck":
                            return "string-not-a-function"
                        return lambda: None
                return BadModule()
            return Module(capability.EXPORTS[dll], calls=[])
        result = capability.inspect_api_surface(platform="nt", loader=loader)
        self.assertEqual(result["api_surface_status"], "BLOCKED")
        self.assertIn("advapi32-api-unavailable:AccessCheck", result["issues"])
        with patch.object(capability.ctypes, "WinDLL", None, create=True):
            result = capability.inspect_api_surface(platform="nt")
        self.assertEqual(result["issues"], ["windows-dll-loader-unavailable"])

    def test_plan_stays_inert_and_documents_future_independent_proofs(self):
        plan = capability.capability_plan()
        self.assertTrue(plan["no_host_mutation"])
        self.assertTrue(plan["accesscheck_requires_impersonation_token"])
        self.assertFalse(plan["restricted_token_proves_global_app_containment"])
        self.assertEqual(plan["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertIn("CreateRestrictedToken", plan["exports"]["advapi32.dll"])
        self.assertIn("GetTokenInformation", plan["exports"]["advapi32.dll"])
        self.assertIn("TokenRestrictedSids", plan["token_information"])
        self.assertIn("SeTakeOwnershipPrivilege", plan["privileges_to_exclude"])
        self.assertIn("effective-protected-write-denied", plan["future_proofs"])
        self.assertIn("same-writer-permitted-positive-control", plan["future_proofs"])
        self.assertNotIn("\\", json.dumps(plan))


if __name__ == "__main__":
    unittest.main()
