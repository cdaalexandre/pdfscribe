"""Adapter helper - open a PDF the same way everywhere.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 2.g.
'What Is a Port and What Is an Adapter, in Python?'

The text reader and the rasterizer need the same document, opened the
same way and failing the same way. Keeping that in one place stops the
two adapters from drifting apart on error handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pymupdf

if TYPE_CHECKING:
    from pathlib import Path


def open_document(path: Path) -> Any:
    """Open a PDF with PyMuPDF, or fail with a message naming the file.

    Args:
        path: Path to the PDF file.

    Returns:
        The open document. PyMuPDF ships no usable annotations, so the
        type is Any by necessity and is narrowed at every use site.

    Raises:
        FileNotFoundError: If path does not exist.
        RuntimeError: If PyMuPDF cannot open the file.
    """
    if not path.exists():
        msg = f"PDF file not found: {path}"
        raise FileNotFoundError(msg)
    try:
        return pymupdf.open(str(path))
    except Exception as exc:
        msg = f"Cannot open PDF: {path}"
        raise RuntimeError(msg) from exc
