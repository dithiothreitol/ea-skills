"""One definition of "the same text" for every matcher in the core (D9).

A quote is verified by locating it in its source, and the coverage report decides which
source statements a quote covers. Both used to compare text after collapsing whitespace
and folding case -- and nothing else. So a Polish interview exported in decomposed form
(``a`` + combining ogonek) never matched a quote typed in composed form, and a quote with
straight quotation marks matched a source with typographic ones only *approximately*:
``PROV004`` under ``--strict`` is an error, raised against a verbatim quote. The words
were identical; the encoding was not.

This module folds exactly the differences that are encoding, never wording:

* **Unicode compatibility forms (NFKC):** composed and decomposed letters, ligatures
  (``ﬁ``), full-width forms, non-breaking and other typographic spaces, the ellipsis.
* **Typographic quotation marks and dashes:** ``„ ” “ ‘ ’ « »`` and ``‐ ‑ ‒ – — ―  −``
  read as their ASCII counterparts.
* **Invisible characters:** the soft hyphen, zero-width spaces and joiners, the word
  joiner and a stray byte-order mark.

It deliberately does **not** fold end-of-line hyphenation: joining ``infra-`` and
``structure`` across a line break would also join words hyphenated on purpose, and a
matcher that guesses which is which accepts text the source does not contain. A changed
*word* stays a ``PROV004``; the record keeps the quote as its author typed it.

Standard library only, and no state: the matcher, the coverage segmenter and the
verbatim-recovery step of ``propose --from coverage`` all read this one table, so the
three can never disagree about whether two strings are the same text.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterator

_FOLD = str.maketrans(
    {
        # Single quotation marks and the apostrophe's typographic forms.
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "‹": "'",
        "›": "'",
        # Double quotation marks, including the Polish low-high pair and guillemets.
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "«": '"',
        "»": '"',
        # Hyphens and dashes (NFKC already maps U+2011 to U+2010).
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "―": "-",
        "−": "-",
        # Invisible characters: soft hyphen, zero-width space and joiners, word joiner, BOM.
        "­": None,
        "​": None,
        "‌": None,
        "‍": None,
        "⁠": None,
        "﻿": None,
    }
)
_WHITESPACE_RE = re.compile(r"\s+")


def fold(text: str) -> str:
    """Fold encoding-only differences. Case and spacing are left as they are."""
    return unicodedata.normalize("NFKC", text).translate(_FOLD)


def normalize(text: str) -> str:
    """The matcher's form of ``text``: folded, whitespace collapsed, case folded."""
    return _WHITESPACE_RE.sub(" ", fold(text)).strip().casefold()


def _joins(cluster: str, ch: str) -> bool:
    """True when ``ch`` composes with the cluster before it under NFKC.

    Combining marks do, and so do characters with no combining class that still compose --
    Hangul conjoining jamo, which macOS exports Korean as, are the common case. The test is
    the definition itself: normalizing the pair differs from normalizing each part. An
    ASCII character never composes with what precedes it, so ASCII text never pays for it.
    """
    if unicodedata.combining(ch):
        return True
    if ch.isascii():
        return False
    return unicodedata.normalize("NFKC", cluster + ch) != (
        unicodedata.normalize("NFKC", cluster) + unicodedata.normalize("NFKC", ch)
    )


def units(text: str) -> Iterator[tuple[int, int, str]]:
    """``(start, end, folded)`` for each cluster of ``text``, in order.

    A cluster is a run of characters NFKC composes together -- a letter and its combining
    marks, a Hangul syllable written as jamo -- so folding cluster by cluster produces the
    same characters as folding the whole string, while every folded character can still be
    traced back to the span of the original it came from. The coverage report needs that
    for line numbers, and ``propose --from coverage`` needs it to return the source's own
    characters. ``folded`` is case folded and may be empty (an invisible character) or
    longer than the cluster (a ligature).
    """
    length = len(text)
    start = 0
    while start < length:
        end = start + 1
        while end < length and _joins(text[start:end], text[end]):
            end += 1
        cluster = text[start:end]
        if cluster.isascii():
            yield start, end, cluster.casefold()
        else:
            yield start, end, unicodedata.normalize("NFKC", cluster).translate(_FOLD).casefold()
        start = end
