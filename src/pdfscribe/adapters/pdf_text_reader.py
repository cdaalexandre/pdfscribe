"""Adapter - read a PDF page by page via PyMuPDF, text untouched.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 2.g.
'What Is a Port and What Is an Adapter, in Python?'

Deliberately smaller than the docslice PDF adapter. docslice asks
pymupdf4llm for a structured Markdown rendering of the whole document;
this adapter asks pymupdf for the raw text of one page and returns it
unchanged. Structure is interpretation, and interpretation is what the
fidelity contract forbids by default.

The text layer is returned exactly as MuPDF reports it, including
hyphenation, repeated headers, folio stamps and mojibake. Deciding that
a text layer is broken is the classifier's job (PR2), not the reader's.

Isolated I/O: swapping PyMuPDF for another engine changes only this file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pymupdf

from pdfscribe.domain.transcript import RawPage
from pdfscribe.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

logger = get_logger(__name__)

_PROGRESS_EVERY = 500


def _open_document(path: Path) -> Any:
    """Open a PDF with pymupdf, or fail with a clear message.

    Args:
        path: Path to the PDF file.

    Returns:
        The open pymupdf document. pymupdf ships no type stubs, so the return
        type is Any by necessity and is narrowed at every use site.

    Raises:
        FileNotFoundError: If path does not exist.
        RuntimeError: If pymupdf cannot open the file.
    """
    if not path.exists():
        msg = f"PDF file not found: {path}"
        raise FileNotFoundError(msg)
    try:
        return pymupdf.open(str(path))
    except Exception as exc:
        msg = f"Cannot open PDF: {path}"
        raise RuntimeError(msg) from exc


class PdfTextReader:
    """Read the native text layer of a PDF, one page at a time."""

    def page_count(self, path: Path) -> int:
        """Return how many pages the PDF holds.

        Args:
            path: Path to the PDF file.

        Returns:
            The page count reported by MuPDF.

        Raises:
            FileNotFoundError: If path does not exist.
            RuntimeError: If pymupdf cannot open the file.
        """
        doc = _open_document(path)
        try:
            return int(doc.page_count)
        finally:
            doc.close()

    def pages(self, path: Path) -> Iterator[RawPage]:
        """Yield the native text of every page, verbatim and in order.

        Args:
            path: Path to the PDF file.

        Yields:
            One RawPage per page, numbered from 1, carrying the text
            exactly as extracted. Pages with no text layer yield an
            empty string rather than being skipped.

        Raises:
            FileNotFoundError: If path does not exist.
            RuntimeError: If pymupdf cannot open the file.
        """
        doc = _open_document(path)
        try:
            total = int(doc.page_count)
            logger.info("Reading native text: %d pages in %s", total, path.name)
            for index, page in enumerate(doc):
                yield RawPage(number=index + 1, text=str(page.get_text("text")))
                if (index + 1) % _PROGRESS_EVERY == 0:
                    logger.info("Read %d / %d pages", index + 1, total)
        finally:
            doc.close()
