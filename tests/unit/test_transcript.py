"""Tests - transcript assembly (domain layer, pure logic).

Piramide de testes: Percival & Gregory, Cap. 5.
'Lots of unit tests, few integration tests.'

The literalidade tests are the fidelity contract expressed as code: if a
future change starts de-hyphenating, joining lines or collapsing spaces,
these fail first.
"""

from __future__ import annotations

import pytest

from pdfscribe.domain.fidelity import PageMark, PageSource
from pdfscribe.domain.transcript import (
    RawPage,
    has_characters,
    mark_native_page,
    render_page,
)


class TestRawPage:
    """Tests for the raw page value object."""

    def test_accepts_first_page(self) -> None:
        assert RawPage(number=1, text="a").number == 1

    def test_rejects_zero_page_number(self) -> None:
        with pytest.raises(ValueError, match="1-based"):
            RawPage(number=0, text="a")

    def test_accepts_empty_text(self) -> None:
        assert RawPage(number=1, text="").text == ""


class TestHasCharacters:
    """Tests for the emptiness rule."""

    def test_text_has_characters(self) -> None:
        assert has_characters("Art. 155") is True

    def test_empty_string_has_none(self) -> None:
        assert has_characters("") is False

    def test_whitespace_only_has_none(self) -> None:
        assert has_characters("  \n\t\n ") is False


class TestMarkNativePage:
    """Tests for the PR1 marking rule."""

    def test_page_with_text_is_native(self) -> None:
        mark = mark_native_page(RawPage(number=1, text="Despacho"))
        assert mark.source is PageSource.NATIVE
        assert mark.confidence == 1.0

    def test_page_without_text_is_empty(self) -> None:
        mark = mark_native_page(RawPage(number=2, text=""))
        assert mark.source is PageSource.EMPTY
        assert mark.confidence == 0.0

    def test_page_number_is_carried_over(self) -> None:
        assert mark_native_page(RawPage(number=77, text="x")).number == 77

    def test_sheet_is_read_from_the_page(self) -> None:
        mark = mark_native_page(RawPage(number=1, text="fls. 412\nDespacho"))
        assert mark.sheet == "412"

    def test_missing_sheet_stays_none(self) -> None:
        assert mark_native_page(RawPage(number=1, text="Despacho")).sheet is None


class TestRenderPage:
    """Tests for the rendered page block."""

    def test_marker_is_the_first_line(self) -> None:
        raw = RawPage(number=3, text="corpo")
        rendered = render_page(raw, mark_native_page(raw))
        assert rendered.split("\n")[0] == "<!-- p.3 | fonte: nativo | conf: 1.00 | folha: ? -->"

    def test_text_follows_the_marker(self) -> None:
        raw = RawPage(number=1, text="corpo da pagina")
        rendered = render_page(raw, mark_native_page(raw))
        assert rendered.endswith("corpo da pagina\n")

    def test_empty_page_renders_marker_only(self) -> None:
        raw = RawPage(number=9, text="")
        rendered = render_page(raw, mark_native_page(raw))
        assert rendered == "<!-- p.9 | fonte: vazia | conf: 0.00 | folha: ? -->\n"

    def test_closing_newline_is_added_once(self) -> None:
        raw = RawPage(number=1, text="linha")
        assert render_page(raw, mark_native_page(raw)).endswith("linha\n")

    def test_existing_closing_newline_is_not_doubled(self) -> None:
        raw = RawPage(number=1, text="linha\n")
        assert render_page(raw, mark_native_page(raw)).endswith("linha\n")

    def test_accepts_a_marker_built_elsewhere(self) -> None:
        raw = RawPage(number=4, text="corpo")
        mark = PageMark(number=4, source=PageSource.OCR, confidence=0.5)
        assert "fonte: ocr" in render_page(raw, mark)


class TestRenderPageIsLiteral:
    """Regression tests - the fidelity contract, rule 1.

    Every text here is something a well-meaning cleanup pass would
    'fix'. The transcript must carry all of it through untouched.
    """

    def test_preserves_hyphenation_across_lines(self) -> None:
        raw = RawPage(number=1, text="Recur-\nso especial")
        assert "Recur-\nso especial" in render_page(raw, mark_native_page(raw))

    def test_preserves_repeated_internal_spaces(self) -> None:
        raw = RawPage(number=1, text="Total     R$ 1.500,00")
        assert "Total     R$ 1.500,00" in render_page(raw, mark_native_page(raw))

    def test_preserves_the_folio_stamp_in_the_body(self) -> None:
        # The stamp is recorded in the marker AND left on the page.
        raw = RawPage(number=1, text="fls. 412\nDespacho")
        rendered = render_page(raw, mark_native_page(raw))
        assert "folha: 412" in rendered
        assert "fls. 412\nDespacho" in rendered

    def test_preserves_a_bare_page_number(self) -> None:
        # docslice deletes isolated page numbers; a scribe does not.
        raw = RawPage(number=1, text="corpo\n\n42\n\nmais corpo")
        assert "\n\n42\n\n" in render_page(raw, mark_native_page(raw))

    def test_preserves_blank_line_runs(self) -> None:
        raw = RawPage(number=1, text="a\n\n\n\n\nb")
        assert "a\n\n\n\n\nb" in render_page(raw, mark_native_page(raw))

    def test_preserves_mojibake(self) -> None:
        # A font with no ToUnicode map yields this. PR2 sends the page
        # to OCR; it never rewrites the characters.
        raw = RawPage(number=1, text="\ufffd\ufffd\ufffd corpo \ufffd")
        assert "\ufffd\ufffd\ufffd corpo \ufffd" in render_page(raw, mark_native_page(raw))

    def test_preserves_tabs_and_trailing_spaces(self) -> None:
        raw = RawPage(number=1, text="col1\tcol2   \nlinha   ")
        assert "col1\tcol2   \nlinha   " in render_page(raw, mark_native_page(raw))
