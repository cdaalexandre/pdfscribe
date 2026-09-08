"""Domain - re-exports."""

from __future__ import annotations

from pdfscribe.domain.fidelity import (  # noqa: F401
    LOW_CONFIDENCE_MARK,
    SHEET_UNKNOWN,
    FidelityThresholds,
    PageMark,
    PageSource,
    find_sheet_number,
    format_marker,
    is_low_confidence,
)
from pdfscribe.domain.frame import (  # noqa: F401
    PageFrame,
    build_frame,
    line_signature,
)
from pdfscribe.domain.ocr import (  # noqa: F401
    OcrOutcome,
    RenderSettings,
    mean_confidence,
)
from pdfscribe.domain.page_classifier import (  # noqa: F401
    classify_page,
    garbage_ratio,
)
from pdfscribe.domain.transcript import (  # noqa: F401
    RawPage,
    has_characters,
    mark_native_page,
    render_page,
)

__all__ = [
    "LOW_CONFIDENCE_MARK",
    "SHEET_UNKNOWN",
    "FidelityThresholds",
    "OcrOutcome",
    "PageFrame",
    "PageMark",
    "PageSource",
    "RawPage",
    "RenderSettings",
    "build_frame",
    "classify_page",
    "find_sheet_number",
    "format_marker",
    "garbage_ratio",
    "has_characters",
    "is_low_confidence",
    "line_signature",
    "mark_native_page",
    "mean_confidence",
    "render_page",
]
