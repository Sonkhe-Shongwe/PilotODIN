"""Isolated default for pytest collection, never the product data directory.

Explicit fixture homes supplied by existing CI and scoped QA remain unchanged.
The fallback here belongs to the test harness only, not backend storage.
"""
import atexit
import os
from pathlib import Path
import tempfile

if "PILOTODIN_HOME" not in os.environ:
    _collection_home = tempfile.TemporaryDirectory(prefix="pilotodin-pytest-collection-")
    os.environ["PILOTODIN_HOME"] = str(Path(_collection_home.name).resolve())
    atexit.register(_collection_home.cleanup)
