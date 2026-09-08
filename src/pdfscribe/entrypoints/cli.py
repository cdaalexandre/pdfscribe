"""Entrypoint CLI - user-facing interface.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 4.e.
'The entrypoint is the thinnest possible layer.'

PR0 wires only version reporting and logging. The transcription flags
(--input, --out, --dpi, --lang, --normalize, --dry-run) arrive in PR1.
"""

from __future__ import annotations

import argparse

from pdfscribe import __version__
from pdfscribe.log import get_logger, setup_logging

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


def main() -> None:
    """CLI entrypoint."""
    args = _build_parser().parse_args()
    setup_logging(verbose=args.verbose, quiet=args.quiet)
    logger.info("pdfscribe %s - bootstrap only, transcription lands in PR1.", __version__)
