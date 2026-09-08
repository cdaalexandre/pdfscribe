"""Adapter - read a rasterized page with tesseract, through pytesseract.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 2.g.
'What Is a Port and What Is an Adapter, in Python?'

pytesseract is a bridge to the tesseract binary, not an engine: the
binary and its language data are installed outside pip, which is why the
entrypoint checks for them and fails early with a message a human can
act on.

image_to_data is used rather than image_to_string because it returns one
confidence per word. Without it the marker could not honestly report how
much the engine trusted the page, and the fidelity contract requires
exactly that.

Reading order is the engine's own: words are regrouped by its block,
paragraph and line numbering. Measured against a real court filing, that
keeps prose and forms clean, but reads a table column by column - a
movement table arrives with its dates in one run and its entry types in
another, rather than paired line by line. The alternative, rebuilding
lines from vertical position, pairs the table correctly but scatters the
footer the court prints sideways down the margin through the whole page,
breaking the prose. Reordered but intact loses less than paired but
polluted, so the engine's order stays. Nothing is dropped either way.

Isolated I/O: this file is the only place that knows tesseract exists.
"""

from __future__ import annotations

import io
import shutil

import pytesseract
from PIL import Image

from pdfscribe.domain.ocr import OcrOutcome, mean_confidence
from pdfscribe.log import get_logger

logger = get_logger(__name__)

MISSING_BINARY = (
    "tesseract was not found on PATH. Install it with the language data "
    "you need (Windows: the UB-Mannheim build) and reopen the terminal."
)


def tesseract_path() -> str | None:
    """Return the tesseract binary path, or None when it is not installed."""
    return shutil.which("tesseract")


class TesseractOcr:
    """Recognize text on a rendered page, with per-word confidence."""

    def read(self, image: bytes, lang: str) -> OcrOutcome:
        """Recognize the text of one rendered page.

        Line structure is rebuilt from the engine's own block, paragraph
        and line numbering, so the output keeps the shape of the page
        instead of collapsing into one paragraph.

        Args:
            image: The rendered page, as PNG bytes.
            lang: tesseract language code, such as 'por'.

        Returns:
            The recognized text with its mean confidence.

        Raises:
            RuntimeError: If the tesseract binary is not installed.
        """
        if tesseract_path() is None:
            raise RuntimeError(MISSING_BINARY)

        with Image.open(io.BytesIO(image)) as page:
            data = pytesseract.image_to_data(page, lang=lang, output_type=pytesseract.Output.DICT)

        words = [str(word) for word in data.get("text", [])]
        confidences = [float(value) for value in data.get("conf", [])]
        blocks = [int(value) for value in data.get("block_num", [])]
        paragraphs = [int(value) for value in data.get("par_num", [])]
        lines = [int(value) for value in data.get("line_num", [])]

        grouped: dict[tuple[int, int, int], list[str]] = {}
        kept: list[float] = []
        for index, word in enumerate(words):
            if not word.strip():
                continue
            confidence = confidences[index] if index < len(confidences) else -1.0
            if confidence < 0:
                continue
            key = (blocks[index], paragraphs[index], lines[index])
            grouped.setdefault(key, []).append(word)
            kept.append(confidence)

        text = "\n".join(" ".join(group) for _, group in sorted(grouped.items()))
        outcome = OcrOutcome(text=text, confidence=mean_confidence(kept), words=len(kept))
        logger.debug("OCR: %d words, confidence %.2f", outcome.words, outcome.confidence)
        return outcome
