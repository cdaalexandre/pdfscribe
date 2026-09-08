"""Adapter - render one PDF page as a bitmap for OCR.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 2.g.
'What Is a Port and What Is an Adapter, in Python?'

Rendering, not extraction. The rasterizer draws the page as a reader
would see it, which is why it reaches content the text layer never
mentions - and, measured on a real court filing, why it is the right
tool even when there is no image on the page: 23 of its scanned pages
carry their content as thousands of vector primitives, with no image
XObject at all. get_pixmap draws both without knowing the difference.

Isolated I/O: this file is the only place that knows about pixel maps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pdfscribe.adapters.pdf_document import open_document
from pdfscribe.log import get_logger

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)


class PdfRasterizer:
    """Render pages of a PDF as PNG bytes."""

    def render(self, path: Path, number: int, dpi: int) -> bytes:
        """Render one page at the given resolution.

        Args:
            path: Path to the PDF file.
            number: 1-based page number.
            dpi: Rendering resolution. Low values cost OCR confidence,
                high values cost time; see RenderSettings for the default.

        Returns:
            The rendered page encoded as PNG.

        Raises:
            FileNotFoundError: If path does not exist.
            RuntimeError: If the file cannot be opened.
            ValueError: If number is outside the document.
        """
        doc = open_document(path)
        try:
            total = int(doc.page_count)
            if not 1 <= number <= total:
                msg = f"page {number} is outside the document (1..{total})"
                raise ValueError(msg)
            pixmap = doc[number - 1].get_pixmap(dpi=dpi)
            data = bytes(pixmap.tobytes("png"))
            logger.debug("Rendered p.%d at %d dpi: %d bytes", number, dpi, len(data))
            return data
        finally:
            doc.close()
