"""Service layer - orchestrates reading, marking and writing a transcript.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 4.e.
'Introducing a Service Layer - define a clear boundary for our use cases.'

Percival & Gregory, Cap. 13.
'Declaring an explicit dependency is an example of the dependency
inversion principle.'

The reader and the writer arrive as parameters, so the whole use case is
testable with Fakes and no page ever has to exist on disk.

Known limit (PR3): the transcript is assembled in memory before it is
written. At the 30,000-page scale this project targets that is a lot of
string, and the splitter PR is where the write becomes incremental.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pdfscribe.adapters.file_io import write_transcript
from pdfscribe.adapters.pdf_text_reader import PdfTextReader
from pdfscribe.domain.fidelity import PageSource
from pdfscribe.domain.transcript import mark_native_page, render_page
from pdfscribe.log import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from pdfscribe.adapters.protocols import TextExtractor, TranscriptWriter

logger = get_logger(__name__)


@dataclass(frozen=True)
class TranscribeResult:
    """Outcome of one transcription run.

    Attributes:
        input_path: The document that was read.
        output_path: Where the transcript was written, or would be.
        page_count: Pages the document reported.
        native_pages: Pages transcribed from the text layer.
        empty_pages: Pages that carried no text at all.
        output_bytes: Size of the assembled transcript in UTF-8 bytes.
        written: False when the run was a dry run.
    """

    input_path: Path
    output_path: Path
    page_count: int
    native_pages: int
    empty_pages: int
    output_bytes: int
    written: bool


def transcribe(
    input_path: Path,
    output_path: Path,
    *,
    dry_run: bool = False,
    extractor: TextExtractor | None = None,
    writer: TranscriptWriter | None = None,
) -> TranscribeResult:
    """Transcribe every page of a document, marker included, and write it.

    Args:
        input_path: Document to transcribe.
        output_path: Destination .md file.
        dry_run: When True, assemble and measure but write nothing.
        extractor: Optional injected reader (for testing with Fakes).
        writer: Optional injected writer (for testing with Fakes).

    Returns:
        A TranscribeResult describing what was produced.

    Raises:
        RuntimeError: If the number of transcribed pages does not match
            the count the document reported. Losing a page silently is
            the one failure this pipeline must never ship.
    """
    reader = extractor if extractor is not None else PdfTextReader()
    write = writer if writer is not None else write_transcript

    expected = reader.page_count(input_path)
    blocks: list[str] = []
    native = 0
    empty = 0

    for raw in reader.pages(input_path):
        mark = mark_native_page(raw)
        if mark.source is PageSource.EMPTY:
            empty += 1
        else:
            native += 1
        blocks.append(render_page(raw, mark))

    seen = len(blocks)
    if seen != expected:
        msg = f"page loss: transcribed {seen} of {expected} pages in {input_path}"
        raise RuntimeError(msg)

    text = "".join(blocks)
    output_bytes = len(text.encode("utf-8"))

    if dry_run:
        logger.info("Dry run: %d pages, %d bytes, nothing written", seen, output_bytes)
    else:
        write(text, output_path)

    logger.info("Transcription complete: %d native, %d empty, %d pages", native, empty, seen)

    return TranscribeResult(
        input_path=input_path,
        output_path=output_path,
        page_count=expected,
        native_pages=native,
        empty_pages=empty,
        output_bytes=output_bytes,
        written=not dry_run,
    )
