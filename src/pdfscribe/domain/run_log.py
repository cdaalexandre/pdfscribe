"""Build the run log: one line per page, tab separated.

Fundamentacao: PLAYBOOK PDF->MCP, secao 'Estrutura de MAPA'.
'Manter sempre: nome do arquivo, unidade, tipo de corte, faixa de origem,
chave de lookup do dominio, bytes.'

This is not a diagnostic dump; it is the index the next step reads. A
transcript split into parts is useless to a downstream lookup unless
something says which page landed in which part, how it was read, and how
much that reading can be trusted. That is exactly this file.

Tab separated on purpose: the sheet number and the source are short
tokens, and a court transcript is full of commas.

Logica pura. Nao conhece APIs, nao faz I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pdfscribe.domain.fidelity import SHEET_UNKNOWN

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pdfscribe.domain.fidelity import PageMark

LOG_COLUMNS = ("page", "source", "confidence", "sheet", "bytes", "part", "file")
LOG_HEADER = "\t".join(LOG_COLUMNS)


@dataclass(frozen=True)
class PageRecord:
    """One line of the run log.

    Attributes:
        number: 1-based page number in the source document.
        source: How the page was read.
        confidence: How much that reading can be trusted, 0.0 to 1.0.
        sheet: Folio stamp found on the page, or None.
        size_bytes: Size of the rendered page block in UTF-8 bytes.
        part: 1-based part the page landed in.
        filename: Name of the file holding that part.
    """

    number: int
    source: str
    confidence: float
    sheet: str | None
    size_bytes: int
    part: int
    filename: str


def record_of(mark: PageMark, size_bytes: int, part: int, filename: str) -> PageRecord:
    """Build a log record from a page marker.

    Args:
        mark: The marker written on the page.
        size_bytes: Size of the rendered block.
        part: 1-based part number.
        filename: Name of the file holding that part.

    Returns:
        The record for this page.
    """
    return PageRecord(
        number=mark.number,
        source=mark.source.value,
        confidence=mark.confidence,
        sheet=mark.sheet,
        size_bytes=size_bytes,
        part=part,
        filename=filename,
    )


def format_log(records: Iterable[PageRecord]) -> str:
    """Render the run log, header included.

    Args:
        records: One record per page, in page order.

    Returns:
        The log as tab separated text, ending in a newline.
    """
    lines = [LOG_HEADER]
    for record in records:
        sheet = record.sheet if record.sheet is not None else SHEET_UNKNOWN
        lines.append(
            "\t".join(
                (
                    str(record.number),
                    record.source,
                    f"{record.confidence:.2f}",
                    sheet,
                    str(record.size_bytes),
                    str(record.part),
                    record.filename,
                )
            )
        )
    return "\n".join(lines) + "\n"
