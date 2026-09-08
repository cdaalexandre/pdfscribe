"""Decide where a transcript is cut into parts.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 1.c.i.
'Value Objects - defined by their attributes, immutable.'

Herdado do docslice: o teto e medido em BYTES, nunca em paginas. A
densidade de texto varia demais - uma pagina de tabela e uma pagina de
prosa nao ocupam o mesmo espaco - e byte e o que o consumidor a jusante
precisa ler.

Diferente do docslice em duas coisas, e as duas por medicao:

- O docslice recebe o texto inteiro ja montado e devolve deslocamentos.
  Aqui o texto inteiro e justamente o que nao pode existir: a 30.000
  paginas ele nao cabe na memoria. Este modulo trabalha por acumulacao,
  recebendo o tamanho de um bloco por vez, o que deixa o chamador
  escrever cada parte assim que ela fecha.

- O docslice corta em fronteira de paragrafo. Aqui a fronteira e a
  pagina: um pedaco de pagina separado do seu marcador seria conteudo
  sem origem declarada, e a proveniencia por pagina e o contrato deste
  projeto. Uma pagina maior que o teto ocupa uma parte inteira sozinha,
  nunca e partida.

Logica pura. Nao conhece APIs, nao faz I/O.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

_ENV_MAX_BYTES = "PDFSCRIBE_MAX_BYTES"

DEFAULT_MAX_BYTES = 3 * 1024 * 1024
MIN_MAX_BYTES = 1024


@dataclass(frozen=True)
class SplitSettings:
    """How large a single part of a transcript may get.

    Attributes:
        max_bytes: Target ceiling for one part, in UTF-8 bytes. A page
            larger than this is not split; it gets a part to itself and
            the part goes over.
    """

    max_bytes: int = DEFAULT_MAX_BYTES

    def __post_init__(self) -> None:
        """Reject a ceiling too small to hold a page.

        Raises:
            ValueError: If max_bytes is below MIN_MAX_BYTES.
        """
        if self.max_bytes < MIN_MAX_BYTES:
            msg = f"max_bytes must be at least {MIN_MAX_BYTES}, got {self.max_bytes}"
            raise ValueError(msg)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> SplitSettings:
        """Build settings from the environment, falling back to the default.

        Args:
            env: Mapping to read overrides from. Defaults to os.environ.

        Returns:
            Settings with PDFSCRIBE_MAX_BYTES applied when present.

        Raises:
            ValueError: If the variable is set to something that is not
                an integer, or the result is out of range.
        """
        source: Mapping[str, str] = os.environ if env is None else env
        raw = source.get(_ENV_MAX_BYTES)
        if raw is None:
            return cls()
        try:
            return cls(max_bytes=int(raw))
        except ValueError as exc:
            if "invalid literal" not in str(exc):
                raise
            msg = f"{_ENV_MAX_BYTES} must be an integer, got {raw!r}"
            raise ValueError(msg) from exc


def starts_new_part(current_bytes: int, block_bytes: int, max_bytes: int) -> bool:
    """Report whether the current part must be closed before this block.

    An empty part never starts a new one, however large the block is:
    that is how an oversized page ends up alone in its own part instead
    of being cut in half.

    Args:
        current_bytes: Size of what the open part already holds.
        block_bytes: Size of the block about to be added.
        max_bytes: Ceiling for one part.

    Returns:
        True when the block would push the open part past the ceiling.
    """
    if current_bytes <= 0:
        return False
    return current_bytes + block_bytes > max_bytes


def plan_parts(sizes: Iterable[int], max_bytes: int) -> list[int]:
    """Group block sizes into parts, without holding any block.

    Used by tests and by anyone who wants to know the shape of the
    output before producing it. The transcriber applies the same rule
    one block at a time, so the two always agree.

    Args:
        sizes: Size in bytes of each block, in order.
        max_bytes: Ceiling for one part.

    Returns:
        How many blocks each part holds. An empty input yields an empty
        list: no blocks means no parts.
    """
    parts: list[int] = []
    held = 0
    count = 0
    for size in sizes:
        if starts_new_part(held, size, max_bytes):
            parts.append(count)
            held = 0
            count = 0
        held += size
        count += 1
    if count:
        parts.append(count)
    return parts


def part_filename(stem: str, suffix: str, index: int, *, multi: bool) -> str:
    """Name one part of a transcript.

    A transcript that fits in one part keeps the plain name: numbering a
    single file would only make it harder to find.

    Args:
        stem: File name without extension.
        suffix: Extension, dot included.
        index: 1-based part number.
        multi: Whether the transcript has more than one part.

    Returns:
        The file name for this part.
    """
    if not multi:
        return f"{stem}{suffix}"
    return f"{stem}_part{index:02d}{suffix}"
