"""The same text in another encoding is the same text (D9) -- and a changed word is not.

Every case here is a pair the matcher must call identical, or a pair it must not, and each
is checked on both readers of the folding table: the quote matcher and the coverage
segmenter. They used to agree by accident (both only collapsed whitespace and case); now
they agree because they read one table.
"""

from __future__ import annotations

import unicodedata

import pytest

from easkills import intake, propose, textfold
from easkills.validate import _normalize, _quote_match

SOURCE_NFC = "Zespół IT obsługuje „System Księgowy” – od lat – i fakturę wystawia co miesiąc."


@pytest.mark.parametrize(
    ("source", "quote"),
    [
        # A decomposed export against a composed quote (macOS, some PDF converters).
        (unicodedata.normalize("NFD", SOURCE_NFC), SOURCE_NFC),
        (SOURCE_NFC, unicodedata.normalize("NFD", SOURCE_NFC)),
        # Typographic quotation marks and dashes against ASCII ones.
        (SOURCE_NFC, 'Zespół IT obsługuje "System Księgowy" - od lat - i fakturę wystawia co miesiąc.'),
        ("He said “the ERP is slow” — twice.", 'He said "the ERP is slow" - twice.'),
        ("the vendor’s portal", "the vendor's portal"),
        # Compatibility forms: a ligature, a non-breaking space, an ellipsis.
        ("the ﬁnance team", "the finance team"),
        ("16 GB of memory", "16 GB of memory"),
        ("and so on…", "and so on..."),
        # Invisible characters a word processor leaves behind.
        ("infra­structure team", "infrastructure team"),
        ("order​portal", "orderportal"),
    ],
)
def test_an_encoding_difference_is_an_exact_match(source, quote):
    assert _quote_match(_normalize(source), _normalize(quote), 0.90) == "exact"


def test_a_changed_word_is_still_only_approximate():
    source = "The ERP core holds the master order records and does the invoicing."
    quote = "The ERP core keeps the master order records and does the invoicing."
    assert _quote_match(_normalize(source), _normalize(quote), 0.90) == "approx"


def test_end_of_line_hyphenation_is_deliberately_not_folded():
    """Joining a hyphenated line break would also join words hyphenated on purpose."""
    source = "the infra-\nstructure team runs it"
    assert _quote_match(_normalize(source), _normalize("the infrastructure team runs it"), 0.99) != "exact"


def test_units_fold_exactly_like_the_whole_string():
    """Cluster-by-cluster folding (what coverage needs for line numbers) must produce the
    same characters as folding the string at once (what the matcher does)."""
    korean = unicodedata.normalize("NFD", "한국어 시스템")  # conjoining jamo: no combining class
    for text in (SOURCE_NFC, unicodedata.normalize("NFD", SOURCE_NFC), "ﬁ “x” — ­ y…", "İstanbul ǅ ß", korean):
        assert "".join(unit for _start, _end, unit in textfold.units(text)) == textfold.fold(text).casefold()


def test_a_composing_script_without_combining_marks_still_covers(tmp_path):
    """Found by review: clusters split only on combining marks left Hangul jamo unfolded in
    coverage while the matcher composed them, so a cited sentence read as uncited."""
    korean = "고객 포털은 주문 시스템에 연결된다."
    source = unicodedata.normalize("NFD", korean)
    assert _quote_match(_normalize(source), _normalize(korean), 0.90) == "exact"
    norm, _lines, _paras = intake._index_source(source)
    assert _normalize(korean) in norm


def test_units_map_every_folded_character_back_to_its_source_span():
    text = unicodedata.normalize("NFD", "żółw")
    spans = [(start, end) for start, end, _unit in textfold.units(text)]
    assert spans[0] == (0, 2), "z + combining dot above is one cluster"
    assert "".join(text[s:e] for s, e in spans) == text


def test_coverage_counts_a_decomposed_source_as_covered_by_a_composed_quote(tmp_path):
    (tmp_path / "ea.config.yaml").write_text("name: T\n", encoding="utf-8")
    sources = tmp_path / "facts" / "sources"
    sources.mkdir(parents=True)
    (sources / "wywiad.md").write_text(
        "# Wywiad\n\n" + unicodedata.normalize("NFD", SOURCE_NFC) + "\n", encoding="utf-8"
    )
    register = tmp_path / "facts" / "register"
    register.mkdir(parents=True)
    (register / "wywiad.yaml").write_text(
        "facts:\n"
        "  - id: fact-ksiegowy\n"
        "    statement: Zespół IT obsługuje System Księgowy.\n"
        "    provenance:\n"
        "      - file: facts/sources/wywiad.md\n"
        f"        quote: {SOURCE_NFC}\n",
        encoding="utf-8",
    )
    report = intake.coverage(tmp_path)
    assert (report.covered, report.sentences) == (1, 1)


def test_question_skeletons_keep_the_sources_own_characters():
    original = "Intro.\nThe board said “keep the ERP” — for now.\n"
    normalized = _normalize("The board said “keep the ERP” — for now.")
    assert propose._verbatim(original, normalized) == "The board said “keep the ERP” — for now."
    decomposed = unicodedata.normalize("NFD", "Zarząd mówi: „zostaje”.")
    assert propose._verbatim(decomposed, _normalize("Zarząd mówi: „zostaje”.")) == decomposed
