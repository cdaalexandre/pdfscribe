"""Adapter - write the transcript to disk, byte for byte.

Fundamentacao: Ramalho, Fluent Python, Cap. 4.
'Beware of Encoding Defaults - the worst bugs are the silent mojibake kind.'

write_bytes rather than write_text, for the reason docslice learned the
hard way and this project inherits as a rule: Path.write_text translates
line endings on Windows, and a transcription that silently gains a CR on
every line is no longer a faithful copy of the page.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pdfscribe.log import get_logger

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)


def write_transcript(text: str, path: Path) -> Path:
    """Write a transcript to path as UTF-8, with no translation at all.

    Args:
        text: The full transcript, markers included.
        path: Destination file. Parent directories are created.

    Returns:
        The path argument, for chainability.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    logger.info("Wrote %d bytes to %s", path.stat().st_size, path)
    return path
