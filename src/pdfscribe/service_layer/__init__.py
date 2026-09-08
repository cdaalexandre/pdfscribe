"""Service layer - re-exports."""

from __future__ import annotations

from pdfscribe.service_layer.transcriber import TranscribeResult, transcribe  # noqa: F401

__all__ = ["TranscribeResult", "transcribe"]
