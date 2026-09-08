"""Value objects for the OCR path: settings and outcome.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 1.c.i.
'Value Objects - defined by their attributes, immutable.'

Ramalho, Fluent Python, Cap. 5.
'Data Class Builders - frozen instances are safe to share.'

DPI is a value object rather than a literal because it is a real
trade-off, not a constant: too low and confidence collapses, too high
and a 30,000-page document stops being feasible.

Logica pura. Nao conhece APIs, nao faz I/O.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

_ENV_DPI = "PDFSCRIBE_DPI"
_ENV_LANG = "PDFSCRIBE_LANG"

MIN_DPI = 72
MAX_DPI = 1200


@dataclass(frozen=True)
class RenderSettings:
    """How a page is rendered and which language the engine reads.

    Attributes:
        dpi: Rendering resolution for the OCR path.
        lang: tesseract language code, such as 'por' or 'por+eng'.
    """

    dpi: int = 300
    lang: str = "por"

    def __post_init__(self) -> None:
        """Reject settings the renderer could not honour.

        Raises:
            ValueError: If dpi is outside 72..1200 or lang is blank.
        """
        if not MIN_DPI <= self.dpi <= MAX_DPI:
            msg = f"dpi must be within {MIN_DPI}..{MAX_DPI}, got {self.dpi}"
            raise ValueError(msg)
        if not self.lang.strip():
            msg = "lang must not be empty"
            raise ValueError(msg)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> RenderSettings:
        """Build settings from environment variables, falling back to defaults.

        Args:
            env: Mapping to read overrides from. Defaults to os.environ.

        Returns:
            Settings with any PDFSCRIBE_* override applied.

        Raises:
            ValueError: If PDFSCRIBE_DPI is set to something that is not
                an integer, or the resulting values are out of range.
        """
        source: Mapping[str, str] = os.environ if env is None else env
        raw = source.get(_ENV_DPI)
        if raw is None:
            dpi = cls.dpi
        else:
            try:
                dpi = int(raw)
            except ValueError as exc:
                msg = f"{_ENV_DPI} must be an integer, got {raw!r}"
                raise ValueError(msg) from exc
        return cls(dpi=dpi, lang=source.get(_ENV_LANG, cls.lang))


@dataclass(frozen=True)
class OcrOutcome:
    """What the engine read from one page, and how much it trusted itself.

    Attributes:
        text: The recognized text, with the page's line structure kept.
        confidence: Mean per-word confidence, 0.0 to 1.0.
        words: How many words carried a usable confidence.
    """

    text: str
    confidence: float
    words: int

    def __post_init__(self) -> None:
        """Reject an outcome that could not describe a real reading.

        Raises:
            ValueError: If confidence is outside 0.0..1.0 or words is
                negative.
        """
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"confidence must be within [0.0, 1.0], got {self.confidence}"
            raise ValueError(msg)
        if self.words < 0:
            msg = f"words must not be negative, got {self.words}"
            raise ValueError(msg)


def mean_confidence(values: Iterable[float]) -> float:
    """Average the per-word confidences the engine reported.

    tesseract scores each word from 0 to 100 and uses a negative value
    for rows that hold no word at all. Those rows are dropped rather
    than counted as zero: a page break is not a badly read word.

    Args:
        values: Per-word confidences as the engine reports them, 0..100.

    Returns:
        The mean, rescaled to 0.0..1.0. An empty page scores 0.0.
    """
    usable = [value for value in values if value >= 0]
    if not usable:
        return 0.0
    return min(1.0, max(0.0, sum(usable) / len(usable) / 100))
