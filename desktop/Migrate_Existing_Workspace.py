"""Suspended legacy desktop migration.

The old copy-and-replace procedure did not coordinate with the desktop and
backend writer leases. Do not access production or historical data through it.
Its implementation remains in Git history; Package B must supply a reviewed
migration design before a separately authorized live operation.
"""
from pathlib import Path
import sys


def migrate(source_inner_folder: Path, destination_data: Path) -> tuple[int, int]:
    """Refuse before inspecting, creating or modifying any workspace."""
    raise ValueError("Legacy desktop migration suspended; no workspace was accessed.")


def main() -> int:
    print("Legacy desktop migration suspended. Existing data is preserved in place.", file=sys.stderr)
    print("A separately reviewed migration is required. No files were accessed.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
