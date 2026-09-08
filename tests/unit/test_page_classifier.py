"""Tests - page classification (domain layer, pure logic)."""

from __future__ import annotations

from pdfscribe.domain.fidelity import FidelityThresholds, PageSource
from pdfscribe.domain.page_classifier import classify_page, garbage_ratio


class TestGarbageRatio:
    """Tests for the broken-text-layer measure."""

    def test_clean_portuguese_scores_zero(self) -> None:
        assert garbage_ratio("Trata-se de acao de inventario, fls. 4.") == 0.0

    def test_empty_scores_zero(self) -> None:
        assert garbage_ratio("   \n  ") == 0.0

    def test_replacement_characters_score_high(self) -> None:
        assert garbage_ratio("\ufffd\ufffd\ufffd\ufffd") == 1.0

    def test_ignores_whitespace_in_the_denominator(self) -> None:
        assert garbage_ratio("ab\n\n\ncd") == 0.0

    def test_mixed_text_scores_in_between(self) -> None:
        assert 0.0 < garbage_ratio("abcd\ufffd\ufffd\ufffd\ufffd") < 1.0


class TestClassifyPage:
    """Tests for the classification cascade."""

    def test_no_own_text_goes_to_ocr(self) -> None:
        # The measured case: the page carries only the document frame.
        assert classify_page("") is PageSource.OCR

    def test_whitespace_only_goes_to_ocr(self) -> None:
        assert classify_page("   \n\t\n ") is PageSource.OCR

    def test_broken_text_layer_goes_to_ocr(self) -> None:
        assert classify_page("\ufffd\ufffd\ufffd\ufffd\ufffd") is PageSource.OCR

    def test_clean_text_without_ink_is_native(self) -> None:
        assert classify_page("Trata-se de inventario", ink_ratio=0.0) is PageSource.NATIVE

    def test_light_ink_stays_native(self) -> None:
        # Table rules and underlines cover a few percent of a text page.
        assert classify_page("Trata-se de inventario", ink_ratio=0.12) is PageSource.NATIVE

    def test_text_plus_heavy_ink_is_mixed(self) -> None:
        assert classify_page("Trata-se de inventario", ink_ratio=0.65) is PageSource.MIXED

    def test_empty_is_never_returned(self) -> None:
        # Only OCR coming back empty settles that a page is blank.
        assert classify_page("", ink_ratio=0.0) is not PageSource.EMPTY

    def test_custom_ink_threshold_is_honoured(self) -> None:
        limits = FidelityThresholds(mixed_ink_ratio=0.05)
        assert classify_page("corpo", ink_ratio=0.12, thresholds=limits) is PageSource.MIXED

    def test_custom_garbage_threshold_is_honoured(self) -> None:
        limits = FidelityThresholds(max_garbage_ratio=0.90)
        assert classify_page("abcd\ufffd\ufffd\ufffd\ufffd", thresholds=limits) is PageSource.NATIVE
