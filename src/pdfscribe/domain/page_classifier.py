"""Decide, page by page, where a page's text has to come from.

Fundamentacao: Percival & Gregory, Architecture Patterns, Cap. 4.g.
'Keep the domain free of dependencies so the rules stay readable.'

The cascade, in order, and what each step was measured against:

1. No own text - only the document's frame - means nothing on this page
   was ever text. It goes to OCR. Measured on a real filing, this alone
   isolated the 31 scanned pages out of 81, exactly and with no
   threshold to tune.

2. Own text that is mostly not text - a font with no ToUnicode map
   yields characters that are not letters - also goes to OCR. This step
   has no measured example yet in this project 🟡.

3. Own text plus ink the text layer does not explain goes to both:
   the native text is kept literally and OCR reads the rest.

4. Otherwise the page is native.

What deliberately is NOT in the cascade: image presence. On the filing
measured, a full-page signature watermark sat behind every page, so
'has an image' was true 81 times out of 81 and separated nothing. What
separated was ink the text layer could not account for, which is why
the rasterizer measures area rather than counting images.

Logica pura. Nao conhece APIs, nao faz I/O.
"""

from __future__ import annotations

from pdfscribe.domain.fidelity import FidelityThresholds, PageSource

_PUNCTUATION = frozenset(".,;:!?()[]{}-\u2013\u2014'\"/\\|@#%&*+=<>\u00ba\u00aa\u00a7\u00b0$_~^`")


def garbage_ratio(text: str) -> float:
    """Measure how much of a text is neither letter, digit nor punctuation.

    A healthy text layer is almost entirely alphanumeric and
    punctuation. A broken one - the classic case being a font with no
    ToUnicode map - is full of replacement characters and symbols that
    belong to no alphabet.

    Args:
        text: The page text under test.

    Returns:
        The share of non-space characters that are neither alphanumeric
        nor punctuation, from 0.0 to 1.0. An empty text scores 0.0.
    """
    body = [char for char in text if not char.isspace()]
    if not body:
        return 0.0
    strange = sum(1 for char in body if not (char.isalnum() or char in _PUNCTUATION))
    return strange / len(body)


def classify_page(
    own_text: str,
    ink_ratio: float = 0.0,
    thresholds: FidelityThresholds | None = None,
) -> PageSource:
    """Decide where the text of one page has to come from.

    Args:
        own_text: The page text with the document's frame removed.
        ink_ratio: Share of the page covered by marks the text layer
            does not explain, from 0.0 to 1.0.
        thresholds: Limits to apply. Defaults to FidelityThresholds().

    Returns:
        NATIVE, OCR or MIXED. EMPTY is never returned here: a page with
        no own text is sent to OCR, and only OCR coming back empty
        settles that the page is blank.
    """
    limits = thresholds if thresholds is not None else FidelityThresholds()

    if not own_text.strip():
        return PageSource.OCR
    if garbage_ratio(own_text) > limits.max_garbage_ratio:
        return PageSource.OCR
    if ink_ratio >= limits.mixed_ink_ratio:
        return PageSource.MIXED
    return PageSource.NATIVE
