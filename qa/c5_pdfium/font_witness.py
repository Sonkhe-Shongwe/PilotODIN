"""Synthetic font witness adapter: existing predicates, no owner CLI."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from qa.c5_pdfium import staged_executor as executor


def run(mode, root):
    executor.require_live()
    from tools.pdf_test_inspection import require_pdfium
    require_pdfium()
    root = Path(root)
    executor.owned(root, Path(__import__("os").environ["LOCALAPPDATA"]))
    sys.path.insert(0, str(executor.ROOT / "tools"))
    from p2_pdf_font_build_preflight import audited_sources
    from p2_pdf_cmap_scoped_devqa import render_child, run_unit_worker
    from p2_pdf_unicode_context_devqa import (
        probe_in_memory, selected_review_sources, register_scoped_faces,
        verified_font_coverage, FONT_NAMES,
    )
    from p2_pdf_font_coverage_probe import audit
    from p2_pdf_tounicode_research import local_experiment
    manifest = executor.stages.strict_json(executor.stages.pinned(
        "tools/p2_pdf_font_candidates.json", "73c49622be94353123af3dd99fe88326c0696cdd"))
    entries = audited_sources(root, manifest)
    if mode == "unit":
        return run_unit_worker()
    if mode in ("baseline", "corrected"):
        from qa_foundation import default_root
        executor.need(root == default_root() / "font-candidates", "FONT_CANDIDATE_ROOT")
        return render_child(mode)
    if mode == "context":
        return probe_in_memory(root, entries)
    if mode == "coverage":
        paths = selected_review_sources(root, entries)
        return audit({"regular": paths["regular"], "cjk": paths["cjk"],
                      "emoji": paths["symbol"]})
    if mode == "research":
        return local_experiment(root, manifest)
    if mode == "actual":
        from p2_actual_unicode_report_devqa import proof_bytes, synthetic_revision
        from backend.pdf_unicode_seam import UnicodePDFContext
        fonts = register_scoped_faces(selected_review_sources(root, entries))
        context = UnicodePDFContext(FONT_NAMES, fonts, verified_font_coverage(fonts))
        _, evidence = proof_bytes(synthetic_revision(), context)
        return evidence
    raise ValueError("FONT_MODE")


if __name__ == "__main__":
    executor.require_live()
    if len(sys.argv) != 3:
        raise ValueError("FONT_ARGUMENTS")
    print(json.dumps(run(sys.argv[1], sys.argv[2]), ensure_ascii=True, sort_keys=True))
