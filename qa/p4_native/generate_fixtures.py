"""Generate an isolated P4 native acceptance kit using ONLY synthetic data.

No network, model training, project database or source-file edits. The output
directory must not already exist, even when it is empty.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
from pathlib import Path

CASE_ORDER = (
    "classification",
    "regression",
    "rare_class",
    "insufficient_labels",
    "no_named_target",
)
ROW_COUNT = 80
SUITE_ID = "p4-native-v1"


def _make_rows(case: str) -> tuple[list[str], list[list[object]]]:
    base = ["account_id", "feature"]
    if case == "classification":
        header = base + ["churn", "fraud_reported", "failure_flag", "outcome", "future_cost"]
    elif case == "regression":
        header = base + ["future_cost"]
    elif case in ("rare_class", "insufficient_labels"):
        header = base + ["churn"]
    elif case == "no_named_target":
        header = base + ["generic_measure"]
    else:
        raise ValueError("Unrecognised P4 acceptance case")

    rows = []
    for i in range(ROW_COUNT):
        row: list[object] = [f"P4-SYNTH-{i // 2:03}", i % 9]
        if case == "classification":
            row += [
                "Y" if i % 2 else "N",
                "Y" if i % 3 == 0 else "N",
                "Y" if i % 4 == 0 else "N",
                "completed" if i % 2 else "pending",
                f"{110.5 + i:.2f}",
            ]
        elif case == "regression":
            row += [f"{110.5 + i:.2f}"]
        elif case == "rare_class":
            row += ["N" if i >= 76 else "Y"]
        elif case == "insufficient_labels":
            row += ["Y" if i % 2 else "N" if i < 24 else ""]
            # Exactly 24 labelled rows; blanks are missing label values.
            row[-1] = ("Y" if i % 2 else "N") if i < 24 else ""
        else:
            row += [i * 3]
        rows.append(row)
    return header, rows


def fixture_contents() -> dict[str, bytes]:
    """Deterministic CSV output with no real user data or random seed."""
    result = {}
    for case in CASE_ORDER:
        header, rows = _make_rows(case)
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
        result[f"p4_{case}.csv"] = buffer.getvalue().encode("utf-8")
    return result


def manifest_for(fixtures: dict[str, bytes]) -> dict:
    return {
        "suite_id": SUITE_ID,
        "synthetic_only": True,
        "intended_rows_per_file": ROW_COUNT,
        "target_version": "owner-must-confirm-actual-installed-native-build",
        "verification_state": "UNTESTED",
        "sha256": {name: hashlib.sha256(data).hexdigest()
                   for name, data in fixtures.items()},
        "note": "Fixture integrity only, never application provenance or acceptance.",
    }


def create_kit(destination: Path) -> Path:
    """Create a *new* directory. Never overwrite any existing user files."""
    destination = destination.expanduser()
    destination.mkdir(parents=False, exist_ok=False)
    fixtures = fixture_contents()
    source_dir = Path(__file__).resolve().parent
    material = {
        **fixtures,
        "MANIFEST.json": (
            json.dumps(manifest_for(fixtures), indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        "README.md": (source_dir / "README.md").read_bytes(),
        "RESULTS_TEMPLATE.md": (source_dir / "RESULTS_TEMPLATE.md").read_bytes(),
    }
    for filename, data in material.items():
        with (destination / filename).open("xb") as file:
            file.write(data)
    return destination


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: py qa/p4_native/generate_fixtures.py "
            "<new-empty-parent/nonexistent-folder>"
        )
    try:
        print(f"Created synthetic P4 native acceptance kit: {create_kit(Path(sys.argv[1]))}")
    except (FileExistsError, OSError) as exc:
        raise SystemExit(
            "Refused to overwrite or could not create the destination: "
            f"{exc}"
        ) from exc
