#!/usr/bin/env python3
"""Stage official, pinned candidate fonts inside disposable DevQA only.

Developer-only tool. Explicit --download required. No application-time network,
install, OS font changes, user project access, font redistribution or product
renderer modifications. STAGED is not approval or PDF visual acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from qa_foundation import default_root, safe_root
from p2_pdf_font_asset_gate import verify

HOST = "raw.githubusercontent.com"
MANIFEST = Path(__file__).with_name("p2_pdf_font_candidates.json")
MAX_BYTES = 32 * 1024 * 1024


class CandidateStageError(Exception):
    """Failure context for one pinned public asset, without traceback output."""
    def __init__(self, asset, source_path, stage, cause):
        self.asset = asset
        self.source_path = source_path
        self.stage = stage
        self.cause = cause
        super().__init__(type(cause).__name__)


def describe_candidate_failure(error, commit):
    """Report an actionable but bounded network diagnosis, never credentials."""
    cause = error.cause
    reason = (cause.reason if isinstance(cause, urllib.error.URLError)
              and not isinstance(cause, urllib.error.HTTPError) else cause)
    summary = str(reason).replace("\r", " ").replace("\n", " ")
    # Network errors can contain proxy URLs, tokens or machine-local paths.
    summary = re.sub(r"(?i)https?://\S+", "[URL REDACTED]", summary)
    summary = re.sub(
        r"(?i)\b(?:password|token|authorization|secret)\s*[:=]\s*\S+",
        "[CREDENTIAL REDACTED]", summary)
    summary = re.sub(r"[A-Za-z]:\\[^\s]+", "[LOCAL PATH REDACTED]", summary)
    summary = summary[:180]
    lower = summary.lower()
    status = getattr(cause, "code", None) if isinstance(
        cause, urllib.error.HTTPError) else None
    errno = getattr(reason, "errno", None)
    if isinstance(cause, urllib.error.HTTPError):
        category = "HTTP_STATUS"
    elif isinstance(reason, socket.gaierror) or any(
            term in lower for term in ("getaddrinfo", "name or service not known",
                                       "nodename nor servname", "no such host")):
        category = "DNS_RESOLUTION"
    elif isinstance(reason, ssl.SSLCertVerificationError) or any(
            term in lower for term in ("certificate_verify_failed", "certificate verify failed",
                                       "self-signed certificate", "unable to get local issuer")):
        category = "TLS_CERTIFICATE"
    elif "proxy" in lower or "tunnel connection failed" in lower:
        category = "PROXY_OR_GATEWAY"
    elif isinstance(reason, ssl.SSLError) or "ssl" in lower or "tls" in lower:
        category = "TLS_OTHER"
    elif isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in lower:
        category = "TIMEOUT"
    elif isinstance(reason, ConnectionRefusedError):
        category = "CONNECTION_REFUSED"
    elif isinstance(reason, ConnectionResetError):
        category = "CONNECTION_RESET"
    elif isinstance(cause, urllib.error.URLError):
        category = "NETWORK_OTHER"
    elif error.stage == "identity_verification":
        category = "ASSET_INTEGRITY"
    else:
        category = "LOCAL_STAGING_OR_VALIDATION"
    path = error.source_path
    # The public source contains no private data; never emit a redirect/proxy URL.
    source_url = ("https://" + HOST + "/google/fonts/" + commit + "/" +
                  urllib.parse.quote(path, safe="/")
                  if re.fullmatch(r"ofl/[a-z0-9]+/[A-Za-z0-9_.\[\],-]+", path)
                  else "PINNED_SOURCE_PATH_INVALID")
    return {
        "state": "BLOCKED",
        "asset": error.asset,
        "stage": error.stage,
        "source_url": source_url,
        "failure_class": type(cause).__name__,
        "reason_class": type(reason).__name__,
        "reason_category": category,
        "reason_excerpt": summary,
        "reason_errno": errno if isinstance(errno, int) else None,
        "http_status": status,
        "product_acceptance": "NOT_TESTED",
    }


def destination():
    root = safe_root(default_root() / "font-candidates", ROOT)
    for node in (root, *root.parents):
        if node.exists() and (node.is_symlink() or
                              getattr(os.path, "isjunction", lambda _: False)(node)):
            raise ValueError("Redirected staging path")
    root.mkdir(parents=True, exist_ok=True)
    return root


def checksum(path, expected_size, expected_blob):
    if (not path.is_file() or path.is_symlink() or
            path.stat().st_size != expected_size):
        raise ValueError("Incorrect, missing or redirected candidate asset")
    git = hashlib.sha1(b"blob " + str(expected_size).encode("ascii") + b"\0")
    sha256 = hashlib.sha256()
    with path.open("rb") as data:
        for chunk in iter(lambda: data.read(1024 * 1024), b""):
            git.update(chunk)
            sha256.update(chunk)
    if git.hexdigest() != expected_blob:
        raise ValueError("Downloaded bytes differ from pinned Git blob")
    return sha256.hexdigest()


def stage_one(root, commit, source_path, filename, expected_size, blob, opener):
    stage = "metadata_validation"
    try:
        if (Path(filename).name != filename or filename in (".", "..") or
                not source_path.startswith("ofl/") or ".." in source_path.split("/") or
                not isinstance(expected_size, int) or
                not 0 < expected_size <= MAX_BYTES or
                len(blob) != 40 or any(c not in "0123456789abcdef" for c in blob)):
            raise ValueError("Invalid pinned asset identity")
        output = root / filename
        stage = "existing_identity"
        if output.exists() or output.is_symlink():
            return {"file": filename, "sha256": checksum(output, expected_size, blob),
                    "source": "existing_verified"}
        url = ("https://" + HOST + "/google/fonts/" + commit + "/" +
               urllib.parse.quote(source_path, safe="/"))
        partial = root / (filename + "." + uuid.uuid4().hex + ".partial")
        try:
            stage = "connection"
            with opener(url, timeout=45) as response:
                final = urllib.parse.urlparse(response.geturl())
                if final.scheme != "https" or final.hostname != HOST:
                    raise ValueError("Unexpected download redirect")
                remaining = expected_size
                stage = "transfer"
                with partial.open("xb") as file:
                    while True:
                        block = response.read(min(1024 * 1024, remaining + 1))
                        if not block:
                            break
                        remaining -= len(block)
                        if remaining < 0:
                            raise ValueError("Oversized downloaded candidate")
                        file.write(block)
            stage = "identity_verification"
            sha = checksum(partial, expected_size, blob)
            stage = "publication"
            if output.exists() or output.is_symlink():
                raise FileExistsError("Candidate path changed during download")
            partial.rename(output)
            return {"file": filename, "sha256": sha, "source": "pinned_download"}
        finally:
            try:
                partial.unlink(missing_ok=True)
            except OSError:
                pass
    except Exception as exc:
        raise CandidateStageError(filename, source_path, stage, exc) from exc

def stage_all(root, manifest, opener=urllib.request.urlopen):
    if (manifest.get("schema") != 1 or
            manifest.get("source_repo") != "google/fonts" or
            manifest.get("status") != "CANDIDATES_UNVERIFIED_DO_NOT_SHIP"):
        raise ValueError("Unverified source manifest")
    commit = manifest["source_commit"]
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("Unpinned source commit")
    assets = manifest["assets"]
    if (len(assets) != 3 or
            {x["role"] for x in assets} != {"regular", "cjk", "symbol"}):
        raise ValueError("Unexpected font roles")
    names = [x[key] for x in assets for key in ("filename", "license_filename")]
    if len(set(names)) != 6:
        raise ValueError("Duplicate staged asset filenames")
    receipt = []
    for entry in assets:
        for name, upstream, size, blob in (
            (entry["filename"], entry["relative_path"],
             entry["bytes"], entry["git_blob_sha1"]),
            (entry["license_filename"], entry["license_path"],
             entry["license_bytes"], entry["license_git_blob_sha1"]),
        ):
            receipt.append(stage_one(root, commit, upstream, name, size, blob, opener))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true",
                        help="Explicit opt-in to fetch only six pinned public assets")
    args = parser.parse_args()
    if not args.download:
        print(json.dumps({"state": "NOT_STARTED",
                          "reason": "Explicit --download required; no files written"}))
        return 2
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        root = destination()
        receipts = stage_all(root, manifest)
        candidate = verify(root, manifest)
        print(json.dumps({"state": "STAGED_FOR_REVIEW",
                          "product_acceptance": "NOT_TESTED",
                          "download_receipts": receipts,
                          "asset_probe": candidate}, ensure_ascii=False, indent=2))
        return 0 if candidate["state"] == "CANDIDATE_FILE_AND_CMAP_PROBE_PASS" else 2
    except CandidateStageError as exc:
        print(json.dumps(describe_candidate_failure(exc, manifest["source_commit"]),
                         ensure_ascii=False, indent=2))
        return 2
    except Exception as exc:
        print(json.dumps({"state": "BLOCKED",
                          "stage": "setup_or_aggregate_verification",
                          "failure_class": type(exc).__name__,
                          "product_acceptance": "NOT_TESTED"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
