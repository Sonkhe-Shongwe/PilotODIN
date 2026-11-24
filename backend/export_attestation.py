"""B5: authenticate a prepared export receipt with a host/sidecar-only key.

A MAC binds exact prepared bytes and metadata, not client receipt, scratch
release, user consent or destination persistence. The key is launch-scoped.
"""
import hashlib
import hmac
import os
import re

try:
    from . import export_publication as ledger
except ImportError:
    import export_publication as ledger

KEY_ENV = "PILOTODIN_DATASET_EXPORT_KEY"
MAX_SAFE_INTEGER = (1 << 53) - 1
_INVALID = "Dataset export attestation unavailable"


def headers_for_transfer(receipt, filename, rows):
    key = os.environ.get(KEY_ENV)
    if key is None:
        return {}  # Browser-only and older sidecars remain compatible.
    session = os.environ.get("PILOTODIN_DESKTOP_SESSION", "")
    if not session or not re.fullmatch(r"[0-9a-f]{64}", key) or key == session:
        raise ledger.PublicationError(_INVALID)
    receipt.validate()
    if (receipt.state != "transferring"
            or not 0 <= receipt.quality_version <= MAX_SAFE_INTEGER
            or type(rows) is not int or not 0 <= rows <= MAX_SAFE_INTEGER
            or not isinstance(filename, str)
            or not re.fullmatch(
                rf"[A-Za-z0-9_-]{{1,70}}_cleaned_v{receipt.quality_version}(?:_filtered)?\.{receipt.format}",
                filename)):
        raise ledger.PublicationError(_INVALID)
    message = "\n".join(("PilotODIN/export-receipt/v1", receipt.project_id,
                         receipt.operation_id, str(receipt.quality_version), receipt.format,
                         str(receipt.expected_bytes), receipt.sha256, filename, str(rows), ""))
    mac = hmac.new(key.encode("ascii"), message.encode("ascii"), hashlib.sha256).hexdigest()
    return {"X-PilotODIN-Export-Project": receipt.project_id,
            "X-PilotODIN-Export-Operation": receipt.operation_id,
            "X-PilotODIN-Export-MAC": mac}
