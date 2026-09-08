"""Tests - splitter (domain layer, pure logic)."""

from __future__ import annotations

import pytest

from pdfscribe.domain.splitter import (
    DEFAULT_MAX_BYTES,
    SplitSettings,
    part_filename,
    plan_parts,
    starts_new_part,
)


class TestSplitSettings:
    """Tests for the split value object."""

    def test_default_is_three_megabytes(self) -> None:
        assert SplitSettings().max_bytes == DEFAULT_MAX_BYTES

    def test_is_frozen(self) -> None:
        with pytest.raises(AttributeError):
            SplitSettings().max_bytes = 10

    def test_rejects_a_ceiling_too_small(self) -> None:
        with pytest.raises(ValueError, match="at least"):
            SplitSettings(max_bytes=10)

    def test_from_env_uses_the_default_when_unset(self) -> None:
        assert SplitSettings.from_env({}) == SplitSettings()

    def test_from_env_overrides(self) -> None:
        assert SplitSettings.from_env({"PDFSCRIBE_MAX_BYTES": "8192"}).max_bytes == 8192

    def test_from_env_rejects_non_integer(self) -> None:
        with pytest.raises(ValueError, match="must be an integer"):
            SplitSettings.from_env({"PDFSCRIBE_MAX_BYTES": "tres megas"})


class TestStartsNewPart:
    """Tests for the accumulation rule."""

    def test_empty_part_never_starts_another(self) -> None:
        # This is what keeps an oversized page whole.
        assert starts_new_part(0, 10_000, 100) is False

    def test_block_that_fits_does_not_close_the_part(self) -> None:
        assert starts_new_part(50, 40, 100) is False

    def test_exact_fit_does_not_close_the_part(self) -> None:
        assert starts_new_part(60, 40, 100) is False

    def test_block_that_overflows_closes_the_part(self) -> None:
        assert starts_new_part(60, 41, 100) is True


class TestPlanParts:
    """Tests for planning the shape of the output."""

    def test_no_blocks_no_parts(self) -> None:
        assert plan_parts([], 100) == []

    def test_everything_fits_in_one_part(self) -> None:
        assert plan_parts([10, 20, 30], 100) == [3]

    def test_splits_when_the_ceiling_is_reached(self) -> None:
        assert plan_parts([40, 40, 40], 100) == [2, 1]

    def test_oversized_block_gets_its_own_part(self) -> None:
        # A page larger than the ceiling is never cut in half.
        assert plan_parts([10, 500, 10], 100) == [1, 1, 1]

    def test_every_block_is_accounted_for(self) -> None:
        sizes = [37, 12, 88, 5, 61, 44, 90, 3]
        assert sum(plan_parts(sizes, 100)) == len(sizes)

    def test_a_single_oversized_block(self) -> None:
        assert plan_parts([9999], 100) == [1]


class TestPartFilename:
    """Tests for how parts are named."""

    def test_single_part_keeps_the_plain_name(self) -> None:
        assert part_filename("autos", ".md", 1, multi=False) == "autos.md"

    def test_multiple_parts_are_numbered(self) -> None:
        assert part_filename("autos", ".md", 1, multi=True) == "autos_part01.md"

    def test_numbering_is_zero_padded(self) -> None:
        assert part_filename("autos", ".md", 7, multi=True) == "autos_part07.md"

    def test_numbering_grows_past_ninety_nine(self) -> None:
        assert part_filename("autos", ".md", 100, multi=True) == "autos_part100.md"
