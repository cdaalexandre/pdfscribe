"""Provenance markers and fidelity thresholds for page transcription.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 1.c.i.
'Value Objects - defined by their attributes, immutable, interchangeable.'

Ramalho, Fluent Python, Cap. 5.
'Data Class Builders - frozen instances are safe to share.'

Every page of a transcription carries a marker written by this module.
The marker is the only place where the reader learns whether a page was
read from the PDF text layer or reconstructed by OCR, and how much the
engine trusted its own output.

Logica pura. Nao conhece APIs, nao faz I/O.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

LOW_CONFIDENCE_MARK = "\u26a0\ufe0f"
SHEET_UNKNOWN = "?"

_ENV_MIN_OCR_CONFIDENCE = "PDFSCRIBE_MIN_OCR_CONFIDENCE"
_ENV_MAX_GARBAGE_RATIO = "PDFSCRIBE_MAX_GARBAGE_RATIO"
_ENV_MIN_WORD_RATIO = "PDFSCRIBE_MIN_WORD_RATIO"

# Brazilian court files stamp a sheet number on every page: 'fls. 1234',
# 'fl. 12', 'Folha 7'. The page number in the PDF and the sheet number in
# the case file diverge whenever a volume is split or a document is
# appended, so both are recorded and neither is inferred from the other.
#
# The stamp owns its line. Anything sharing a line with other text is a
# cross-reference to a different page - '(fls. 407-410)', 'de fls.
# 540/541, sendo' - and recording it as this page's sheet would be an
# invented fact. Anchoring the pattern to the whole line is what
# separates the two; see find_sheet_number for the measurement.
_STAMP_LINE_RE = re.compile(
    r"^f(?:ls?|olhas?)\b\.?\s*(?:n?[.\u00ba\u00b0]?\s*)?(\d{1,6})$",
    re.IGNORECASE,
)


class PageSource(StrEnum):
    """Where the text of a transcribed page came from."""

    NATIVE = "nativo"
    OCR = "ocr"
    EMPTY = "vazia"


@dataclass(frozen=True)
class FidelityThresholds:
    """Tunable limits for page classification and confidence warnings.

    Attributes:
        min_ocr_confidence: Below this, an OCR page is flagged in its
            marker as unreliable.
        max_garbage_ratio: Above this share of characters outside the
            expected alphabet, a native text layer is treated as broken
            (a font with no ToUnicode map yields chars that are not text).
        min_word_ratio: Below this share of word-shaped tokens, a native
            text layer is treated as broken.
    """

    min_ocr_confidence: float = 0.80
    max_garbage_ratio: float = 0.30
    min_word_ratio: float = 0.50

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> FidelityThresholds:
        """Build thresholds from environment variables, falling back to defaults.

        Args:
            env: Mapping to read overrides from. Defaults to os.environ.

        Returns:
            Thresholds with every PDFSCRIBE_* override applied.

        Raises:
            ValueError: If a variable is set to something that is not a float.
        """
        source: Mapping[str, str] = os.environ if env is None else env
        return cls(
            min_ocr_confidence=_read_float(source, _ENV_MIN_OCR_CONFIDENCE, cls.min_ocr_confidence),
            max_garbage_ratio=_read_float(source, _ENV_MAX_GARBAGE_RATIO, cls.max_garbage_ratio),
            min_word_ratio=_read_float(source, _ENV_MIN_WORD_RATIO, cls.min_word_ratio),
        )


@dataclass(frozen=True)
class PageMark:
    """Provenance record of one transcribed page.

    Attributes:
        number: 1-based page index in the source PDF.
        source: Which path produced the text.
        confidence: 0.0 to 1.0. Native pages are 1.0 by construction,
            empty pages are 0.0, OCR pages carry the engine's own score.
        sheet: Sheet number stamped on the page, or None when the page
            carries none. Never inferred from a neighbouring page.
    """

    number: int
    source: PageSource
    confidence: float
    sheet: str | None = None

    def __post_init__(self) -> None:
        """Reject a marker that could not describe a real page.

        Raises:
            ValueError: If number is below 1 or confidence is outside 0.0-1.0.
        """
        if self.number < 1:
            msg = f"page number is 1-based, got {self.number}"
            raise ValueError(msg)
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"confidence must be within [0.0, 1.0], got {self.confidence}"
            raise ValueError(msg)


def _read_float(env: Mapping[str, str], key: str, default: float) -> float:
    """Read one float from the environment mapping, or return the default."""
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        msg = f"{key} must be a float, got {raw!r}"
        raise ValueError(msg) from exc


def find_sheet_number(text: str) -> str | None:
    """Find the sheet number stamped on a page of a court file.

    A stamp occupies a line of its own. A mention inside a sentence
    points at some other page and is never this page's sheet.

    Measured against a real TJSP filing of 81 pages: taking the first
    match anywhere on the page got 51 right, because references appear
    before the stamp in reading order. Requiring a whole line, and
    keeping the last such line, is what separates stamp from reference.

    When no line holds a stamp alone the answer is None. For a
    transcription an honest '?' beats an invented number.

    Args:
        text: Full text of a single page, as transcribed.

    Returns:
        The digits of the sheet number exactly as stamped, zero padding
        included, or None when the page shows no stamp.
    """
    found: str | None = None
    for line in text.splitlines():
        match = _STAMP_LINE_RE.match(line.strip())
        if match is not None:
            # str() wrap: Match.group is typed str | Any in typeshed; the
            # cast narrows it without a `# type: ignore` under
            # warn_return_any.
            found = str(match.group(1))
    return found


def is_low_confidence(mark: PageMark, thresholds: FidelityThresholds | None = None) -> bool:
    """Report whether an OCR page fell below the confidence threshold.

    Only OCR pages can be low confidence. A native page is 1.0 by
    construction and an empty page is 0.0 with nothing to trust or
    distrust, so neither is ever flagged.

    Args:
        mark: The page marker under test.
        thresholds: Limits to apply. Defaults to FidelityThresholds().

    Returns:
        True when the page came from OCR and scored below the threshold.
    """
    limits = thresholds if thresholds is not None else FidelityThresholds()
    return mark.source is PageSource.OCR and mark.confidence < limits.min_ocr_confidence


def format_marker(mark: PageMark, thresholds: FidelityThresholds | None = None) -> str:
    """Render the provenance marker that precedes a page in the output.

    The marker is an HTML comment, so it survives Markdown rendering
    without appearing in the reading flow, and it is greppable by the
    indexing step downstream.

    Args:
        mark: The page marker to render.
        thresholds: Limits used to decide the low-confidence flag.

    Returns:
        A single line such as
        '<!-- p.12 | fonte: ocr | conf: 0.74 | folha: 345 | WARN -->',
        where WARN is the warning sign only on low-confidence OCR pages.
    """
    sheet = mark.sheet if mark.sheet is not None else SHEET_UNKNOWN
    body = (
        f"p.{mark.number} | fonte: {mark.source.value} "
        f"| conf: {mark.confidence:.2f} | folha: {sheet}"
    )
    if is_low_confidence(mark, thresholds):
        body = f"{body} | {LOW_CONFIDENCE_MARK}"
    return f"<!-- {body} -->"
