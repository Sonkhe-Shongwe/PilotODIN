"""Shared PDFium fixture bodies, no pytest or native import at module import."""
import unittest
from unittest.mock import patch

from tools import pdf_test_inspection as qa


def disarmed_gate_check():
    with patch.object(qa, "PDFIUM_TEST_EXECUTION_ENABLED", False), \
            patch("importlib.metadata.version") as version:
        with unittest.TestCase().assertRaisesRegex(
                RuntimeError, "C5_PDFIUM_TEST_EXECUTION_DISARMED"):
            qa.require_pdfium()
        version.assert_not_called()


def malformed_eof_check():
    qa.require_pdfium()
    from pypdfium2 import PdfiumError
    malformed = b"%PDF-1.4\nnot a PDF object or page tree\n%%EOF\n"
    # A valid suffix alone cannot make this a generated report.
    qa._check_generated_pdf(malformed)
    with unittest.TestCase().assertRaises((PdfiumError, ValueError)):
        qa.inspect_pdf(malformed)
