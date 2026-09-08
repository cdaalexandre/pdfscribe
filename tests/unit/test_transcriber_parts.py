"""Tests - splitting and the run log, through the service layer.

The Fakes here are the same shape as the ones in test_transcriber: they
record what they were asked to do, so the assertions are about behaviour
rather than about calls being patched away.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pdfscribe.domain.ocr import OcrOutcome
from pdfscribe.domain.run_log import LOG_HEADER
from pdfscribe.domain.splitter import SplitSettings
from pdfscribe.domain.transcript import RawPage
from pdfscribe.service_layer.transcriber import transcribe

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class FakeExtractor:
    """Test double that returns canned pages instead of reading a PDF."""

    def __init__(self, texts: list[str]) -> None:
        self.texts = texts

    def page_count(self, path: Path) -> int:
        return len(self.texts)

    def pages(self, path: Path) -> Iterator[RawPage]:
        return iter([RawPage(number=index + 1, text=text) for index, text in enumerate(self.texts)])


class FakeOcr:
    """Test double that returns a canned reading."""

    def read(self, image: bytes, lang: str) -> OcrOutcome:
        return OcrOutcome(text="", confidence=0.0, words=0)


class FakeRasterizer:
    """Test double that returns canned bytes."""

    def render(self, path: Path, number: int, dpi: int) -> bytes:
        return b"PNG"


class FakeWriter:
    """Test double that records every file it was asked to write."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    def __call__(self, text: str, path: Path) -> Path:
        self.calls.append((text, path))
        return path

    def named(self, suffix: str) -> list[tuple[str, Path]]:
        """Return the calls whose path ends with a suffix."""
        return [call for call in self.calls if call[1].name.endswith(suffix)]


_SUBJECTS = ("inventario", "agravo", "peticao", "certidao", "mandado", "acordao", "sentenca")


def _pages(count: int, filler: int = 400) -> list[str]:
    """Build pages large enough to force splitting.

    Each page is worded differently, not merely numbered differently:
    the frame detector collapses runs of digits, so pages that vary only
    by number would all share one signature and be taken for boilerplate.
    """
    pages = []
    for number in range(1, count + 1):
        subject = _SUBJECTS[number % len(_SUBJECTS)]
        pages.append(f"Trata-se de {subject} nos autos.\n" + f"{subject} " * filler)
    return pages


def _run(tmp_path: Path, texts: list[str], max_bytes: int) -> tuple[object, FakeWriter]:
    """Run transcribe with Fakes and the given ceiling."""
    writer = FakeWriter()
    result = transcribe(
        tmp_path / "in.pdf",
        tmp_path / "autos.md",
        extractor=FakeExtractor(texts),
        writer=writer,
        rasterizer=FakeRasterizer(),
        ocr=FakeOcr(),
        split=SplitSettings(max_bytes=max_bytes),
    )
    return result, writer


class TestSinglePart:
    """Tests for a transcript that fits in one file."""

    def test_keeps_the_plain_name(self, tmp_path: Path) -> None:
        _, writer = _run(tmp_path, _pages(3), max_bytes=1_000_000)
        assert writer.named(".md")[0][1].name == "autos.md"

    def test_writes_one_transcript_and_one_log(self, tmp_path: Path) -> None:
        _, writer = _run(tmp_path, _pages(3), max_bytes=1_000_000)
        assert len(writer.named(".md")) == 1
        assert len(writer.named(".log")) == 1


class TestSplitting:
    """Tests for a transcript cut into parts."""

    def test_splits_into_numbered_parts(self, tmp_path: Path) -> None:
        _, writer = _run(tmp_path, _pages(6), max_bytes=8000)
        names = [call[1].name for call in writer.named(".md")]
        assert names[0] == "autos_part01.md"
        assert len(names) > 1

    def test_no_part_exceeds_the_ceiling_alone(self, tmp_path: Path) -> None:
        # A page bigger than the ceiling is allowed to overflow; two
        # pages that together overflow are not.
        _, writer = _run(tmp_path, _pages(6), max_bytes=8000)
        for text, _path in writer.named(".md"):
            assert text.count("<!-- p.") == 1 or len(text.encode("utf-8")) <= 8000

    def test_every_page_lands_in_some_part(self, tmp_path: Path) -> None:
        result, writer = _run(tmp_path, _pages(6), max_bytes=8000)
        written = "".join(text for text, _ in writer.named(".md"))
        assert written.count("<!-- p.") == 6
        assert result.page_count == 6  # type: ignore[attr-defined]

    def test_reports_the_part_names(self, tmp_path: Path) -> None:
        result, writer = _run(tmp_path, _pages(6), max_bytes=8000)
        names = [call[1].name for call in writer.named(".md")]
        assert list(result.part_names) == names  # type: ignore[attr-defined]


class TestRunLog:
    """Tests for the log written next to the transcript."""

    def test_log_sits_next_to_the_transcript(self, tmp_path: Path) -> None:
        result, _ = _run(tmp_path, _pages(3), max_bytes=1_000_000)
        assert result.log_path.name == "autos.log"  # type: ignore[attr-defined]

    def test_log_has_a_line_per_page(self, tmp_path: Path) -> None:
        _, writer = _run(tmp_path, _pages(5), max_bytes=1_000_000)
        text = writer.named(".log")[0][0]
        assert text.splitlines()[0] == LOG_HEADER
        assert len(text.splitlines()) == 6

    def test_log_names_the_part_each_page_landed_in(self, tmp_path: Path) -> None:
        _, writer = _run(tmp_path, _pages(6), max_bytes=8000)
        lines = writer.named(".log")[0][0].splitlines()[1:]
        files = {line.split("\t")[6] for line in lines}
        written = {call[1].name for call in writer.named(".md")}
        assert files == written

    def test_log_is_written_after_the_parts(self, tmp_path: Path) -> None:
        # A log naming files that do not exist yet would be a liability
        # if the run died halfway.
        _, writer = _run(tmp_path, _pages(6), max_bytes=8000)
        assert writer.calls[-1][1].name.endswith(".log")

    def test_dry_run_writes_neither(self, tmp_path: Path) -> None:
        writer = FakeWriter()
        transcribe(
            tmp_path / "in.pdf",
            tmp_path / "autos.md",
            dry_run=True,
            extractor=FakeExtractor(_pages(6)),
            writer=writer,
            rasterizer=FakeRasterizer(),
            ocr=FakeOcr(),
            split=SplitSettings(max_bytes=8000),
        )
        assert writer.calls == []
