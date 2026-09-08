"""Assemble one page of a transcript: provenance marker plus verbatim text.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 1.c.i.
'Value Objects - defined by their attributes, immutable.'

The scribe analogy lives here. This module copies what the page shows and
puts the marker in the margin; it never edits the copy. No de-hyphenation,
no line joining, no header removal, no whitespace collapsing - the exact
operations docslice performs in its own domain layer and that this project
defers to an opt-in flag in PR4.

Logica pura. Nao conhece APIs, nao faz I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from pdfscribe.domain.fidelity import (
    FidelityThresholds,
    PageMark,
    PageSource,
    find_sheet_number,
    format_marker,
)


@dataclass(frozen=True)
class RawPage:
    """One page as read from the source document, untouched.

    Attributes:
        number: 1-based page index in the source document.
        text: The page text exactly as the extractor returned it,
            including hyphenation, repeated headers and folio stamps.
    """

    number: int
    text: str

    def __post_init__(self) -> None:
        """Reject a page that could not exist in a document.

        Raises:
            ValueError: If number is below 1.
        """
        if self.number < 1:
            msg = f"page number is 1-based, got {self.number}"
            raise ValueError(msg)


def has_characters(text: str) -> bool:
    """Report whether a page carries anything worth transcribing.

    Whitespace-only counts as nothing: a page holding a single newline
    shows the reader as much as a page holding none.

    Args:
        text: The page text as extracted.

    Returns:
        True when the page has at least one non-whitespace character.
    """
    return bool(text.strip())


def mark_native_page(raw: RawPage) -> PageMark:
    """Build the provenance marker for a page read from the text layer.

    A native page is confidence 1.0 by construction: the characters were
    stored in the file, not guessed from an image.

    PR1 has no OCR path, so a page with an empty text layer is marked
    'vazia' here. From PR2 that page goes to OCR first and only stays
    'vazia' when OCR also comes back empty, as the fidelity contract
    requires. Either way the page is marked and never omitted.

    Args:
        raw: The page as extracted.

    Returns:
        A marker describing where the page text came from.
    """
    if has_characters(raw.text):
        source = PageSource.NATIVE
        confidence = 1.0
    else:
        source = PageSource.EMPTY
        confidence = 0.0
    return PageMark(
        number=raw.number,
        source=source,
        confidence=confidence,
        sheet=find_sheet_number(raw.text),
    )


def render_page(raw: RawPage, mark: PageMark, thresholds: FidelityThresholds | None = None) -> str:
    """Render one page block: the marker line, then the page text verbatim.

    The only byte this function adds to the page text is a closing LF when
    the text does not already end with one. That LF belongs to the
    container, not to the page: without it the next page's marker would
    share a line with this page's last word. Nothing else is added,
    removed or reordered.

    Args:
        raw: The page as extracted.
        mark: The marker describing the page.
        thresholds: Limits used to decide the low-confidence flag.

    Returns:
        The marker line followed by the page text. An empty page renders
        as its marker line alone.
    """
    marker = format_marker(mark, thresholds)
    if not raw.text:
        return f"{marker}\n"
    body = raw.text if raw.text.endswith("\n") else f"{raw.text}\n"
    return f"{marker}\n{body}"
