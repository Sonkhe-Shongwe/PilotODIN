"""Synthetic-only N12 protected-file evidence contract regressions."""
import copy
import json
import unittest

from qa.p4_research import n12_protected_fixture_contract as contract


def synthetic_receipt():
    return {
        "scope": contract.SCOPE,
        "roots": list(contract.ROOTS),
        "identity_model": contract.IDENTITY_MODEL,
        "token": dict.fromkeys(contract.TOKEN_PROOFS, True),
        "protected_attempts": [
            {"operation": op, "result": "access-denied"} for op in contract.PROTECTED_CASES
        ],
        "permitted_attempts": [
            {"operation": op, "result": "success"} for op in contract.PERMITTED_CASES
        ],
        "integrity": dict.fromkeys(contract.INTEGRITY_PROOFS, True),
        "etw": {
            **dict.fromkeys(contract.ETW_PROOFS, True),
            "unresolved-mutations": 0, "protected-successful-mutations": 0,
        },
    }


class ProtectedFixtureContractTests(unittest.TestCase):
    def test_plan_has_only_neutral_labels_and_performs_no_host_operations(self):
        plan = contract.contract_plan()
        self.assertEqual(plan["roots"], ["protected", "permitted"])
        self.assertEqual(plan["protected_attempts"], list(contract.PROTECTED_CASES))
        self.assertEqual(plan["permitted_attempts"], list(contract.PERMITTED_CASES))
        self.assertFalse(plan["writes_or_acl_changes_performed"])
        self.assertEqual(plan["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertNotIn("\\", json.dumps(plan))
        self.assertNotIn("C:", json.dumps(plan))

    def test_perfect_synthetic_receipt_never_earns_native_acceptance(self):
        result = contract.check_evidence_shape(synthetic_receipt())
        self.assertEqual(result["schema_status"], "SHAPE_COMPLETE")
        self.assertEqual(result["issues"], [])
        self.assertFalse(result["evidence_provenance_verified"])
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
        self.assertFalse(result["owner_native_execution_authorized"])

    def test_missing_duplicate_unknown_or_successful_protected_case_blocks(self):
        mutations = [
            lambda r: r["protected_attempts"].pop(),
            lambda r: r["protected_attempts"].__setitem__(1, copy.deepcopy(r["protected_attempts"][0])),
            lambda r: r["protected_attempts"][0].update(operation="unreviewed-write"),
            lambda r: r["protected_attempts"][0].update(result="success"),
            lambda r: r["protected_attempts"][0].update(result="unverified"),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                r = synthetic_receipt()
                mutation(r)
                self.assertEqual(contract.check_evidence_shape(r)["schema_status"], "BLOCKED")

    def test_permitted_positive_and_transient_replay_controls_are_required(self):
        for mutation, reason in [
            (lambda r: r["permitted_attempts"].pop(), "permitted-attempts-invalid"),
            (lambda r: r["permitted_attempts"][0].update(result="access-denied"),
             "permitted-expected-result-missing"),
            (lambda r: r["integrity"].update(**{"permitted-write-restore-verified": False}),
             "integrity-proof-unverified"),
            (lambda r: r["etw"].update(**{"permitted-transient-replay-observed": False}),
             "etw-proof-unverified"),
        ]:
            with self.subTest(reason=reason):
                r = synthetic_receipt()
                mutation(r)
                self.assertIn(reason, contract.check_evidence_shape(r)["issues"])

    def test_bad_token_privileges_ownership_and_identity_block(self):
        for key in contract.TOKEN_PROOFS:
            with self.subTest(key=key):
                r = synthetic_receipt()
                r["token"][key] = False
                self.assertIn("token-proof-unverified", contract.check_evidence_shape(r)["issues"])
        for mutation, reason in [
            (lambda r: r["token"].update(**{"unverified-extra": True}), "token-schema-invalid"),
            (lambda r: r.update(identity_model="runner-admin"), "identity-model-unverified"),
            (lambda r: r.update(roots=["protected", "other"]), "root-contract-invalid"),
        ]:
            with self.subTest(reason=reason):
                r = synthetic_receipt()
                mutation(r)
                self.assertIn(reason, contract.check_evidence_shape(r)["issues"])

    def test_etw_loss_unresolved_path_and_successful_protected_mutation_block(self):
        for mutation, reason in [
            (lambda r: r["etw"].update(**{"zero-loss-confirmed": False}), "etw-proof-unverified"),
            (lambda r: r["etw"].update(**{"file-operations-attributed": False}), "etw-proof-unverified"),
            (lambda r: r["etw"].update(**{"unresolved-mutations": 1}), "etw-mutations-unresolved"),
            (lambda r: r["etw"].update(**{"protected-successful-mutations": 1}), "etw-mutations-unresolved"),
            (lambda r: r["etw"].update(**{"unresolved-mutations": False}), "etw-mutations-unresolved"),
            (lambda r: r["etw"].pop("unresolved-mutations"), "etw-schema-invalid"),
        ]:
            with self.subTest(reason=reason):
                r = synthetic_receipt()
                mutation(r)
                self.assertIn(reason, contract.check_evidence_shape(r)["issues"])

    def test_all_integrity_and_cleanup_fields_are_required(self):
        for key in contract.INTEGRITY_PROOFS:
            with self.subTest(key=key):
                r = synthetic_receipt()
                r["integrity"][key] = False
                self.assertIn("integrity-proof-unverified", contract.check_evidence_shape(r)["issues"])

    def test_unknown_private_fields_cannot_be_reflected(self):
        r = synthetic_receipt()
        r["private-path"] = "C:\\private-owner\\sensitive.txt"
        r["protected_attempts"][0]["file-name"] = "private-secret"
        result = contract.check_evidence_shape(r)
        self.assertEqual(result["schema_status"], "BLOCKED")
        self.assertIn("receipt-schema-invalid", result["issues"])
        self.assertIn("protected-attempts-invalid", result["issues"])
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")

    def test_missing_or_invalid_receipt_fails_closed(self):
        for value in (None, [], {}, "not-a-receipt"):
            with self.subTest(kind=type(value).__name__):
                result = contract.check_evidence_shape(value)
                self.assertEqual(result["schema_status"], "BLOCKED")
                self.assertEqual(result["native_N12_acceptance"], "NOT_EVALUATED")
                self.assertFalse(result["owner_native_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
