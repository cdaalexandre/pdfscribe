"""Tests - transcriber service layer with Fakes.

Percival & Gregory, Architecture Patterns, Cap. 3.c.ii:
'Why Not Just Patch It Out? - every call to mock.patch is a ticking
time bomb.'

Percival & Gregory, Cap. 13:
'Declaring an explicit dependency is an example of the dependency
inversion principle.'
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pdfscribe.domain.transcript import RawPage
from pdfscribe.service_layer.transcriber import TranscribeResult, transcribe

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class FakeExtractor:
    """Test double that returns canned page texts instead of reading a PDF.

    `declared` overrides the reported page count, so the no-page-is-lost
    guard can be exercised without a corrupt file.
    """

    def __init__(self, texts: list[str], declared: int | None = None) -> None:
        self.texts = texts
        self.declared = declared if declared is not None else len(texts)
        self.count_calls: list[Path] = []
        self.page_calls: list[Path] = []

    def page_count(self, path: Path) -> int:
        self.count_calls.append(path)
        return self.declared

    def pages(self, path: Path) -> Iterator[RawPage]:
        self.page_calls.append(path)
        return iter([RawPage(number=i + 1, text=t) for i, t in enumerate(self.texts)])


class FakeWriter:
    """Test double that records what it was asked to write."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    def __call__(self, text: str, path: Path) -> Path:
        self.calls.append((text, path))
        return path


class TestTranscribe:
    """Tests for the transcribe use case."""

    def test_returns_a_result(self, tmp_path: Path) -> None:
        result = transcribe(
            tmp_path / "in.pdf",
            tmp_path / "out.md",
            extractor=FakeExtractor(["a"]),
            writer=FakeWriter(),
        )
        assert isinstance(result, TranscribeResult)

    def test_no_page_is_lost(self, tmp_path: Path) -> None:
        # Fidelity contract, rule 5. One marker per page, always.
        texts = ["um", "", "tres", "quatro", ""]
        writer = FakeWriter()
        result = transcribe(
            tmp_path / "in.pdf",
            tmp_path / "out.md",
            extractor=FakeExtractor(texts),
            writer=writer,
        )
        written = writer.calls[0][0]
        assert result.page_count == len(texts)
        assert written.count("<!-- p.") == len(texts)
        for number in range(1, len(texts) + 1):
            assert f"<!-- p.{number} |" in written

    def test_page_loss_raises(self, tmp_path: Path) -> None:
        # The document claims 5 pages, the reader yields 3.
        with pytest.raises(RuntimeError, match="page loss"):
            transcribe(
                tmp_path / "in.pdf",
                tmp_path / "out.md",
                extractor=FakeExtractor(["a", "b", "c"], declared=5),
                writer=FakeWriter(),
            )

    def test_counts_native_and_empty_pages(self, tmp_path: Path) -> None:
        result = transcribe(
            tmp_path / "in.pdf",
            tmp_path / "out.md",
            extractor=FakeExtractor(["um", "", "tres", ""]),
            writer=FakeWriter(),
        )
        assert result.native_pages == 2
        assert result.empty_pages == 2

    def test_writer_receives_the_output_path(self, tmp_path: Path) -> None:
        writer = FakeWriter()
        out = tmp_path / "nested" / "out.md"
        transcribe(tmp_path / "in.pdf", out, extractor=FakeExtractor(["a"]), writer=writer)
        assert writer.calls[0][1] == out

    def test_extractor_receives_the_input_path(self, tmp_path: Path) -> None:
        extractor = FakeExtractor(["a"])
        source = tmp_path / "in.pdf"
        transcribe(source, tmp_path / "out.md", extractor=extractor, writer=FakeWriter())
        assert extractor.count_calls == [source]
        assert extractor.page_calls == [source]

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        writer = FakeWriter()
        result = transcribe(
            tmp_path / "in.pdf",
            tmp_path / "out.md",
            dry_run=True,
            extractor=FakeExtractor(["um", "dois"]),
            writer=writer,
        )
        assert writer.calls == []
        assert result.written is False

    def test_dry_run_still_measures_everything(self, tmp_path: Path) -> None:
        result = transcribe(
            tmp_path / "in.pdf",
            tmp_path / "out.md",
            dry_run=True,
            extractor=FakeExtractor(["um", "dois"]),
            writer=FakeWriter(),
        )
        assert result.page_count == 2
        assert result.native_pages == 2
        assert result.output_bytes > 0

    def test_output_bytes_match_the_written_text(self, tmp_path: Path) -> None:
        writer = FakeWriter()
        result = transcribe(
            tmp_path / "in.pdf",
            tmp_path / "out.md",
            extractor=FakeExtractor(["acentuacao e cedilha"]),
            writer=writer,
        )
        assert result.output_bytes == len(writer.calls[0][0].encode("utf-8"))

    def test_page_text_survives_the_pipeline(self, tmp_path: Path) -> None:
        # End-to-end literalidade: what the reader returned is what the
        # writer receives, byte for byte.
        writer = FakeWriter()
        page = "Recur-\nso  especial\n\n42\n\nfls. 7"
        transcribe(
            tmp_path / "in.pdf",
            tmp_path / "out.md",
            extractor=FakeExtractor([page]),
            writer=writer,
        )
        assert page in writer.calls[0][0]

    def test_writer_is_called_once(self, tmp_path: Path) -> None:
        writer = FakeWriter()
        transcribe(
            tmp_path / "in.pdf",
            tmp_path / "out.md",
            extractor=FakeExtractor(["a", "b", "c"]),
            writer=writer,
        )
        assert len(writer.calls) == 1
