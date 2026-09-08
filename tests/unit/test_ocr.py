"""Tests - OCR value objects (domain layer, pure logic).

Piramide de testes: Percival & Gregory, Cap. 5.
'Lots of unit tests, few integration tests.'
"""

from __future__ import annotations

import pytest

from pdfscribe.domain.ocr import OcrOutcome, RenderSettings, mean_confidence


class TestRenderSettings:
    """Tests for the rendering value object."""

    def test_defaults(self) -> None:
        settings = RenderSettings()
        assert settings.dpi == 300
        assert settings.lang == "por"

    def test_is_frozen(self) -> None:
        with pytest.raises(AttributeError):
            RenderSettings().dpi = 150

    def test_rejects_dpi_below_range(self) -> None:
        with pytest.raises(ValueError, match="dpi must be within"):
            RenderSettings(dpi=10)

    def test_rejects_dpi_above_range(self) -> None:
        with pytest.raises(ValueError, match="dpi must be within"):
            RenderSettings(dpi=5000)

    def test_rejects_blank_lang(self) -> None:
        with pytest.raises(ValueError, match="lang must not be empty"):
            RenderSettings(lang="  ")

    def test_from_env_uses_defaults_when_unset(self) -> None:
        assert RenderSettings.from_env({}) == RenderSettings()

    def test_from_env_overrides_dpi_and_lang(self) -> None:
        settings = RenderSettings.from_env({"PDFSCRIBE_DPI": "150", "PDFSCRIBE_LANG": "por+eng"})
        assert settings.dpi == 150
        assert settings.lang == "por+eng"

    def test_from_env_rejects_non_integer_dpi(self) -> None:
        with pytest.raises(ValueError, match="must be an integer"):
            RenderSettings.from_env({"PDFSCRIBE_DPI": "alto"})


class TestOcrOutcome:
    """Tests for the OCR result value object."""

    def test_accepts_a_plain_reading(self) -> None:
        outcome = OcrOutcome(text="corpo", confidence=0.9, words=1)
        assert outcome.text == "corpo"

    def test_accepts_an_empty_reading(self) -> None:
        assert OcrOutcome(text="", confidence=0.0, words=0).words == 0

    def test_rejects_confidence_above_one(self) -> None:
        with pytest.raises(ValueError, match="within"):
            OcrOutcome(text="x", confidence=1.5, words=1)

    def test_rejects_negative_words(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            OcrOutcome(text="x", confidence=0.5, words=-1)


class TestMeanConfidence:
    """Tests for the confidence average."""

    def test_empty_scores_zero(self) -> None:
        assert mean_confidence([]) == 0.0

    def test_rescales_to_zero_one(self) -> None:
        assert mean_confidence([100.0, 0.0]) == 0.5

    def test_drops_negative_rows(self) -> None:
        # tesseract marks a row that holds no word with -1; counting it
        # as a badly read word would understate a good page.
        assert mean_confidence([-1.0, 90.0, -1.0]) == 0.9

    def test_all_negative_scores_zero(self) -> None:
        assert mean_confidence([-1.0, -1.0]) == 0.0

    def test_stays_within_bounds(self) -> None:
        assert mean_confidence([120.0]) == 1.0
