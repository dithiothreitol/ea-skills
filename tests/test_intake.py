"""Chunking must be deterministic and line-accurate; coverage must be honest about
what the facts do and do not cite."""

import textwrap

from easkills import intake

SAMPLE = textwrap.dedent(
    """\
    # Title

    First paragraph, short and sweet.

    Second paragraph. It has two sentences in it.


    Third paragraph after a double blank line.
    It continues on a second physical line.
    """
)


# --------------------------------------------------------------------------- chunking


def test_chunker_is_deterministic():
    assert intake.chunk_text(SAMPLE, "sample.md") == intake.chunk_text(SAMPLE, "sample.md")


def test_chunk_line_numbers_are_exact():
    chunks = intake.chunk_text(SAMPLE, "sample.md", max_chars=60)
    lines = SAMPLE.splitlines()
    for chunk in chunks:
        first_line_of_chunk = chunk.text.splitlines()[0]
        assert lines[chunk.start_line - 1] == first_line_of_chunk


def test_chunks_respect_the_budget_and_pack_blocks():
    chunks = intake.chunk_text(SAMPLE, "sample.md", max_chars=60)
    assert len(chunks) > 1
    for chunk in chunks:
        # A chunk may exceed the budget only if a single block alone does.
        assert len(chunk.text) <= 60 or "\n\n" not in chunk.text


def test_chunk_ids_are_stable_sequence():
    chunks = intake.chunk_text(SAMPLE, "sample.md", max_chars=60)
    assert [c.id for c in chunks] == [f"c{i:03d}" for i in range(1, len(chunks) + 1)]


def test_oversized_block_is_split_at_line_granularity():
    text = "\n".join(f"line number {i} with some padding text" for i in range(1, 11))
    chunks = intake.chunk_text(text, "big.md", max_chars=80)
    assert len(chunks) > 1
    assert chunks[0].start_line == 1
    assert chunks[-1].end_line == 10
    # Contiguous, no line lost between chunks.
    for previous, current in zip(chunks, chunks[1:]):
        assert current.start_line == previous.end_line + 1


def test_single_line_longer_than_budget_is_kept_whole():
    text = "x" * 500
    chunks = intake.chunk_text(text, "long.md", max_chars=100)
    assert len(chunks) == 1
    assert chunks[0].text == text


# --------------------------------------------------------------------------- coverage


def test_example_sources_are_fully_covered(example_root):
    report = intake.coverage(example_root)
    assert report.files, "the worked example has two source files"
    assert report.ratio == 1.0, report.render()


def test_uncited_statements_are_reported_with_line_numbers(tmp_path):
    (tmp_path / "facts" / "sources").mkdir(parents=True)
    (tmp_path / "facts" / "register").mkdir(parents=True)
    (tmp_path / "facts" / "sources" / "doc.md").write_text(
        "The invoicing system is owned by the finance department.\n"
        "\n"
        "The warehouse robots were bought in 2024 and nobody maintains them.\n",
        encoding="utf-8",
    )
    (tmp_path / "facts" / "register" / "doc.yaml").write_text(
        "facts:\n"
        "  - id: fact-invoicing-owner\n"
        "    statement: The invoicing system is owned by the finance department.\n"
        "    provenance:\n"
        "      - file: facts/sources/doc.md\n"
        "        quote: The invoicing system is owned by the finance department.\n",
        encoding="utf-8",
    )
    report = intake.coverage(tmp_path)
    (file_coverage,) = report.files
    assert file_coverage.sentences == 2
    assert file_coverage.covered == 1
    (uncovered,) = file_coverage.uncovered
    assert uncovered.start_line == 3
    assert "warehouse robots" in uncovered.text


def test_headings_and_metadata_are_not_counted(tmp_path):
    (tmp_path / "facts" / "sources").mkdir(parents=True)
    (tmp_path / "facts" / "sources" / "doc.md").write_text(
        "# A heading long enough that it would otherwise count\n"
        "\n"
        "**Date:** 2026-07-15 and other metadata on this line\n"
        "\n"
        "| Sys | Role | Owner |\n"
        "|---|---|---|\n",
        encoding="utf-8",
    )
    report = intake.coverage(tmp_path)
    (file_coverage,) = report.files
    assert file_coverage.sentences == 0


def test_quote_spanning_two_sentences_covers_both(tmp_path):
    (tmp_path / "facts" / "sources").mkdir(parents=True)
    (tmp_path / "facts" / "register").mkdir(parents=True)
    (tmp_path / "facts" / "sources" / "doc.md").write_text(
        "The API is published by the ERP and nothing else uses it. It is the only integration point.\n",
        encoding="utf-8",
    )
    (tmp_path / "facts" / "register" / "doc.yaml").write_text(
        "facts:\n"
        "  - id: fact-api\n"
        "    statement: The API published by the ERP is the only integration point.\n"
        "    provenance:\n"
        "      - file: facts/sources/doc.md\n"
        "        quote: The API is published by the ERP and nothing else uses it. It is the only integration point.\n",
        encoding="utf-8",
    )
    report = intake.coverage(tmp_path)
    (file_coverage,) = report.files
    assert file_coverage.sentences == 2
    assert file_coverage.covered == 2


def test_coverage_report_serializes_to_json(example_root):
    payload = intake.coverage(example_root).as_dict()
    assert payload["coverage"] == 1.0
    assert len(payload["files"]) == 2
