"""P2-U2d DevQA runtime hook template. NOT registered in production.

The isolated DevQA controller copies this file into a new ignored workdir,
substituting the one pinned literal below with six independently reverified
source hashes. PyInstaller runs this hook BEFORE importing the real sidecar.
Never package this unchanged template or copy it into the release builder.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

PINNED_ASSETS = None  # P2_REPLACE_WITH_VERIFIED_SIX_FILE_LITERAL


def verify_p2_devqa_frozen_resources() -> None:
    if os.environ.get("PILOTODIN_P2_REAL_SIDECAR_DEVQA") != "1":
        raise RuntimeError("DevQA sidecar execution consent marker absent")
    home = Path(os.environ.get("PILOTODIN_HOME", ""))
    if (home.name != "isolated-user-data" or
            not home.parent.name.startswith("pilotodin-engine-smoke-")):
        raise RuntimeError("DevQA sidecar home is not the disposable smoke directory")
    if (not getattr(sys, "frozen", False) or
            not isinstance(getattr(sys, "_MEIPASS", None), str)):
        raise RuntimeError("Real sidecar is not running inside a frozen bundle")
    bundle = Path(sys._MEIPASS).resolve(strict=True)
    from backend import pdf_font_resources
    module = Path(pdf_font_resources.__file__).resolve(strict=False)
    if not module.is_relative_to(bundle):
        raise RuntimeError("Font validator did not originate in the frozen bundle")
    root = pdf_font_resources.resolve_pdf_font_root()
    if root != module.parent / "assets" / "pdf_fonts" or not root.resolve().is_relative_to(bundle):
        raise RuntimeError("Unexpected extracted font resource location")
    if not isinstance(PINNED_ASSETS, list) or len(PINNED_ASSETS) != 6:
        raise RuntimeError("Missing code-pinned DevQA font identities")
    if {p.name for p in root.iterdir()} != {entry["name"] for entry in PINNED_ASSETS}:
        raise RuntimeError("Unexpected or missing bundled font files")
    if len(pdf_font_resources.verify_pdf_font_files(PINNED_ASSETS)) != 6:
        raise RuntimeError("Incomplete bundled font verification")
    # A concrete DevQA-only receipt proves this hook actually executed INSIDE
    # the real frozen engine, rather than relying on smoke success by inference.
    proof = Path(os.environ.get("PILOTODIN_P2_DEVQA_ATTESTATION", ""))
    if (not proof.is_absolute() or proof.name != "font-attestation.json" or
            not proof.parent.name.startswith("run-") or
            proof.parent.parent.name != "real-sidecar-proofs" or
            proof.parent.parent.parent.name != "p2-sidecar-env"):
        raise RuntimeError("Missing or invalid DevQA attestation destination")
    for part in (proof.parent, *proof.parent.parents):
        if part.is_symlink() or (part.exists() and
                                 getattr(os.path, "isjunction", lambda _: False)(part)):
            raise RuntimeError("Redirected DevQA attestation directory")
    identities = sorted((item["name"], item["bytes"], item["sha256"])
                        for item in PINNED_ASSETS)
    digest = hashlib.sha256(json.dumps(identities, separators=(",", ":")).encode()).hexdigest()
    receipt = {"schema": 1, "state": "FROZEN_REAL_SIDECAR_FONT_FILES_VERIFIED",
               "embedded_file_count": 6, "font_identity_digest": digest,
               "from_frozen_hook": True}
    with proof.open("x", encoding="utf-8") as sink:
        json.dump(receipt, sink, sort_keys=True)


verify_p2_devqa_frozen_resources()
