"""Source-only N12 protected fixture contract. No host operations or N12 acceptance."""
from collections import Counter

SCOPE = "n12-generated-protected-fixture-v1"
ROOTS = ("protected", "permitted")
IDENTITY_MODEL = "restricted-primary-token"
PROTECTED_CASES = (
    "create", "overwrite", "truncate", "rename-into", "rename-out",
    "delete", "write-restore", "change-acl", "take-ownership",
)
PERMITTED_CASES = ("create", "write-restore")
TOKEN_PROOFS = (
    "primary-token-verified", "restricting-sid-verified",
    "admin-sid-deny-only", "privilege-bypass-removed",
    "protected-owner-distinct", "effective-acl-verified",
)
INTEGRITY_PROOFS = (
    "protected-tree-content-match", "protected-tree-metadata-match",
    "protected-tree-identity-match", "permitted-write-restore-verified",
    "runner-cleanup-verified",
)
ETW_PROOFS = (
    "zero-loss-confirmed", "process-lifetimes-bound",
    "file-operations-attributed", "permitted-transient-replay-observed",
)
TOP_KEYS = frozenset({
    "scope", "roots", "identity_model", "token",
    "protected_attempts", "permitted_attempts", "integrity", "etw",
})


def contract_plan():
    """Names and obligations only; no operating-system reads or writes."""
    return {
        "scope": SCOPE,
        "roots": list(ROOTS),
        "identity_model": IDENTITY_MODEL,
        "protected_attempts": list(PROTECTED_CASES),
        "permitted_attempts": list(PERMITTED_CASES),
        "token_proofs": list(TOKEN_PROOFS),
        "integrity_proofs": list(INTEGRITY_PROOFS),
        "etw_proofs": list(ETW_PROOFS),
        "writes_or_acl_changes_performed": False,
        "native_N12_acceptance": "NOT_EVALUATED",
    }


def _boolean_proofs(proofs, keys, label, issues):
    if not isinstance(proofs, dict) or set(proofs) != set(keys):
        issues.add(f"{label}-schema-invalid")
        return
    if any(proofs[key] is not True for key in keys):
        issues.add(f"{label}-proof-unverified")


def _attempts(rows, expected, result, label, issues):
    if not isinstance(rows, list) or len(rows) != len(expected):
        issues.add(f"{label}-attempts-invalid")
        return
    seen = Counter()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"operation", "result"}
                or not isinstance(row.get("operation"), str)
                or row["operation"] not in expected
                or not isinstance(row.get("result"), str)
                or row["result"] not in {"access-denied", "success", "unverified"}):
            issues.add(f"{label}-attempts-invalid")
            continue
        seen[row["operation"]] += 1
        if row["result"] != result:
            issues.add(f"{label}-expected-result-missing")
    if set(seen) != set(expected) or any(count != 1 for count in seen.values()):
        issues.add(f"{label}-attempts-invalid")


def check_evidence_shape(receipt):
    """Check only the schema. No assertion of native truth or collector completeness."""
    issues = set()
    if not isinstance(receipt, dict):
        issues.add("receipt-invalid")
    else:
        if set(receipt) != TOP_KEYS:
            issues.add("receipt-schema-invalid")
        if receipt.get("scope") != SCOPE:
            issues.add("scope-invalid")
        if not isinstance(receipt.get("roots"), list) or receipt["roots"] != list(ROOTS):
            issues.add("root-contract-invalid")
        if receipt.get("identity_model") != IDENTITY_MODEL:
            issues.add("identity-model-unverified")
        _boolean_proofs(receipt.get("token"), TOKEN_PROOFS, "token", issues)
        _attempts(receipt.get("protected_attempts"), PROTECTED_CASES,
                  "access-denied", "protected", issues)
        _attempts(receipt.get("permitted_attempts"), PERMITTED_CASES,
                  "success", "permitted", issues)
        _boolean_proofs(receipt.get("integrity"), INTEGRITY_PROOFS, "integrity", issues)
        etw = receipt.get("etw")
        if (not isinstance(etw, dict)
                or set(etw) != {*ETW_PROOFS, "unresolved-mutations", "protected-successful-mutations"}):
            issues.add("etw-schema-invalid")
        else:
            if any(etw[name] is not True for name in ETW_PROOFS):
                issues.add("etw-proof-unverified")
            if (type(etw["unresolved-mutations"]) is not int or etw["unresolved-mutations"] != 0
                    or type(etw["protected-successful-mutations"]) is not int
                    or etw["protected-successful-mutations"] != 0):
                issues.add("etw-mutations-unresolved")
    return {
        "scope": SCOPE,
        "schema_status": "BLOCKED" if issues else "SHAPE_COMPLETE",
        "issues": sorted(issues),
        "evidence_provenance_verified": False,
        "native_N12_acceptance": "NOT_EVALUATED",
        "owner_native_execution_authorized": False,
    }
