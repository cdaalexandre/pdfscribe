"""Assemble one page of a transcript: provenance marker plus verbatim text.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 1.c.i.
'Value Objects - defined by their attributes, immutable.'

The scribe analogy lives here. This module copies what the page shows and
puts the marker in the margin; it never edits the copy. No de-hyphenation,
no line joining, no header removal, no whitespace collapsing.

When a page is read twice - its own text layer and then OCR over the
image - both readings are kept. The native text of a scanned page is
usually just the court's footer, but it is text that is on the page, and
dropping it would be an edit.

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

NATIVE_CONFIDENCE = 1.0
EMPTY_CONFIDENCE = 0.0


@dataclass(frozen=True)
class RawPage:
    """One page as read from the source document, untouched.

    Attributes:
        number: 1-based page index in the source document.
        text: The page text exactly as the extractor returned it,
            including hyphenation, repeated headers and folio stamps.
        ink_ratio: Share of the page covered by marks the text layer
            does not explain - drawings and images that do not span the
            whole page. A full-page watermark is excluded on purpose:
            measured on a real filing it was present on every single
            page and separated nothing.
    """

    number: int
    text: str
    ink_ratio: float = 0.0

    def __post_init__(self) -> None:
        """Reject a page that could not exist in a document.

        Raises:
            ValueError: If number is below 1 or ink_ratio is outside
                0.0 to 1.0.
        """
        if self.number < 1:
            msg = f"page number is 1-based, got {self.number}"
            raise ValueError(msg)
        if not 0.0 <= self.ink_ratio <= 1.0:
            msg = f"ink_ratio must be within [0.0, 1.0], got {self.ink_ratio}"
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


def build_mark(raw: RawPage, source: PageSource, confidence: float) -> PageMark:
    """Build the provenance marker for a page read a given way.

    The folio stamp is always read from the native text layer, never
    from OCR: on a scanned page the court's footer is the one part that
    is still real text, and it is more reliable than a recognized guess.

    Args:
        raw: The page as extracted.
        source: Where the page's content came from.
        confidence: How much that reading can be trusted.

    Returns:
        The marker describing the page.
    """
    return PageMark(
        number=raw.number,
        source=source,
        confidence=confidence,
        sheet=find_sheet_number(raw.text),
    )


def mark_native_page(raw: RawPage) -> PageMark:
    """Build the marker for a page read from the text layer alone.

    A native page is confidence 1.0 by construction: the characters were
    stored in the file, not guessed from an image.

    Args:
        raw: The page as extracted.

    Returns:
        A marker describing where the page text came from.
    """
    if has_characters(raw.text):
        return build_mark(raw, PageSource.NATIVE, NATIVE_CONFIDENCE)
    return build_mark(raw, PageSource.EMPTY, EMPTY_CONFIDENCE)


def render_page(
    raw: RawPage,
    mark: PageMark,
    ocr_text: str | None = None,
    thresholds: FidelityThresholds | None = None,
) -> str:
    """Render one page block: the marker, the page text, and any OCR.

    The only byte this function adds to a text is a closing LF when it
    does not already end with one. That LF belongs to the container, not
    to the page: without it the next marker would share a line with this
    page's last word. Nothing else is added, removed or reordered.

    Args:
        raw: The page as extracted.
        mark: The marker describing the page.
        ocr_text: What OCR read from the page image, when it ran. An
            empty string is still rendered, as evidence that OCR ran and
            found nothing.
        thresholds: Limits used to decide the low-confidence flag.

    Returns:
        The marker line, the native text, and - when OCR ran - a nested
        marker followed by the recognized text.
    """
    parts = [f"{format_marker(mark, thresholds)}\n"]
    if raw.text:
        parts.append(raw.text if raw.text.endswith("\n") else f"{raw.text}\n")
    if ocr_text is not None:
        parts.append(f"<!-- p.{mark.number} | ocr -->\n")
        if ocr_text:
            parts.append(ocr_text if ocr_text.endswith("\n") else f"{ocr_text}\n")
    return "".join(parts)
