"""Tests - pdf_rasterizer adapter, integration with a real document.

Percival & Gregory, Architecture Patterns, Cap. 5:
'Integration tests exercise the adapter against the real dependency,
isolated with tmp_path.'
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pymupdf
import pytest

from pdfscribe.adapters.pdf_rasterizer import PdfRasterizer

if TYPE_CHECKING:
    from pathlib import Path

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _make_pdf(path: Path, pages: int = 2) -> None:
    """Build a small multi-page PDF at path."""
    doc = pymupdf.open()
    for number in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Pagina {number + 1}")
    doc.save(str(path))
    doc.close()


class TestPdfRasterizer:
    """Integration tests for the page rasterizer."""

    def test_renders_png_bytes(self, tmp_path: Path) -> None:
        pdf = tmp_path / "sample.pdf"
        _make_pdf(pdf)
        data = PdfRasterizer().render(pdf, 1, dpi=72)
        assert data.startswith(PNG_MAGIC)

    def test_higher_dpi_produces_more_pixels(self, tmp_path: Path) -> None:
        pdf = tmp_path / "sample.pdf"
        _make_pdf(pdf)
        rasterizer = PdfRasterizer()
        assert len(rasterizer.render(pdf, 1, dpi=200)) > len(rasterizer.render(pdf, 1, dpi=72))

    def test_renders_each_page(self, tmp_path: Path) -> None:
        pdf = tmp_path / "sample.pdf"
        _make_pdf(pdf, pages=3)
        rasterizer = PdfRasterizer()
        for number in (1, 2, 3):
            assert rasterizer.render(pdf, number, dpi=72).startswith(PNG_MAGIC)

    def test_rejects_page_zero(self, tmp_path: Path) -> None:
        pdf = tmp_path / "sample.pdf"
        _make_pdf(pdf)
        with pytest.raises(ValueError, match="outside the document"):
            PdfRasterizer().render(pdf, 0, dpi=72)

    def test_rejects_page_past_the_end(self, tmp_path: Path) -> None:
        pdf = tmp_path / "sample.pdf"
        _make_pdf(pdf, pages=2)
        with pytest.raises(ValueError, match="outside the document"):
            PdfRasterizer().render(pdf, 3, dpi=72)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            PdfRasterizer().render(tmp_path / "nope.pdf", 1, dpi=72)
