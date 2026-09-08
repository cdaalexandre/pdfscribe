"""Entrypoint CLI - user-facing interface.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 4.e.
'The entrypoint is the thinnest possible layer.'

The tesseract binary is checked here rather than deep in the adapter,
because a missing dependency should stop the run in the first second
with a message a human can act on, not after reading 30,000 pages.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pdfscribe import __version__
from pdfscribe.adapters.tesseract_ocr import MISSING_BINARY, tesseract_path
from pdfscribe.domain.ocr import RenderSettings
from pdfscribe.log import get_logger, setup_logging
from pdfscribe.service_layer.transcriber import transcribe

logger = get_logger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="pdfscribe",
        description="Faithful page-by-page PDF transcription with provenance.",
    )
    parser.add_argument("--version", action="version", version=f"pdfscribe {__version__}")
    parser.add_argument("--input", type=Path, required=True, help="Path to the PDF to transcribe.")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output .md path (default: <stem>_transcript/<stem>.md).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=None,
        help="Rendering resolution for the OCR path (default: 300).",
    )
    parser.add_argument(
        "--lang",
        default=None,
        help="tesseract language code, such as por or por+eng (default: por).",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Skip recognition. Pages needing it are still marked.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify and report without writing. Skips OCR.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed log output.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress informational output.")
    return parser


def _default_output(input_path: Path) -> Path:
    """Return the default transcript path for an input document."""
    stem = input_path.stem
    return input_path.parent / f"{stem}_transcript" / f"{stem}.md"


def _settings(args: argparse.Namespace) -> RenderSettings:
    """Build render settings from the environment, then the flags.

    Raises:
        ValueError: If a value is out of range or badly formed.
    """
    base = RenderSettings.from_env()
    return RenderSettings(
        dpi=args.dpi if args.dpi is not None else base.dpi,
        lang=args.lang if args.lang is not None else base.lang,
    )


def main() -> None:
    """CLI entrypoint."""
    args = _build_parser().parse_args()
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    input_path: Path = args.input.resolve()
    if not input_path.exists():
        logger.error("File not found: %s", input_path)
        sys.exit(1)

    try:
        settings = _settings(args)
    except ValueError as exc:
        logger.error("Invalid settings: %s", exc)
        sys.exit(1)

    recognizing = not args.no_ocr and not args.dry_run
    if recognizing and tesseract_path() is None:
        logger.error("%s", MISSING_BINARY)
        logger.error("Run again with --no-ocr to transcribe the native text only.")
        sys.exit(1)

    output_path: Path = args.out.resolve() if args.out is not None else _default_output(input_path)

    try:
        result = transcribe(
            input_path,
            output_path,
            dry_run=args.dry_run,
            use_ocr=not args.no_ocr,
            settings=settings,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        logger.error("Transcription failed: %s", exc)
        sys.exit(1)

    logger.info(
        "Pages: %d total, %d native, %d ocr, %d mixed, %d empty",
        result.page_count,
        result.native_pages,
        result.ocr_pages,
        result.mixed_pages,
        result.empty_pages,
    )
    if result.flagged_pages:
        logger.info(
            "Low confidence on %d page(s); look for the warning marker",
            result.flagged_pages,
        )
    if not result.ocr_ran and (result.ocr_pages or result.mixed_pages):
        logger.info("OCR did not run: %d page(s) carry no recognized text", result.ocr_pages)

    logger.info("Transcript size: %d bytes", result.output_bytes)
    if result.written:
        logger.info("Wrote %s", result.output_path)
    else:
        logger.info("Dry run: nothing written. Target would be %s", result.output_path)
