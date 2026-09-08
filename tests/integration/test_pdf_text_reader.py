"""Tests - pdf_text_reader adapter, integration with a real fitz PDF.

Percival & Gregory, Architecture Patterns, Cap. 5:
'Integration tests exercise the adapter against the real dependency,
isolated with tmp_path.'
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import fitz
import pytest

from pdfscribe.adapters.pdf_text_reader import PdfTextReader

if TYPE_CHECKING:
    from pathlib import Path


def _make_pdf(path: Path, pages: int, *, blank_last: bool = False) -> None:
    """Build a minimal multi-page PDF at path for testing."""
    doc = fitz.open()
    for n in range(pages):
        page = doc.new_page()
        is_blank = blank_last and n == pages - 1
        if not is_blank:
            page.insert_text((72, 72), f"Pagina {n + 1} do documento")
    doc.save(str(path))
    doc.close()


class TestPdfTextReader:
    """Integration tests for the native text adapter."""

    def test_page_count_matches(self, tmp_path: Path) -> None:
        pdf = tmp_path / "sample.pdf"
        _make_pdf(pdf, pages=4)
        assert PdfTextReader().page_count(pdf) == 4

    def test_no_page_is_lost(self, tmp_path: Path) -> None:
        # Fidelity contract, rule 5, against the real engine.
        pdf = tmp_path / "sample.pdf"
        _make_pdf(pdf, pages=6)
        reader = PdfTextReader()
        assert len(list(reader.pages(pdf))) == reader.page_count(pdf)

    def test_pages_are_numbered_from_one(self, tmp_path: Path) -> None:
        pdf = tmp_path / "sample.pdf"
        _make_pdf(pdf, pages=3)
        numbers = [page.number for page in PdfTextReader().pages(pdf)]
        assert numbers == [1, 2, 3]

    def test_text_of_each_page_is_returned(self, tmp_path: Path) -> None:
        pdf = tmp_path / "sample.pdf"
        _make_pdf(pdf, pages=3)
        pages = list(PdfTextReader().pages(pdf))
        for index, page in enumerate(pages):
            assert f"Pagina {index + 1} do documento" in page.text

    def test_blank_page_yields_empty_text_not_a_gap(self, tmp_path: Path) -> None:
        # A page with no text layer is still a page.
        pdf = tmp_path / "sample.pdf"
        _make_pdf(pdf, pages=3, blank_last=True)
        pages = list(PdfTextReader().pages(pdf))
        assert len(pages) == 3
        assert pages[2].text.strip() == ""

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            PdfTextReader().page_count(tmp_path / "nope.pdf")

    def test_missing_file_raises_on_pages(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            list(PdfTextReader().pages(tmp_path / "nope.pdf"))

    def test_corrupt_file_raises_runtime_error(self, tmp_path: Path) -> None:
        broken = tmp_path / "broken.pdf"
        broken.write_bytes(b"not a pdf at all")
        with pytest.raises(RuntimeError, match="Cannot open PDF"):
            PdfTextReader().page_count(broken)
