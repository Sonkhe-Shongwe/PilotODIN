"""Read-only Win32 API export capability probe for future N12 restricted-writer fixture.

Only loads system DLLs and resolves function addresses. Never invokes token,
ACL, process creation or file operations. API presence is NOT security evidence.
"""
import ctypes
import json
import os
import sys


SCOPE = "n12-restricted-token-capability-surface-v1"
EXPORTS = {
    "advapi32.dll": (
        "OpenProcessToken",
        "CreateRestrictedToken",
        "DuplicateTokenEx",
        "GetTokenInformation",
        "IsTokenRestricted",
        "AccessCheck",
        "GetNamedSecurityInfoW",
        "CreateProcessAsUserW",
    ),
    "kernel32.dll": (
        "GetCurrentProcess",
        "CloseHandle",
    ),
}
TOKEN_INFORMATION_CLASSES_TO_VERIFY_LATER = (
    "TokenType", "TokenGroups", "TokenRestrictedSids", "TokenPrivileges", "TokenOwner",
)
PRIVILEGES_TO_EXCLUDE_FROM_WRITER = (
    "SeTakeOwnershipPrivilege", "SeRestorePrivilege", "SeBackupPrivilege",
    "SeSecurityPrivilege", "SeDebugPrivilege", "SeImpersonatePrivilege",
)
FUTURE_PROOF_REQUIREMENTS = (
    "primary-token-type",
    "nonempty-restricted-sids",
    "administrators-deny-only",
    "privilege-bypass-absent",
    "protected-owner-distinct",
    "effective-protected-write-denied",
    "effective-permitted-write-granted",
    "same-writer-permitted-positive-control",
)


def capability_plan():
    """Static requirements, never a claim about the actual Windows host."""
    return {
        "scope": SCOPE,
        "exports": {name: list(symbols) for name, symbols in EXPORTS.items()},
        "token_information": list(TOKEN_INFORMATION_CLASSES_TO_VERIFY_LATER),
        "privileges_to_exclude": list(PRIVILEGES_TO_EXCLUDE_FROM_WRITER),
        "future_proofs": list(FUTURE_PROOF_REQUIREMENTS),
        "accesscheck_requires_impersonation_token": True,
        "restricted_token_proves_global_app_containment": False,
        "no_host_mutation": True,
        "native_N12_acceptance": "NOT_EVALUATED",
    }


def inspect_api_surface(*, platform=None, loader=None):
    """Resolve exports only. Never call any resolved function.

    platform/loader injection allows synthetic failure tests without Windows.
    """
    issues = set()
    observed = 0
    expected = sum(len(symbols) for symbols in EXPORTS.values())
    host = os.name if platform is None else platform
    if host != "nt":
        issues.add("windows-host-required")
    else:
        load = getattr(ctypes, "WinDLL", None) if loader is None else loader
        if not callable(load):
            issues.add("windows-dll-loader-unavailable")
        else:
            for library, symbols in EXPORTS.items():
                label = library.removesuffix(".dll")
                try:
                    module = load(library)
                except Exception:
                    issues.add(label + "-load-unverified")
                    continue
                for symbol in symbols:
                    try:
                        pointer = getattr(module, symbol)
                        found = callable(pointer)
                    except Exception:
                        found = False
                    if not found:
                        issues.add(label + "-api-unavailable:" + symbol)
                    else:
                        observed += 1
    return {
        "scope": SCOPE,
        "api_surface_status": "PRESENT" if not issues and observed == expected else "BLOCKED",
        "issues": sorted(issues),
        "exports_observed": observed,
        "exports_expected": expected,
        "native_token_created": False,
        "token_attributes_verified": False,
        "restricted_writer_launched": False,
        "acl_modified": False,
        "file_access_attempted": False,
        "file_protection_verified": False,
        "api_evidence_proves_security": False,
        "native_N12_acceptance": "NOT_EVALUATED",
        "owner_native_execution_authorized": False,
    }


def main():
    report = inspect_api_surface()
    print(json.dumps(report, sort_keys=True))
    return 0 if report["api_surface_status"] == "PRESENT" else 2


if __name__ == "__main__":
    sys.exit(main())
