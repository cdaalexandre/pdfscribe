"""Tests - frame detection (domain layer, pure logic).

The fixtures below are shortened from a real court filing: an eSAJ
conference footer whose access code changes per page, a signature line
whose timestamp changes, and a folio stamp whose number changes.
"""

from __future__ import annotations

import pytest

from pdfscribe.domain.frame import (
    PageFrame,
    build_frame,
    line_signature,
)

FOOTER = "Para conferir o original, acesse o site https://esaj.tjsp.jus.br/pastadigital/sg/abrir"
SIGNED = "Este documento e copia do original, assinado digitalmente, protocolado em 15/01/2026"


# Bodies must differ by WORDS, not only by number: signatures collapse
# runs of digits, so 'Item 1' and 'Item 2' share one signature and a
# numbered list repeated across pages would look like frame.
_SUBJECTS = (
    "inventario",
    "agravo de instrumento",
    "peticao intercorrente",
    "manifestacao ministerial",
    "certidao de objeto",
    "mandado de intimacao",
    "acordao da camara",
)


def _page(number: int, body: str = "") -> str:
    """Build a page with the usual frame plus an optional body."""
    lines = [f"{FOOTER}, informe o processo 1000052-93.2026 e codigo abc{number}XY."]
    lines.append(f"{SIGNED} as 21:0{number % 10}.")
    if body:
        lines.append(body)
    lines.append(f"fls. {number}")
    return "\n".join(lines)


def _body(number: int) -> str:
    """Build a page body whose wording, not only its number, varies."""
    return f"Trata-se de {_SUBJECTS[number % len(_SUBJECTS)]} nos autos, parte {number}"


class TestLineSignature:
    """Tests for the per-line signature."""

    def test_collapses_digit_runs(self) -> None:
        assert line_signature("fls. 4") == line_signature("fls. 1234")

    def test_collapses_whitespace(self) -> None:
        assert line_signature("fls.   4") == line_signature("fls. 4")

    def test_keeps_only_the_prefix(self) -> None:
        base = "Para conferir o original, acesse o site https://esaj.tjsp.jus.br/x"
        assert line_signature(base + " codigo AAA") == line_signature(base + " codigo ZZZ")

    def test_different_content_keeps_different_signatures(self) -> None:
        assert line_signature("Trata-se de inventario") != line_signature("Trata-se de agravo")


class TestBuildFrame:
    """Tests for frame discovery across a document."""

    def test_finds_the_repeated_lines(self) -> None:
        frame = build_frame(_page(n, _body(n)) for n in range(1, 21))
        assert frame.is_frame("fls. 7")
        assert frame.is_frame(f"{SIGNED} as 21:01.")

    def test_leaves_content_out_of_the_frame(self) -> None:
        frame = build_frame(_page(n, _body(n)) for n in range(1, 21))
        assert not frame.is_frame(_body(3))

    def test_known_limit_numbered_lines_look_like_frame(self) -> None:
        # Documented failure mode, not an accident: signatures collapse
        # digit runs, so a list repeated across pages collapses too.
        # It costs at most a page sent to OCR that was native, because
        # without_frame() only measures - the transcript keeps every line.
        frame = build_frame(_page(n, f"Item {n} do rol de bens") for n in range(1, 21))
        assert frame.is_frame("Item 4 do rol de bens")

    def test_single_page_document_has_no_frame(self) -> None:
        # With one page nothing repeats, and calling its footer
        # boilerplate would delete the whole page.
        frame = build_frame([_page(1, "Corpo")])
        assert frame.signatures == frozenset()

    def test_empty_document_has_no_frame(self) -> None:
        assert build_frame([]).signatures == frozenset()

    def test_rejects_ratio_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="repeat_ratio"):
            build_frame(["a", "b"], repeat_ratio=1.5)

    def test_a_line_on_few_pages_is_not_frame(self) -> None:
        pages = [
            _page(n, "Cabecalho de secao") if n <= 3 else _page(n, _body(n)) for n in range(1, 21)
        ]
        frame = build_frame(pages)
        assert not frame.is_frame("Cabecalho de secao")


class TestPageFrameWithoutFrame:
    """Tests for removing the frame from a page."""

    def test_scanned_page_has_no_own_text(self) -> None:
        # The measured case: page carries the footer and nothing else.
        pages = [_page(n, _body(n)) for n in range(1, 20)]
        pages.append(_page(20))
        frame = build_frame(pages)
        assert frame.own_characters(pages[19]) == 0

    def test_native_page_keeps_its_own_text(self) -> None:
        pages = [_page(n, _body(n)) for n in range(1, 21)]
        frame = build_frame(pages)
        assert _body(1) in frame.without_frame(pages[0])

    def test_strip_drops_the_folio_stamp(self) -> None:
        pages = [_page(n, _body(n)) for n in range(1, 21)]
        frame = build_frame(pages)
        assert "fls." not in frame.without_frame(pages[4])

    def test_empty_frame_keeps_everything(self) -> None:
        frame = PageFrame(frozenset())
        kept = frame.without_frame("uma linha\noutra linha")
        assert kept == "uma linha\noutra linha"
