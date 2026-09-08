"""Adapter - read a PDF page by page via PyMuPDF, text untouched.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 2.g.
'What Is a Port and What Is an Adapter, in Python?'

Deliberately smaller than the docslice PDF adapter. docslice asks
pymupdf4llm for a structured Markdown rendering of the whole document;
this adapter asks for the raw text of one page and returns it unchanged.
Structure is interpretation, and interpretation is what the fidelity
contract forbids by default.

The text layer is returned exactly as MuPDF reports it, including
hyphenation, repeated headers, folio stamps and mojibake. Deciding that
a text layer is broken is the classifier's job, not the reader's.

Isolated I/O: swapping the PDF engine changes only this file and its
sibling pdf_document.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pdfscribe.adapters.pdf_document import open_document
from pdfscribe.domain.transcript import RawPage
from pdfscribe.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

logger = get_logger(__name__)

_PROGRESS_EVERY = 500


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
            RuntimeError: If the file cannot be opened.
        """
        doc = open_document(path)
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
            RuntimeError: If the file cannot be opened.
        """
        doc = open_document(path)
        try:
            total = int(doc.page_count)
            logger.info("Reading native text: %d pages in %s", total, path.name)
            for index, page in enumerate(doc):
                yield RawPage(number=index + 1, text=str(page.get_text("text")))
                if (index + 1) % _PROGRESS_EVERY == 0:
                    logger.info("Read %d / %d pages", index + 1, total)
        finally:
            doc.close()
