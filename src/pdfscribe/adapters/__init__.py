"""Adapters - re-exports."""

from __future__ import annotations

from pdfscribe.adapters.file_io import write_transcript  # noqa: F401
from pdfscribe.adapters.pdf_text_reader import PdfTextReader  # noqa: F401

__all__ = ["PdfTextReader", "write_transcript"]
