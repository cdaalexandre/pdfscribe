"""Tests - write_transcript adapter with real files.

write_transcript has no dependency beyond the filesystem, so the real
function is tested against tmp_path (Percival & Gregory, Cap. 3.c.ii:
prefer real over mock when there is no boundary).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pdfscribe.adapters.file_io import write_transcript

if TYPE_CHECKING:
    from pathlib import Path


class TestWriteTranscript:
    """Tests for the transcript writer adapter."""

    def test_creates_the_file(self, tmp_path: Path) -> None:
        out = tmp_path / "out.md"
        assert write_transcript("corpo\n", out) == out
        assert out.exists()

    def test_writes_lf_not_crlf(self, tmp_path: Path) -> None:
        # Lesson 12: Path.write_text would emit CRLF here on Windows.
        out = tmp_path / "out.md"
        write_transcript("linha um\nlinha dois\n", out)
        assert b"\r\n" not in out.read_bytes()

    def test_bytes_are_identical_to_the_input(self, tmp_path: Path) -> None:
        out = tmp_path / "out.md"
        text = "<!-- p.1 | fonte: nativo | conf: 1.00 | folha: 7 -->\nRecur-\nso  especial\n"
        write_transcript(text, out)
        assert out.read_bytes() == text.encode("utf-8")

    def test_preserves_a_lone_carriage_return(self, tmp_path: Path) -> None:
        # A CR inside the page text belongs to the page, not to us.
        out = tmp_path / "out.md"
        write_transcript("antes\rdepois", out)
        assert out.read_bytes() == b"antes\rdepois"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        out = tmp_path / "deep" / "nested" / "out.md"
        write_transcript("corpo", out)
        assert out.exists()

    def test_preserves_unicode(self, tmp_path: Path) -> None:
        out = tmp_path / "out.md"
        write_transcript("A\u00e7\u00e3o em S\u00e3o Paulo. Caf\u00e9.", out)
        assert out.read_text(encoding="utf-8") == "A\u00e7\u00e3o em S\u00e3o Paulo. Caf\u00e9."
