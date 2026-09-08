"""Adapter protocols - explicit interfaces for the adapter layer.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 2.
'The Repository in the Abstract - define the interface before the
implementation.'

Ramalho, Fluent Python, Cap. 13.
'Protocol provides structural subtyping - a.k.a. static duck typing.'

TextExtractor is a two-method port rather than the plain callable its
docslice counterpart uses. The page loop and the page count come from
the same document and have to agree: comparing them is how the
no-page-is-lost invariant of the fidelity contract is enforced, so both
belong to the same port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from pdfscribe.domain.transcript import RawPage


class TextExtractor(Protocol):
    """Interface for reading a document page by page, text untouched."""

    def page_count(self, path: Path) -> int:
        """Return how many pages the document at path holds."""
        ...

    def pages(self, path: Path) -> Iterator[RawPage]:
        """Yield one RawPage per page, in document order, starting at 1."""
        ...


class TranscriptWriter(Protocol):
    """Interface for writing a finished transcript to disk."""

    def __call__(self, text: str, path: Path) -> Path:
        """Write text to path as UTF-8, with no line-ending translation."""
        ...
