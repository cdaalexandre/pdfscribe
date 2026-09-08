"""Tests - tesseract adapter, integration with the real binary.

Skipped when tesseract is absent: a missing external binary must never
turn the pipeline red (PLAYBOOK, Fase 5). The OCR engine is never faked
here - a Fake belongs in the service layer, where the boundary is ours.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pymupdf
import pytest

from pdfscribe.adapters.pdf_rasterizer import PdfRasterizer
from pdfscribe.adapters.tesseract_ocr import TesseractOcr, tesseract_path

if TYPE_CHECKING:
    from pathlib import Path

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="tesseract binary not installed",
)


def _make_pdf(path: Path, lines: list[str]) -> None:
    """Build a one-page PDF holding the given lines."""
    doc = pymupdf.open()
    page = doc.new_page()
    for index, line in enumerate(lines):
        page.insert_text((72, 100 + index * 30), line, fontsize=18)
    doc.save(str(path))
    doc.close()


class TestTesseractPath:
    """Tests for the binary lookup."""

    def test_returns_a_path_or_none(self) -> None:
        found = tesseract_path()
        assert found is None or isinstance(found, str)


@needs_tesseract
class TestTesseractOcr:
    """Integration tests that run the real engine."""

    def test_reads_words_from_a_rendered_page(self, tmp_path: Path) -> None:
        pdf = tmp_path / "sample.pdf"
        _make_pdf(pdf, ["TRIBUNAL DE JUSTICA"])
        image = PdfRasterizer().render(pdf, 1, dpi=300)
        outcome = TesseractOcr().read(image, lang="por")
        assert "TRIBUNAL" in outcome.text.upper()

    def test_reports_confidence(self, tmp_path: Path) -> None:
        pdf = tmp_path / "sample.pdf"
        _make_pdf(pdf, ["TRIBUNAL DE JUSTICA"])
        image = PdfRasterizer().render(pdf, 1, dpi=300)
        outcome = TesseractOcr().read(image, lang="por")
        assert 0.0 < outcome.confidence <= 1.0
        assert outcome.words > 0

    def test_keeps_line_structure(self, tmp_path: Path) -> None:
        # A transcription that collapses lines is not a faithful copy.
        pdf = tmp_path / "sample.pdf"
        _make_pdf(pdf, ["PRIMEIRA LINHA", "SEGUNDA LINHA"])
        image = PdfRasterizer().render(pdf, 1, dpi=300)
        outcome = TesseractOcr().read(image, lang="por")
        assert len(outcome.text.splitlines()) >= 2

    def test_blank_page_reads_as_empty(self, tmp_path: Path) -> None:
        pdf = tmp_path / "blank.pdf"
        _make_pdf(pdf, [])
        image = PdfRasterizer().render(pdf, 1, dpi=150)
        outcome = TesseractOcr().read(image, lang="por")
        assert outcome.text.strip() == ""
        assert outcome.words == 0
