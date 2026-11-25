"""C4 candidate inventory from exact committed first-party Git blobs.

Reuse the existing C3 Git-only reader. Output paths, categories and line
numbers, never source snippets, keys, environment values or owner-local data.
Lexical candidates are review inputs, not complete runtime call/data-flow proof.
"""
from __future__ import annotations

from collections import Counter
import json
import re

from tools.c3_source_caller_inventory import committed_sources, git

# Exclude the scanner's own expressions and its synthetic tests, explicitly.
SELF = {
    "tools/c4_settings_inventory.py",
    "tests/test_c4_settings_inventory.py",
}

PATTERNS = {
    "settings-file": r"\b(?:resource_preferences\.json|ai_settings\.(?:json|tmp)|ai_secrets\.dpapi)\b",
    "settings-stage": r"\.(?:resource-policy|ai-settings|secrets)-",
    "settings-service": r"\b(?:ai_provider|resource_policy|settings_storage)\b",
    "settings-symbol": r"\b(?:CONFIG_PATH|SECRETS_PATH|_read_config|_stored_keys|_save_keys|config_status|update_settings|set_key|read_policy|save_policy|AISettingsRequest|AIKeyRequest|ResourcePolicyRequest|save_ai_settings|save_ai_key|update_resource_policy)\b",
    "settings-http": r"/(?:api/)?(?:resource/(?:policy|status|preflight)|ai/(?:settings|key|test|verify-connected|local/status)|projects/[^ \t\r\n]+/ai/insight)\b",
    "settings-schema": r"\b(?:cloud_enabled|share_aggregates|auto_insights|provider_order|preferred_provider|workspace_preferences|intelligence_mode|local_model_enabled|local_timeout_seconds)\b",
    "key-provider": r"\b(?:GEMINI_API_KEY|GROQ_API_KEY|OPENROUTER_API_KEY|ENV_KEYS|_memory_keys|_get_key|_consent_revision|CryptProtectData|CryptUnprotectData|_dpapi)\b",
    "workspace-ownership": r"\b(?:validate_process_write|hold_process_workspace|storage_home|check_write_path|guarded_unlink|_process_workspace)\b",
    "backup-build": r"\b(?:stage_workspace_backup|stage_database_snapshot|verify_staged_backup|restore_staged_backup|BACKUP_STAGE_NAME|PyInstaller|--add-data|--collect-data)\b|--add-data|--collect-data",
}
COMPILED = {name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in PATTERNS.items()}


def classify(source: str) -> dict[str, list[int]]:
    result = {}
    for name, pattern in COMPILED.items():
        lines = [i for i, line in enumerate(source.splitlines(), 1)
                 if pattern.search(line)]
        if lines:
            result[name] = lines
    return result


def main():
    sha = git("rev-parse", "HEAD").decode("ascii").strip()
    sources, undecodable, counts = committed_sources(sha)
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("Unexpected Git source identity")
    totals = Counter()
    matched = 0
    excluded = 0
    for path, source in sorted(sources.items()):
        if path in SELF:
            excluded += 1
            continue
        matches = classify(source)
        if not matches:
            continue
        matched += 1
        totals.update({name: len(lines) for name, lines in matches.items()})
        print("C4_INV " + json.dumps({"path": path, "matches": matches},
                                     sort_keys=True, ensure_ascii=True))
    print("C4_SUMMARY " + json.dumps({
        "sha": sha, "scope": counts, "excluded_scanner_blobs": excluded,
        "matched_files": matched, "line_counts": dict(totals),
        "undecodable_paths": undecodable,
        "limitation": "Lexical candidates only; review aliases, constructed paths and structural ownership separately.",
    }, sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    main()
