"""Tests - fidelity markers and thresholds (domain layer, pure logic).

Piramide de testes: Percival & Gregory, Cap. 5.
'Lots of unit tests, few integration tests.'
"""

from __future__ import annotations

import pytest

from pdfscribe.domain.fidelity import (
    LOW_CONFIDENCE_MARK,
    FidelityThresholds,
    PageMark,
    PageSource,
    find_sheet_number,
    format_marker,
    is_low_confidence,
)


class TestFidelityThresholds:
    """Tests for the thresholds value object."""

    def test_defaults(self) -> None:
        limits = FidelityThresholds()
        assert limits.min_ocr_confidence == 0.80
        assert limits.max_garbage_ratio == 0.30
        assert limits.min_word_ratio == 0.50

    def test_is_frozen(self) -> None:
        limits = FidelityThresholds()
        with pytest.raises(AttributeError):
            limits.min_ocr_confidence = 0.5

    def test_from_env_uses_defaults_when_unset(self) -> None:
        limits = FidelityThresholds.from_env({})
        assert limits == FidelityThresholds()

    def test_from_env_overrides_single_value(self) -> None:
        limits = FidelityThresholds.from_env({"PDFSCRIBE_MIN_OCR_CONFIDENCE": "0.5"})
        assert limits.min_ocr_confidence == 0.5
        assert limits.max_garbage_ratio == 0.30

    def test_from_env_rejects_non_float(self) -> None:
        with pytest.raises(ValueError, match="must be a float"):
            FidelityThresholds.from_env({"PDFSCRIBE_MAX_GARBAGE_RATIO": "muito"})


class TestPageMark:
    """Tests for the page marker value object."""

    def test_accepts_first_page(self) -> None:
        mark = PageMark(number=1, source=PageSource.NATIVE, confidence=1.0)
        assert mark.number == 1

    def test_rejects_zero_page_number(self) -> None:
        with pytest.raises(ValueError, match="1-based"):
            PageMark(number=0, source=PageSource.NATIVE, confidence=1.0)

    def test_rejects_confidence_above_one(self) -> None:
        with pytest.raises(ValueError, match="within"):
            PageMark(number=1, source=PageSource.OCR, confidence=1.5)

    def test_rejects_negative_confidence(self) -> None:
        with pytest.raises(ValueError, match="within"):
            PageMark(number=1, source=PageSource.OCR, confidence=-0.1)


class TestFindSheetNumber:
    """Tests for the folio stamp rule.

    Calibrated against a real TJSP filing: the stamp owns its line and
    sits at the foot of the page, while every mention inside a sentence
    points at some other page. The reference cases below are shortened
    from that document.
    """

    def test_finds_a_stamp_alone_on_its_line(self) -> None:
        assert find_sheet_number("Despacho do juizo\n\nfls. 4") == "4"

    def test_finds_abbreviated_singular(self) -> None:
        assert find_sheet_number("fl. 12") == "12"

    def test_finds_full_word(self) -> None:
        assert find_sheet_number("folha 7") == "7"

    def test_is_case_insensitive(self) -> None:
        assert find_sheet_number("FLS. 88") == "88"

    def test_tolerates_surrounding_whitespace(self) -> None:
        assert find_sheet_number("corpo\n   fls. 9   \n") == "9"

    def test_keeps_zero_padding_verbatim(self) -> None:
        assert find_sheet_number("corpo\nfls. 05") == "05"

    def test_ignores_a_reference_inside_a_sentence(self) -> None:
        assert find_sheet_number("de fls. 540/541, sendo nomeado inventariante.") is None

    def test_ignores_a_reference_in_parentheses(self) -> None:
        assert find_sheet_number("juntado aos autos (fls. 400-412), que concluiu") is None

    def test_ignores_a_page_range_alone_on_a_line(self) -> None:
        assert find_sheet_number("fls. 407-410") is None

    def test_reference_loses_to_the_stamp(self) -> None:
        page = "as fls. 17 dos autos do inventario\ncorpo\nfls. 4"
        assert find_sheet_number(page) == "4"

    def test_last_stamp_wins(self) -> None:
        assert find_sheet_number("fls. 3\ncorpo\nfls. 4") == "4"

    def test_returns_none_without_stamp(self) -> None:
        assert find_sheet_number("Pagina de texto corrido, sem carimbo.") is None

    def test_ignores_bare_numbers(self) -> None:
        assert find_sheet_number("O valor de 1500 reais") is None


class TestIsLowConfidence:
    """Tests for the low-confidence rule."""

    def test_ocr_below_threshold_is_low(self) -> None:
        mark = PageMark(number=3, source=PageSource.OCR, confidence=0.74)
        assert is_low_confidence(mark) is True

    def test_ocr_at_threshold_is_not_low(self) -> None:
        mark = PageMark(number=3, source=PageSource.OCR, confidence=0.80)
        assert is_low_confidence(mark) is False

    def test_native_is_never_low(self) -> None:
        mark = PageMark(number=3, source=PageSource.NATIVE, confidence=0.10)
        assert is_low_confidence(mark) is False

    def test_empty_is_never_low(self) -> None:
        mark = PageMark(number=3, source=PageSource.EMPTY, confidence=0.0)
        assert is_low_confidence(mark) is False

    def test_custom_threshold_is_honoured(self) -> None:
        mark = PageMark(number=3, source=PageSource.OCR, confidence=0.74)
        limits = FidelityThresholds(min_ocr_confidence=0.5)
        assert is_low_confidence(mark, limits) is False


class TestFormatMarker:
    """Tests for the rendered provenance marker."""

    def test_native_page_with_sheet(self) -> None:
        mark = PageMark(number=1, source=PageSource.NATIVE, confidence=1.0, sheet="12")
        assert format_marker(mark) == "<!-- p.1 | fonte: nativo | conf: 1.00 | folha: 12 -->"

    def test_missing_sheet_becomes_question_mark(self) -> None:
        mark = PageMark(number=2, source=PageSource.NATIVE, confidence=1.0)
        assert format_marker(mark) == "<!-- p.2 | fonte: nativo | conf: 1.00 | folha: ? -->"

    def test_low_confidence_ocr_is_flagged(self) -> None:
        mark = PageMark(number=9, source=PageSource.OCR, confidence=0.735, sheet="404")
        rendered = format_marker(mark)
        assert rendered == (
            f"<!-- p.9 | fonte: ocr | conf: 0.73 | folha: 404 | {LOW_CONFIDENCE_MARK} -->"
        )

    def test_high_confidence_ocr_is_not_flagged(self) -> None:
        mark = PageMark(number=9, source=PageSource.OCR, confidence=0.95, sheet="404")
        assert LOW_CONFIDENCE_MARK not in format_marker(mark)

    def test_empty_page_still_gets_a_marker(self) -> None:
        # Contract rule 4: an empty page is marked, never omitted.
        mark = PageMark(number=40, source=PageSource.EMPTY, confidence=0.0)
        assert format_marker(mark) == "<!-- p.40 | fonte: vazia | conf: 0.00 | folha: ? -->"

    def test_marker_is_a_single_line(self) -> None:
        mark = PageMark(number=5, source=PageSource.OCR, confidence=0.4, sheet="7")
        assert "\n" not in format_marker(mark)

    def test_marker_is_an_html_comment(self) -> None:
        mark = PageMark(number=5, source=PageSource.NATIVE, confidence=1.0)
        rendered = format_marker(mark)
        assert rendered.startswith("<!--")
        assert rendered.endswith("-->")
