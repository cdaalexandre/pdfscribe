"""Entrypoint CLI - user-facing interface.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 4.e.
'The entrypoint is the thinnest possible layer.'

PR1 wires native transcription. The OCR flags (--dpi, --lang) arrive in
PR2 and --normalize in PR4.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pdfscribe import __version__
from pdfscribe.log import get_logger, setup_logging
from pdfscribe.service_layer.transcriber import transcribe

logger = get_logger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="pdfscribe",
        description="Faithful page-by-page PDF transcription with provenance.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"pdfscribe {__version__}",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the PDF to transcribe.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output .md path (default: <stem>_transcript/<stem>.md).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report pages and bytes without writing anything.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed log output.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress informational messages.",
    )
    return parser


def _default_output(input_path: Path) -> Path:
    """Return the default transcript path for an input document."""
    stem = input_path.stem
    return input_path.parent / f"{stem}_transcript" / f"{stem}.md"


def main() -> None:
    """CLI entrypoint."""
    args = _build_parser().parse_args()
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    input_path: Path = args.input.resolve()
    if not input_path.exists():
        logger.error("File not found: %s", input_path)
        sys.exit(1)

    output_path: Path = args.out.resolve() if args.out is not None else _default_output(input_path)

    try:
        result = transcribe(input_path, output_path, dry_run=args.dry_run)
    except (FileNotFoundError, RuntimeError) as exc:
        logger.error("Transcription failed: %s", exc)
        sys.exit(1)

    logger.info(
        "Pages: %d total, %d native, %d empty",
        result.page_count,
        result.native_pages,
        result.empty_pages,
    )
    logger.info("Transcript size: %d bytes", result.output_bytes)
    if result.written:
        logger.info("Wrote %s", result.output_path)
    else:
        logger.info("Dry run: nothing written. Target would be %s", result.output_path)
