"""Tests - run log (domain layer, pure logic)."""

from __future__ import annotations

from pdfscribe.domain.fidelity import PageMark, PageSource
from pdfscribe.domain.run_log import LOG_HEADER, PageRecord, format_log, record_of


def _record(number: int = 1, sheet: str | None = "12", part: int = 1) -> PageRecord:
    """Build a record for testing."""
    return PageRecord(
        number=number,
        source="nativo",
        confidence=1.0,
        sheet=sheet,
        size_bytes=500,
        part=part,
        filename="autos.md",
    )


class TestRecordOf:
    """Tests for building a record from a marker."""

    def test_carries_the_marker_fields(self) -> None:
        mark = PageMark(number=9, source=PageSource.OCR, confidence=0.74, sheet="404")
        record = record_of(mark, 1234, 2, "autos_part02.md")
        assert record.number == 9
        assert record.source == "ocr"
        assert record.sheet == "404"
        assert record.part == 2
        assert record.filename == "autos_part02.md"

    def test_keeps_a_missing_sheet_as_none(self) -> None:
        mark = PageMark(number=1, source=PageSource.NATIVE, confidence=1.0)
        assert record_of(mark, 10, 1, "autos.md").sheet is None


class TestFormatLog:
    """Tests for the rendered log."""

    def test_starts_with_the_header(self) -> None:
        assert format_log([]).splitlines()[0] == LOG_HEADER

    def test_one_line_per_page_plus_the_header(self) -> None:
        text = format_log([_record(n) for n in range(1, 6)])
        assert len(text.splitlines()) == 6

    def test_missing_sheet_is_written_as_a_question_mark(self) -> None:
        line = format_log([_record(sheet=None)]).splitlines()[1]
        assert line.split("\t")[3] == "?"

    def test_confidence_has_two_decimals(self) -> None:
        line = format_log([_record()]).splitlines()[1]
        assert line.split("\t")[2] == "1.00"

    def test_columns_are_tab_separated(self) -> None:
        line = format_log([_record()]).splitlines()[1]
        assert len(line.split("\t")) == len(LOG_HEADER.split("\t"))

    def test_ends_with_a_newline(self) -> None:
        assert format_log([_record()]).endswith("\n")
