"""Service layer - orchestrates reading, classifying and writing.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 4.e.
'Introducing a Service Layer - define a clear boundary for our use cases.'

Percival & Gregory, Cap. 13.
'Declaring an explicit dependency is an example of the dependency
inversion principle.'

Every collaborator arrives as a parameter, so the whole use case runs
against Fakes with no PDF, no tesseract and no disk.

Two passes, and the first one is what makes the second honest. Until
every page has been read, there is no way to know which lines are the
document's frame, and without that a scanned page carrying only a footer
looks exactly like a transcribed page.

Parts are written as they close, never held together. What stays in
memory is one part at a time, plus the native text of every page, which
the frame pass needs. Dropping that last ceiling means a second read of
the document, and it is the next thing to do if 30,000 pages prove it
necessary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pdfscribe.adapters.file_io import write_transcript
from pdfscribe.adapters.pdf_rasterizer import PdfRasterizer
from pdfscribe.adapters.pdf_text_reader import PdfTextReader
from pdfscribe.adapters.tesseract_ocr import TesseractOcr
from pdfscribe.domain.fidelity import PageSource, is_low_confidence
from pdfscribe.domain.frame import build_frame
from pdfscribe.domain.ocr import RenderSettings
from pdfscribe.domain.page_classifier import classify_page
from pdfscribe.domain.run_log import PageRecord, format_log, record_of
from pdfscribe.domain.splitter import SplitSettings, part_filename, starts_new_part
from pdfscribe.domain.transcript import (
    EMPTY_CONFIDENCE,
    NATIVE_CONFIDENCE,
    RawPage,
    build_mark,
    has_characters,
    render_page,
)
from pdfscribe.log import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from pdfscribe.adapters.protocols import (
        OcrEngine,
        PageRasterizer,
        TextExtractor,
        TranscriptWriter,
    )
    from pdfscribe.domain.fidelity import FidelityThresholds

logger = get_logger(__name__)

_PROGRESS_EVERY = 50
LOG_SUFFIX = ".log"


@dataclass(frozen=True)
class TranscribeResult:
    """Outcome of one transcription run.

    Attributes:
        input_path: The document that was read.
        output_path: Destination given by the caller. With more than one
            part, the files written are named after it.
        log_path: Where the run log was written, or would be.
        page_count: Pages the document reported.
        native_pages: Pages whose content came from the text layer.
        ocr_pages: Pages whose content was recognized from the image.
        mixed_pages: Pages read both ways.
        empty_pages: Pages that carried nothing at all.
        flagged_pages: Pages whose recognition fell below the threshold.
            Always zero when OCR did not run: a page nobody read has no
            confidence to be low.
        output_bytes: Size of the whole transcript in UTF-8 bytes.
        parts: How many files the transcript was cut into.
        part_names: Name of each part, in order.
        ocr_ran: False when OCR was skipped, which makes output_bytes a
            lower bound rather than the final size.
        written: False when the run was a dry run.
    """

    input_path: Path
    output_path: Path
    log_path: Path
    page_count: int
    native_pages: int
    ocr_pages: int
    mixed_pages: int
    empty_pages: int
    flagged_pages: int
    output_bytes: int
    parts: int
    part_names: tuple[str, ...] = field(default=())
    ocr_ran: bool = True
    written: bool = True


def transcribe(
    input_path: Path,
    output_path: Path,
    *,
    dry_run: bool = False,
    use_ocr: bool = True,
    settings: RenderSettings | None = None,
    split: SplitSettings | None = None,
    thresholds: FidelityThresholds | None = None,
    extractor: TextExtractor | None = None,
    writer: TranscriptWriter | None = None,
    rasterizer: PageRasterizer | None = None,
    ocr: OcrEngine | None = None,
) -> TranscribeResult:
    """Transcribe every page of a document and write it, split if needed.

    Args:
        input_path: Document to transcribe.
        output_path: Destination .md file. When the transcript needs
            more than one part, the parts are named after it and this
            exact file is not written.
        dry_run: When True, classify and measure but write nothing. OCR
            is skipped, because recognizing thousands of pages to then
            discard the result would defeat the purpose of a dry run.
        use_ocr: When False, pages that need OCR are still marked as
            needing it, but no recognition is attempted.
        settings: Rendering resolution and language.
        split: Ceiling for one part of the transcript.
        thresholds: Limits for classification and the confidence flag.
        extractor: Injected reader, for testing with Fakes.
        writer: Injected writer, for testing with Fakes.
        rasterizer: Injected renderer, for testing with Fakes.
        ocr: Injected recognition engine, for testing with Fakes.

    Returns:
        A TranscribeResult describing what was produced.

    Raises:
        RuntimeError: If the number of transcribed pages does not match
            the count the document reported. Losing a page silently is
            the one failure this pipeline must never ship.
    """
    reader = extractor if extractor is not None else PdfTextReader()
    write = writer if writer is not None else write_transcript
    render = settings if settings is not None else RenderSettings()
    limits = split if split is not None else SplitSettings()

    expected = reader.page_count(input_path)
    pages: list[RawPage] = list(reader.pages(input_path))
    if len(pages) != expected:
        msg = f"page loss: read {len(pages)} of {expected} pages in {input_path}"
        raise RuntimeError(msg)

    recognizing = use_ocr and not dry_run
    engine = (ocr if ocr is not None else TesseractOcr()) if recognizing else None
    screen = (rasterizer if rasterizer is not None else PdfRasterizer()) if recognizing else None

    frame = build_frame(page.text for page in pages)
    logger.info("Frame: %d repeated line(s) across %d pages", len(frame.signatures), expected)

    counted: dict[PageSource, int] = dict.fromkeys(PageSource, 0)
    records: list[PageRecord] = []
    flagged = 0
    total_bytes = 0

    held: list[str] = []
    held_bytes = 0
    part = 1
    multi = False
    names: list[str] = []

    for raw in pages:
        own_text = frame.without_frame(raw.text)
        source = classify_page(own_text, raw.ink_ratio, thresholds)
        ocr_text: str | None = None
        confidence = NATIVE_CONFIDENCE

        if source in (PageSource.OCR, PageSource.MIXED):
            if engine is not None and screen is not None:
                image = screen.render(input_path, raw.number, render.dpi)
                outcome = engine.read(image, render.lang)
                ocr_text = outcome.text
                confidence = outcome.confidence
                if not has_characters(outcome.text) and not has_characters(raw.text):
                    source = PageSource.EMPTY
                    confidence = EMPTY_CONFIDENCE
            else:
                confidence = EMPTY_CONFIDENCE

        mark = build_mark(raw, source, confidence)
        if recognizing and is_low_confidence(mark, thresholds):
            flagged += 1
        counted[source] += 1

        block = render_page(raw, mark, ocr_text, thresholds)
        size = len(block.encode("utf-8"))

        if starts_new_part(held_bytes, size, limits.max_bytes):
            multi = True
            name = part_filename(output_path.stem, output_path.suffix, part, multi=True)
            names.append(name)
            if not dry_run:
                write("".join(held), output_path.with_name(name))
            logger.info("Part %d closed: %s (%d bytes)", part, name, held_bytes)
            held = []
            held_bytes = 0
            part += 1

        held.append(block)
        held_bytes += size
        total_bytes += size
        records.append(record_of(mark, size, part, ""))

        if raw.number % _PROGRESS_EVERY == 0:
            logger.info("Transcribed %d / %d pages", raw.number, expected)

    last_name = part_filename(output_path.stem, output_path.suffix, part, multi=multi)
    names.append(last_name)
    if not dry_run:
        write("".join(held), output_path.with_name(last_name))

    named = [
        PageRecord(
            number=record.number,
            source=record.source,
            confidence=record.confidence,
            sheet=record.sheet,
            size_bytes=record.size_bytes,
            part=record.part,
            filename=names[record.part - 1],
        )
        for record in records
    ]

    log_path = output_path.with_suffix(LOG_SUFFIX)
    if not dry_run:
        write(format_log(named), log_path)

    if dry_run:
        logger.info("Dry run: %d pages, %d part(s), nothing written", expected, part)

    logger.info(
        "Done: %d native, %d ocr, %d mixed, %d empty, %d flagged",
        counted[PageSource.NATIVE],
        counted[PageSource.OCR],
        counted[PageSource.MIXED],
        counted[PageSource.EMPTY],
        flagged,
    )

    return TranscribeResult(
        input_path=input_path,
        output_path=output_path,
        log_path=log_path,
        page_count=expected,
        native_pages=counted[PageSource.NATIVE],
        ocr_pages=counted[PageSource.OCR],
        mixed_pages=counted[PageSource.MIXED],
        empty_pages=counted[PageSource.EMPTY],
        flagged_pages=flagged,
        output_bytes=total_bytes,
        parts=part,
        part_names=tuple(names),
        ocr_ran=recognizing,
        written=not dry_run,
    )
