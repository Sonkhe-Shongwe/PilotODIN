"""Retired checkout-to-checkout importer.

The checkout data root is no longer a supported runtime destination.
Previous implementation remains in Git history. Existing files stay untouched.
Any future live migration requires a separately reviewed and authorized path.
"""
from pathlib import Path
import sys


def migrate(source_project: Path, destination_project: Path) -> tuple[int, int]:
    """Fail closed before reading, copying or modifying any workspace."""
    raise ValueError("Legacy checkout migration retired; no data was accessed.")


def main() -> int:
    print("Legacy checkout migration retired. Existing data is preserved in place.", file=sys.stderr)
    print("A separately reviewed migration is required. No files were accessed.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
