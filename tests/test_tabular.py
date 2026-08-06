"""A spreadsheet turned into evidence.

The point of this converter is not the markdown table -- it is that a quote taken from
the table can still be located mechanically, and that the document says which bytes it
came from. So the load-bearing test is the last one: a fact register citing a converted
row must pass `validate-facts` unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from easkills import cli, facts, tabular


def _csv(tmp_path: Path, name: str, content: str, encoding: str = "utf-8") -> Path:
    path = tmp_path / name
    path.write_bytes(content.encode(encoding))
    return path


# --------------------------------------------------------------------- delimiters


@pytest.mark.parametrize(
    ("delimiter", "label"),
    [(",", ","), (";", ";"), ("\t", "\t"), ("|", "|")],
)
def test_each_supported_delimiter_is_detected(tmp_path, delimiter, label):
    source = _csv(
        tmp_path,
        "inventory.csv",
        delimiter.join(["Application", "Owner"]) + "\n" + delimiter.join(["CRM", "sales@x.test"]) + "\n",
    )
    report = tabular.convert(source, tmp_path / "out.md")
    assert report.delimiter == label
    assert report.columns == ["Application", "Owner"]
    assert report.rows == 1


def test_a_comma_inside_a_quoted_cell_does_not_win_over_the_real_delimiter(tmp_path):
    """Frequency-based sniffing picks the comma here and produces a table whose columns
    shift row by row -- authoritative-looking and silently misaligned."""
    source = _csv(
        tmp_path,
        "people.csv",
        'Name;Team\n"Smith, J.";Sales\n"Nowak, A.";Finance\n',
    )
    report = tabular.convert(source, tmp_path / "out.md")
    assert report.delimiter == ";"
    assert report.columns == ["Name", "Team"]
    text = (tmp_path / "out.md").read_text(encoding="utf-8")
    assert "| Smith, J. | Sales |" in text


def test_a_single_column_file_still_converts(tmp_path):
    source = _csv(tmp_path, "hosts.csv", "Hostname\nsrv-01\nsrv-02\n")
    report = tabular.convert(source, tmp_path / "out.md")
    assert report.columns == ["Hostname"] and report.rows == 2


# ------------------------------------------------------------------ what Excel does


def test_a_byte_order_mark_is_read_not_pasted_into_the_first_column(tmp_path):
    source = _csv(tmp_path, "excel.csv", "Application,Owner\nCRM,sales@x.test\n", encoding="utf-8-sig")
    report = tabular.convert(source, tmp_path / "out.md")
    assert report.columns == ["Application", "Owner"], "the BOM must not become part of a header"
    assert report.encoding == "utf-8-sig"


def test_cp1252_content_is_read(tmp_path):
    source = _csv(
        tmp_path, "latin.csv", "Application,Owner\nZürich Datacentre,it@x.test\n", encoding="cp1252"
    )
    report = tabular.convert(source, tmp_path / "out.md")
    assert report.encoding in {"utf-8", "cp1252"}
    assert "it@x.test" in (tmp_path / "out.md").read_text(encoding="utf-8")


def test_a_line_break_inside_a_cell_is_flattened_and_reported(tmp_path):
    """Each row has to stay one line, or a quote cannot be one line either."""
    source = _csv(tmp_path, "notes.csv", 'App,Note\nCRM,"first line\nsecond line"\n')
    report = tabular.convert(source, tmp_path / "out.md")
    assert report.flattened == [2]
    text = (tmp_path / "out.md").read_text(encoding="utf-8")
    assert "| CRM | first line second line |" in text
    assert "line breaks" in text


def test_a_pipe_in_a_cell_does_not_break_the_table(tmp_path):
    source = _csv(tmp_path, "pipes.csv", "App,Note\nCRM,a | b\n")
    tabular.convert(source, tmp_path / "out.md")
    row = next(
        line
        for line in (tmp_path / "out.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("| CRM")
    )
    assert row.replace(r"\|", "").count("|") == 3, "the escaped pipe must not read as a column break"
    assert r"a \| b" in row


def test_ragged_rows_are_padded_and_named(tmp_path):
    source = _csv(tmp_path, "ragged.csv", "A,B,C\n1,2,3\n4,5\n6,7,8,9\n")
    report = tabular.convert(source, tmp_path / "out.md")
    assert [item["row"] for item in report.ragged] == [3, 4]
    text = (tmp_path / "out.md").read_text(encoding="utf-8")
    assert "Ragged rows" in text
    assert "| 4 | 5 |  |" in text, "short rows are padded, never dropped"
    assert report.columns == ["A", "B", "C", "column4"]
    assert "| 6 | 7 | 8 | 9 |" in text, "and long rows widen the table instead of losing a cell"


def test_no_cell_is_ever_dropped(tmp_path):
    """A converted document is quoted from; a silently truncated cell is evidence lost.

    The adoption fixture found this: a semicolon inside an unquoted Notes cell made one
    row wider than its header, and the overflow -- "no owner named for the batch
    scheduler" -- vanished from the table while the header politely said "truncated".
    """
    source = _csv(tmp_path, "wide.csv", "App;Note\nBilling;Nightly batch; no owner named\n")
    report = tabular.convert(source, tmp_path / "out.md")
    text = (tmp_path / "out.md").read_text(encoding="utf-8")
    assert "no owner named" in text
    assert report.ragged and "nothing dropped" in text


def test_a_blank_line_is_not_a_row(tmp_path):
    source = _csv(tmp_path, "gaps.csv", "A,B\n1,2\n\n3,4\n")
    report = tabular.convert(source, tmp_path / "out.md")
    assert report.rows == 2


# ------------------------------------------------------------------------ recording


def test_the_document_records_the_bytes_it_came_from(tmp_path):
    source = _csv(tmp_path, "inventory.csv", "A,B\n1,2\n")
    report = tabular.convert(source, tmp_path / "out.md")
    text = (tmp_path / "out.md").read_text(encoding="utf-8")
    assert report.sha256 in text
    assert "inventory.csv" in text
    assert "Do not edit" in text


def test_conversion_is_byte_stable(tmp_path):
    source = _csv(tmp_path, "inventory.csv", "A,B\n1,2\n")
    tabular.convert(source, tmp_path / "one.md")
    tabular.convert(source, tmp_path / "two.md")
    assert (tmp_path / "one.md").read_bytes() == (tmp_path / "two.md").read_bytes()


def test_an_existing_document_is_never_replaced_silently(tmp_path):
    source = _csv(tmp_path, "inventory.csv", "A,B\n1,2\n")
    tabular.convert(source, tmp_path / "out.md")
    with pytest.raises(tabular.TabularError, match="already exists"):
        tabular.convert(source, tmp_path / "out.md")
    tabular.convert(source, tmp_path / "out.md", overwrite=True)


def test_an_empty_or_missing_file_is_refused(tmp_path):
    with pytest.raises(tabular.TabularError, match="does not exist"):
        tabular.convert(tmp_path / "nope.csv", tmp_path / "out.md")
    with pytest.raises(tabular.TabularError, match="is empty"):
        tabular.convert(_csv(tmp_path, "empty.csv", "   \n"), tmp_path / "out.md")


# ----------------------------------------------- the reason the converter exists


def test_a_fact_can_cite_a_converted_row_and_pass_the_evidence_gate(tmp_path):
    """End to end: spreadsheet in, verified quote out, no hand editing anywhere."""
    repo = tmp_path / "repo"
    (repo / "facts" / "register").mkdir(parents=True)
    (repo / "facts" / "sources").mkdir(parents=True)
    source = _csv(
        repo,
        "inventory-2026-08.csv",
        "Application;Owner;Hosting\nCRM Suite;crm-team@x.test;on-premise\n",
    )
    tabular.convert(source, repo / "facts" / "sources" / "inventory-2026-08.md")
    (repo / "facts" / "register" / "inventory.yaml").write_text(
        "facts:\n"
        "  - id: fact-crm-on-premise\n"
        "    statement: The CRM suite is hosted on premise and owned by the CRM team.\n"
        "    provenance:\n"
        "      - file: facts/sources/inventory-2026-08.md\n"
        '        quote: "| CRM Suite | crm-team@x.test | on-premise |"\n',
        encoding="utf-8",
        newline="\n",
    )
    report = facts.validate_facts(repo)
    assert report.ok, report.render()
    assert not [f for f in report.findings if f.code in {"FACT004", "FACT005"}], (
        "the quote must be located exactly, not approximately"
    )


# ------------------------------------------------------------------------------ CLI


def test_cli_converts_into_the_configured_sources_directory(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _csv(repo, "inventory.csv", "A,B\n1,2\n")
    assert cli.main(["intake-csv", "--root", str(repo), "--file", str(source)]) == 0
    assert (repo / "facts" / "sources" / "inventory.md").is_file()
    out = capsys.readouterr().out
    assert "Converted 1 row(s) x 2 column(s)" in out
    assert "nothing here interpreted a single column" in out


def test_cli_refuses_and_exits_one(tmp_path, capsys):
    assert cli.main(["intake-csv", "--root", str(tmp_path), "--file", str(tmp_path / "no.csv")]) == 1
    assert "ERROR" in capsys.readouterr().out
