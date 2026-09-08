"""Adapters - re-exports."""

from __future__ import annotations

from pdfscribe.adapters.file_io import write_transcript  # noqa: F401
from pdfscribe.adapters.pdf_document import open_document  # noqa: F401
from pdfscribe.adapters.pdf_rasterizer import PdfRasterizer  # noqa: F401
from pdfscribe.adapters.pdf_text_reader import PdfTextReader  # noqa: F401
from pdfscribe.adapters.tesseract_ocr import TesseractOcr, tesseract_path  # noqa: F401

__all__ = [
    "PdfRasterizer",
    "PdfTextReader",
    "TesseractOcr",
    "open_document",
    "tesseract_path",
    "write_transcript",
]
