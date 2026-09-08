"""Separate the frame of a document from the content of a page.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 1.c.i.
'Value Objects - defined by their attributes, immutable.'

Frame is what repeats on nearly every page: a court's conference footer,
a digital-signature band, a folio stamp. Content is what belongs to the
page alone. Telling them apart is what lets the classifier notice that a
page carrying only its footer has nothing transcribed at all.

Measured on a real filing of 81 pages: 31 of them carried the footer and
nothing else, and the native pipeline reported all 31 as fully
transcribed with confidence 1.00. Their content was on the page as
image and as vector, never as text.

Two details earned by that measurement:

- Signatures normalize runs of digits, because the folio stamp changes
  every page: 'fls. 4' and 'fls. 78' are the same frame line.
- Signatures keep only a prefix, because the footer carries a per-page
  access code that no digit rule would collapse.

Logica pura. Nao conhece APIs, nao faz I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

_DIGIT_RUN = re.compile(r"\d+")

SIGNATURE_PREFIX = 60
DEFAULT_REPEAT_RATIO = 0.60
MIN_FRAME_PAGES = 2


def line_signature(line: str) -> str:
    """Reduce a line to what stays the same across pages.

    Whitespace is collapsed, runs of digits become a single marker, and
    only the leading characters are kept.

    Args:
        line: One line of page text.

    Returns:
        The signature used to match this line against other pages.
    """
    collapsed = " ".join(line.split())
    return _DIGIT_RUN.sub("#", collapsed)[:SIGNATURE_PREFIX]


@dataclass(frozen=True)
class PageFrame:
    """The set of line signatures that repeat across a document.

    Attributes:
        signatures: Signatures of every line considered frame.
    """

    signatures: frozenset[str]

    def is_frame(self, line: str) -> bool:
        """Report whether a line belongs to the document's frame."""
        return line_signature(line) in self.signatures

    def without_frame(self, text: str) -> str:
        """Return the page text with its frame lines removed.

        The result is never written to the transcript: the transcript
        keeps the page whole, frame included. This is a measurement of
        how much the page says on its own, and the name says so - a
        method called strip on something that is not a string misleads
        both the reader and the linter.

        Args:
            text: Full text of one page.

        Returns:
            The remaining lines, joined by newline.
        """
        kept = [line for line in text.split("\n") if line.strip() and not self.is_frame(line)]
        return "\n".join(kept)

    def own_characters(self, text: str) -> int:
        """Count the non-space characters a page contributes by itself."""
        return len("".join(self.without_frame(text).split()))


def build_frame(
    pages: Iterable[str],
    *,
    repeat_ratio: float = DEFAULT_REPEAT_RATIO,
) -> PageFrame:
    """Discover the frame by looking at every page at once.

    A line is frame when its signature shows up on at least
    `repeat_ratio` of the pages. A document with a single page has no
    frame: nothing can be said to repeat, and calling its only footer
    boilerplate would silently delete content.

    Args:
        pages: Text of every page, in any order.
        repeat_ratio: Share of pages a line must appear on.

    Returns:
        The frame of the document, possibly empty.

    Raises:
        ValueError: If repeat_ratio is outside 0.0 to 1.0.
    """
    if not 0.0 <= repeat_ratio <= 1.0:
        msg = f"repeat_ratio must be within [0.0, 1.0], got {repeat_ratio}"
        raise ValueError(msg)

    texts = list(pages)
    if len(texts) < MIN_FRAME_PAGES:
        return PageFrame(frozenset())

    seen: dict[str, int] = {}
    for text in texts:
        for signature in {line_signature(line) for line in text.split("\n") if line.strip()}:
            seen[signature] = seen.get(signature, 0) + 1

    limit = max(MIN_FRAME_PAGES, int(len(texts) * repeat_ratio))
    return PageFrame(frozenset(sig for sig, count in seen.items() if count >= limit))
