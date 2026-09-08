"""Tests - transcriber service layer with Fakes.

Percival & Gregory, Architecture Patterns, Cap. 3.c.ii:
'Why Not Just Patch It Out? - every call to mock.patch is a ticking
time bomb.'
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pdfscribe.domain.ocr import OcrOutcome, RenderSettings
from pdfscribe.domain.transcript import RawPage
from pdfscribe.service_layer.transcriber import TranscribeResult, transcribe

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

FOOTER = "Para conferir o original, acesse o site https://esaj.tjsp.jus.br/pastadigital"
SUBJECTS = ("inventario", "agravo", "peticao", "certidao", "mandado", "acordao", "sentenca")


def _framed(number: int, body: str = "") -> str:
    """Build page text with the usual court frame around an optional body."""
    lines = [f"{FOOTER}, informe o processo 1000052-93.2026 e codigo abc{number}XY."]
    if body:
        lines.append(body)
    lines.append(f"fls. {number}")
    return "\n".join(lines)


def _body(number: int) -> str:
    """Build a body whose wording, not only its number, varies."""
    return f"Trata-se de {SUBJECTS[number % len(SUBJECTS)]} nos autos, parte {number}"


class FakeExtractor:
    """Test double that returns canned pages instead of reading a PDF."""

    def __init__(self, texts: list[str], declared: int | None = None, ink: float = 0.0) -> None:
        self.texts = texts
        self.declared = declared if declared is not None else len(texts)
        self.ink = ink
        self.count_calls: list[Path] = []
        self.page_calls: list[Path] = []

    def page_count(self, path: Path) -> int:
        self.count_calls.append(path)
        return self.declared

    def pages(self, path: Path) -> Iterator[RawPage]:
        self.page_calls.append(path)
        return iter(
            [
                RawPage(number=index + 1, text=text, ink_ratio=self.ink)
                for index, text in enumerate(self.texts)
            ]
        )


class FakeRasterizer:
    """Test double that records which pages were rendered."""

    def __init__(self) -> None:
        self.calls: list[tuple[Path, int, int]] = []

    def render(self, path: Path, number: int, dpi: int) -> bytes:
        self.calls.append((path, number, dpi))
        return b"PNG"


class FakeOcr:
    """Test double that returns a canned reading."""

    def __init__(self, text: str = "TEXTO RECONHECIDO", confidence: float = 0.9) -> None:
        self.text = text
        self.confidence = confidence
        self.calls: list[tuple[bytes, str]] = []

    def read(self, image: bytes, lang: str) -> OcrOutcome:
        self.calls.append((image, lang))
        return OcrOutcome(text=self.text, confidence=self.confidence, words=2)


class FakeWriter:
    """Test double that records what it was asked to write."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    def __call__(self, text: str, path: Path) -> Path:
        self.calls.append((text, path))
        return path


def _run(tmp_path: Path, texts: list[str], **kwargs: object) -> tuple[TranscribeResult, FakeWriter]:
    """Run transcribe with Fakes and return the result and the writer."""
    writer = FakeWriter()
    result = transcribe(
        tmp_path / "in.pdf",
        tmp_path / "out.md",
        extractor=FakeExtractor(texts, ink=float(kwargs.pop("ink", 0.0))),  # type: ignore[arg-type]
        writer=writer,
        rasterizer=FakeRasterizer(),
        ocr=FakeOcr(),
        **kwargs,  # type: ignore[arg-type]
    )
    return result, writer


class TestNoPageIsLost:
    """The one invariant the pipeline must never break."""

    def test_every_page_gets_a_marker(self, tmp_path: Path) -> None:
        texts = [_framed(n, _body(n)) for n in range(1, 11)]
        texts[4] = _framed(5)
        result, writer = _run(tmp_path, texts)
        written = writer.calls[0][0]
        assert result.page_count == 10
        assert written.count("<!-- p.") >= 10
        for number in range(1, 11):
            assert f"<!-- p.{number} |" in written

    def test_page_loss_raises(self, tmp_path: Path) -> None:
        writer = FakeWriter()
        with pytest.raises(RuntimeError, match="page loss"):
            transcribe(
                tmp_path / "in.pdf",
                tmp_path / "out.md",
                extractor=FakeExtractor(["a", "b"], declared=5),
                writer=writer,
                ocr=FakeOcr(),
                rasterizer=FakeRasterizer(),
            )


class TestClassification:
    """Tests for how pages are routed."""

    def test_pages_with_own_text_stay_native(self, tmp_path: Path) -> None:
        result, _ = _run(tmp_path, [_framed(n, _body(n)) for n in range(1, 11)])
        assert result.native_pages == 10
        assert result.ocr_pages == 0

    def test_frame_only_pages_go_to_ocr(self, tmp_path: Path) -> None:
        # The measured case: a scanned page carries only the footer.
        texts = [_framed(n, _body(n)) for n in range(1, 9)]
        texts += [_framed(9), _framed(10)]
        result, _ = _run(tmp_path, texts)
        assert result.ocr_pages == 2
        assert result.native_pages == 8

    def test_ocr_text_lands_in_the_transcript(self, tmp_path: Path) -> None:
        texts = [_framed(n, _body(n)) for n in range(1, 10)] + [_framed(10)]
        _, writer = _run(tmp_path, texts)
        written = writer.calls[0][0]
        assert "<!-- p.10 | ocr -->" in written
        assert "TEXTO RECONHECIDO" in written

    def test_native_text_of_an_ocr_page_is_kept(self, tmp_path: Path) -> None:
        # Nothing on the page is dropped, not even the frame.
        texts = [_framed(n, _body(n)) for n in range(1, 10)] + [_framed(10)]
        _, writer = _run(tmp_path, texts)
        assert "fls. 10" in writer.calls[0][0]

    def test_heavy_ink_with_text_is_mixed(self, tmp_path: Path) -> None:
        result, _ = _run(tmp_path, [_framed(n, _body(n)) for n in range(1, 11)], ink=0.7)
        assert result.mixed_pages == 10

    def test_empty_when_ocr_also_finds_nothing(self, tmp_path: Path) -> None:
        writer = FakeWriter()
        result = transcribe(
            tmp_path / "in.pdf",
            tmp_path / "out.md",
            extractor=FakeExtractor(["", "", ""]),
            writer=writer,
            rasterizer=FakeRasterizer(),
            ocr=FakeOcr(text="", confidence=0.0),
        )
        assert result.empty_pages == 3


class TestOcrControl:
    """Tests for when recognition runs and when it does not."""

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        result, writer = _run(tmp_path, [_framed(n, _body(n)) for n in range(1, 5)], dry_run=True)
        assert writer.calls == []
        assert result.written is False

    def test_dry_run_skips_recognition(self, tmp_path: Path) -> None:
        result, _ = _run(tmp_path, [_framed(n) for n in range(1, 5)], dry_run=True)
        assert result.ocr_ran is False

    def test_no_ocr_still_marks_the_pages(self, tmp_path: Path) -> None:
        texts = [_framed(n, _body(n)) for n in range(1, 10)] + [_framed(10)]
        result, writer = _run(tmp_path, texts, use_ocr=False)
        assert result.ocr_pages == 1
        assert result.ocr_ran is False
        assert "TEXTO RECONHECIDO" not in writer.calls[0][0]

    def test_rasterizer_receives_the_settings(self, tmp_path: Path) -> None:
        rasterizer = FakeRasterizer()
        texts = [_framed(n, _body(n)) for n in range(1, 10)] + [_framed(10)]
        transcribe(
            tmp_path / "in.pdf",
            tmp_path / "out.md",
            extractor=FakeExtractor(texts),
            writer=FakeWriter(),
            rasterizer=rasterizer,
            ocr=FakeOcr(),
            settings=RenderSettings(dpi=150, lang="por+eng"),
        )
        assert rasterizer.calls == [(tmp_path / "in.pdf", 10, 150)]

    def test_ocr_receives_the_language(self, tmp_path: Path) -> None:
        engine = FakeOcr()
        texts = [_framed(n, _body(n)) for n in range(1, 10)] + [_framed(10)]
        transcribe(
            tmp_path / "in.pdf",
            tmp_path / "out.md",
            extractor=FakeExtractor(texts),
            writer=FakeWriter(),
            rasterizer=FakeRasterizer(),
            ocr=engine,
            settings=RenderSettings(lang="por+eng"),
        )
        assert engine.calls[0][1] == "por+eng"


class TestConfidence:
    """Tests for the low-confidence flag."""

    def test_low_confidence_page_is_counted(self, tmp_path: Path) -> None:
        texts = [_framed(n, _body(n)) for n in range(1, 10)] + [_framed(10)]
        writer = FakeWriter()
        result = transcribe(
            tmp_path / "in.pdf",
            tmp_path / "out.md",
            extractor=FakeExtractor(texts),
            writer=writer,
            rasterizer=FakeRasterizer(),
            ocr=FakeOcr(text="lixo", confidence=0.42),
        )
        assert result.flagged_pages == 1

    def test_high_confidence_page_is_not_flagged(self, tmp_path: Path) -> None:
        texts = [_framed(n, _body(n)) for n in range(1, 10)] + [_framed(10)]
        result, _ = _run(tmp_path, texts)
        assert result.flagged_pages == 0


class TestResult:
    """Tests for the reported outcome."""

    def test_reports_paths(self, tmp_path: Path) -> None:
        result, _ = _run(tmp_path, [_framed(n, _body(n)) for n in range(1, 4)])
        assert result.input_path == tmp_path / "in.pdf"
        assert result.output_path == tmp_path / "out.md"

    def test_output_bytes_match_the_written_text(self, tmp_path: Path) -> None:
        result, writer = _run(tmp_path, [_framed(n, _body(n)) for n in range(1, 4)])
        assert result.output_bytes == len(writer.calls[0][0].encode("utf-8"))

    def test_page_text_survives_the_pipeline(self, tmp_path: Path) -> None:
        page = "Recur-\nso  especial\n\n42\n\nfls. 7"
        _, writer = _run(tmp_path, [page, _framed(2, _body(2)), _framed(3, _body(3))])
        assert page in writer.calls[0][0]
