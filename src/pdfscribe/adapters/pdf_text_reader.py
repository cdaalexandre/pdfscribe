"""Adapter - read a PDF page by page via PyMuPDF, text untouched.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 2.g.
'What Is a Port and What Is an Adapter, in Python?'

Deliberately smaller than the docslice PDF adapter. docslice asks
pymupdf4llm for a structured Markdown rendering of the whole document;
this adapter asks for the raw text of one page and returns it unchanged.
Structure is interpretation, and interpretation is what the fidelity
contract forbids by default.

Besides the text, the reader measures how much of the page is covered by
marks the text layer does not explain. That measurement is done on a
grid rather than by summing rectangles, because overlapping shapes would
otherwise be counted many times over; and images spanning the whole page
are excluded, because the filing this was measured against carries a
signature watermark behind every single page.

Known cost: the ink measurement walks every drawing on the page, which
on a heavily scanned page means thousands of primitives. At the
30,000-page scale this is the slowest part of the native pass.

Isolated I/O: swapping the PDF engine changes only this file and its
sibling pdf_document.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pdfscribe.adapters.pdf_document import open_document
from pdfscribe.domain.transcript import RawPage
from pdfscribe.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

logger = get_logger(__name__)

_PROGRESS_EVERY = 500
_GRID_COLS = 48
_GRID_ROWS = 64
_FULL_PAGE_IMAGE = 0.90


def _cells(box: tuple[float, float, float, float], rect: Any) -> set[tuple[int, int]]:
    """Return the grid cells a rectangle touches, clipped to the page."""
    width = float(rect.width) or 1.0
    height = float(rect.height) or 1.0
    x0, y0, x1, y1 = box
    first_col = max(0, min(_GRID_COLS - 1, int((x0 - rect.x0) / width * _GRID_COLS)))
    last_col = max(0, min(_GRID_COLS - 1, int((x1 - rect.x0) / width * _GRID_COLS)))
    first_row = max(0, min(_GRID_ROWS - 1, int((y0 - rect.y0) / height * _GRID_ROWS)))
    last_row = max(0, min(_GRID_ROWS - 1, int((y1 - rect.y0) / height * _GRID_ROWS)))
    return {
        (col, row)
        for col in range(first_col, last_col + 1)
        for row in range(first_row, last_row + 1)
    }


def measure_ink(page: Any) -> float:
    """Measure the share of a page covered by non-text marks.

    Args:
        page: An open PyMuPDF page.

    Returns:
        A value from 0.0 to 1.0. Images covering almost the whole page
        are ignored: they are watermarks and letterheads, present on
        every page, and counting them would make every page look full.
    """
    rect = page.rect
    page_area = float(rect.width) * float(rect.height)
    if page_area <= 0:
        return 0.0

    covered: set[tuple[int, int]] = set()

    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 1:
            continue
        edges = block.get("bbox", (0.0, 0.0, 0.0, 0.0))
        box = (float(edges[0]), float(edges[1]), float(edges[2]), float(edges[3]))
        area = max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
        if area / page_area >= _FULL_PAGE_IMAGE:
            continue
        covered |= _cells(box, rect)

    for drawing in page.get_drawings():
        box = drawing.get("rect")
        if box is None:
            continue
        covered |= _cells((float(box.x0), float(box.y0), float(box.x1), float(box.y1)), rect)

    return len(covered) / (_GRID_COLS * _GRID_ROWS)


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
            exactly as extracted plus its ink measurement. Pages with no
            text layer yield an empty string rather than being skipped.

        Raises:
            FileNotFoundError: If path does not exist.
            RuntimeError: If the file cannot be opened.
        """
        doc = open_document(path)
        try:
            total = int(doc.page_count)
            logger.info("Reading native text: %d pages in %s", total, path.name)
            for index, page in enumerate(doc):
                yield RawPage(
                    number=index + 1,
                    text=str(page.get_text("text")),
                    ink_ratio=measure_ink(page),
                )
                if (index + 1) % _PROGRESS_EVERY == 0:
                    logger.info("Read %d / %d pages", index + 1, total)
        finally:
            doc.close()
