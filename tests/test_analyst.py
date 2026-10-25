"""Phase 8.2: the analyst's inputs (documents, questions) and derived tables (rtm, glossary).

The document converters need optional libraries; their tests skip when one is absent, and
one test proves the core neither imports them at module level nor crashes without them --
the extras are an extras group, not a fourth runtime dependency.
"""

from __future__ import annotations

import ast
import csv
import io
import shutil
from datetime import date
from pathlib import Path

import pytest
import yaml

from easkills import analyst, documents, facts, propose, reports

REPO_ROOT = Path(__file__).resolve().parents[1]
OPTIONAL = {"pypdf", "docx", "pptx", "openpyxl"}


# ------------------------------------------------------------------------ the extras


def test_no_core_module_imports_an_intake_library_at_module_level():
    for module in sorted((REPO_ROOT / "easkills").glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in tree.body:  # module level only; lazy imports inside functions are the design
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module.split(".")[0]]
            assert not OPTIONAL & set(names), f"{module.name} imports {OPTIONAL & set(names)} at module level"


def test_the_extras_are_declared_and_kept_out_of_the_runtime_requirements():
    runtime = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    extras = (REPO_ROOT / "requirements-intake.txt").read_text(encoding="utf-8")
    for distribution in ("pypdf", "python-docx", "python-pptx", "openpyxl"):
        assert distribution not in runtime
        assert distribution in extras
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "intake = [" in pyproject


def test_a_missing_library_is_a_refusal_naming_the_install_command(tmp_path, monkeypatch):
    source = tmp_path / "policy.docx"
    source.write_bytes(b"not really a docx")

    def missing(name):
        raise ImportError(f"No module named {name!r}", name=name)

    monkeypatch.setattr(documents.importlib, "import_module", missing)
    with pytest.raises(documents.DocumentError, match="requirements-intake.txt"):
        documents.convert(source, tmp_path / "out.md")


def test_an_unsupported_kind_is_refused_and_csv_is_pointed_elsewhere(tmp_path):
    source = tmp_path / "inventory.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(documents.DocumentError, match="intake-csv"):
        documents.convert(source, tmp_path / "out.md")


def test_an_existing_target_is_never_overwritten_silently(tmp_path):
    source = tmp_path / "x.pdf"
    source.write_bytes(_minimal_pdf(["Hello there, evidence."]))
    target = tmp_path / "x.md"
    target.write_text("already cited\n", encoding="utf-8")
    with pytest.raises(documents.DocumentError, match="--overwrite"):
        documents.convert(source, target)
    assert target.read_text(encoding="utf-8") == "already cited\n"


# --------------------------------------------------------------------------- readers


def _minimal_pdf(pages: list[str]) -> bytes:
    """A valid PDF whose pages carry one text line each ('' for a page with no text)."""
    objects: list[bytes] = []
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font = 3 + 2 * len(pages)
    for index, text in enumerate(pages):
        content_id = 4 + 2 * index
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 {font} 0 R >> >> >>".encode()
        )
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode() if text else b""
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def test_a_pdf_is_converted_and_an_imageonly_page_is_named_not_skipped(tmp_path):
    pytest.importorskip("pypdf")
    source = tmp_path / "policy.pdf"
    source.write_bytes(_minimal_pdf(["Orders are retained for seven years.", ""]))
    report = documents.convert(source, tmp_path / "policy.md")
    text = (tmp_path / "policy.md").read_text(encoding="utf-8")
    assert "Orders are retained for seven years." in text
    assert "## Page 2" in text and "no extractable text" in text
    assert report.sections == 2
    assert any("page 2" in note and "OCR" in note for note in report.notes)
    assert report.sha256 in text, "the header must tie the document to the original bytes"


def test_a_word_document_keeps_body_order_headings_and_tables(tmp_path):
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_heading("Hosting policy", level=1)
    document.add_paragraph("Customer-facing workloads run in managed cloud.")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "System", "Hosting"
    table.cell(1, 0).text, table.cell(1, 1).text = "Order Portal", "cloud | managed"
    document.add_paragraph("The table above is authoritative.")
    source = tmp_path / "policy.docx"
    document.save(str(source))
    documents.convert(source, tmp_path / "policy.md")
    text = (tmp_path / "policy.md").read_text(encoding="utf-8")
    assert "## Hosting policy" in text
    assert text.index("managed cloud.") < text.index("| System | Hosting |") < text.index("authoritative")
    assert "cloud \\| managed" in text, "a pipe inside a cell must not split the row"


def test_a_deck_keeps_slide_titles_tables_and_speaker_notes(tmp_path):
    pptx = pytest.importorskip("pptx")
    from pptx.util import Inches

    deck = pptx.Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[5])  # title only
    slide.shapes.title.text = "Target state"
    box = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(6), Inches(1))
    box.text_frame.text = "The warehouse system moves to cloud hosting in 2028."
    slide.notes_slide.notes_text_frame.text = "No budget is approved yet."
    source = tmp_path / "steering.pptx"
    deck.save(str(source))
    documents.convert(source, tmp_path / "steering.md")
    text = (tmp_path / "steering.md").read_text(encoding="utf-8")
    assert "## Slide 1: Target state" in text
    assert "moves to cloud hosting in 2028." in text
    assert "**Speaker notes:**" in text and "No budget is approved yet." in text


def test_a_workbook_converts_every_sheet_and_names_uncached_formulas(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Applications"
    sheet.append(["Name", "Owner", "Users"])
    sheet.append(["CRM Suite", "crm-team@x.test", 120])
    sheet.append(["Total", "", "=SUM(C2:C2)"])
    servers = book.create_sheet("Servers")
    servers.append(["Host", "Zone"])
    servers.append(["db-01", "internal"])
    source = tmp_path / "inventory.xlsx"
    book.save(str(source))
    report = documents.convert(source, tmp_path / "inventory.md")
    text = (tmp_path / "inventory.md").read_text(encoding="utf-8")
    assert "## Sheet: Applications" in text and "## Sheet: Servers" in text
    assert "| CRM Suite | crm-team@x.test | 120 |" in text
    assert any("formula" in note for note in report.notes), "a formula never calculated must be named"


def test_conversion_is_byte_stable(tmp_path):
    pytest.importorskip("pypdf")
    source = tmp_path / "a.pdf"
    source.write_bytes(_minimal_pdf(["Stable text."]))
    documents.convert(source, tmp_path / "one.md")
    documents.convert(source, tmp_path / "two.md")
    assert (tmp_path / "one.md").read_bytes() == (tmp_path / "two.md").read_bytes()


# ------------------------------------------------------------------------- questions


def test_kpi_counts_questions_only_where_a_repository_keeps_them(example_root, tmp_path):
    data = reports.kpi(example_root, today=date(2026, 10, 25))
    assert data["questions"]["open"] == 1 and data["questions"]["answered"] == 1
    assert data["questions"]["oldestOpenDays"] == (date(2026, 10, 25) - date(2026, 7, 15)).days
    assert "Questions" in reports.render_kpi(data)
    clinic = reports.kpi(REPO_ROOT / "eval" / "golden" / "clinic", today=date(2026, 10, 25))
    assert "questions" not in clinic, "no question records, no key -- the report stays what it was"


def test_the_architecture_description_lists_open_questions(example_root):
    text = (example_root / "docs" / "architecture-description.md").read_text(encoding="utf-8")
    assert "clarification questions" in text
    assert "It receives released orders from the ERP every few minutes." in text
    assert "How many orders a week" not in text, "an answered question is not an open one"


@pytest.fixture()
def clinic_sources(tmp_path):
    gold = REPO_ROOT / "eval" / "golden" / "clinic"
    shutil.copy(gold / "ea.config.yaml", tmp_path / "ea.config.yaml")
    shutil.copytree(gold / "facts" / "sources", tmp_path / "facts" / "sources")
    return tmp_path


def test_propose_from_coverage_writes_questions_that_validate(clinic_sources):
    report = propose.propose(clinic_sources, source="coverage", as_of=date(2026, 10, 25))
    assert report.written and report.proposals
    target = clinic_sources / "facts" / "questions" / "proposed-questions.yaml"
    assert report.target == target
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    source_text = (clinic_sources / "facts" / "sources").glob("*.md")
    original = "\n".join(path.read_text(encoding="utf-8") for path in source_text)
    for question in data["questions"]:
        assert question["question"].startswith(propose.PLACEHOLDER)
        assert question["status"] == "open"
        # The quote is the source's own text -- casing and all -- not the normalized form
        # the coverage report works in.
        assert " ".join(question["source"]["quote"].split()) in " ".join(original.split())
    findings = facts.validate_facts(clinic_sources).findings
    assert not [f for f in findings if f.code.startswith("QST")], [f.render() for f in findings]


def test_propose_from_coverage_rerun_proposes_nothing_new_and_says_so(clinic_sources):
    first = propose.propose(clinic_sources, source="coverage", as_of=date(2026, 10, 25))
    second = propose.propose(clinic_sources, source="coverage", as_of=date(2026, 10, 26))
    assert not second.proposals
    assert {s["id"] for s in second.skipped} == {p.id for p in first.proposals}
    assert all("facts/questions/" in s["reason"] for s in second.skipped)


def test_the_example_has_no_uncited_statement_to_ask_about(example_root):
    report = propose.propose(example_root, source="coverage", as_of=date(2026, 10, 25), dry_run=True)
    assert not report.proposals


# --------------------------------------------------------------------------- tables


def test_rtm_joins_bindings_evidence_realization_and_decisions(example_root):
    matrix = analyst.rtm(example_root)
    rows = {row.id: row for row in matrix.rows}
    retention = rows["req-po-retention"]
    assert retention.binds == ["app-erp-core", "data-order-record"]
    assert retention.facts == ["fact-po-retention"]
    assert len(retention.sources) == 2, "both sources the fact quotes"
    assert "decision-order-api-single-integration" in retention.decisions, "through app-erp-core"
    goal = rows["goal-shorten-lead-time"]
    assert goal.realized_by == ["cap-order-management"]
    assert set(goal.flags) == {"unbound", "assumed"}


def test_rtm_and_glossary_write_csv_a_spreadsheet_reads_back(example_root, tmp_path):
    analyst.write_table(tmp_path / "rtm.csv", "RTM", analyst.rtm_table(analyst.rtm(example_root)))
    rows = list(csv.reader(io.StringIO((tmp_path / "rtm.csv").read_text(encoding="utf-8"))))
    assert rows[0] == list(analyst.RTM_COLUMNS)
    assert len(rows) == 1 + len(analyst.rtm(example_root).rows)
    analyst.write_table(tmp_path / "glossary.md", "Glossary", analyst.glossary_table(analyst.glossary(example_root)))
    assert (tmp_path / "glossary.md").read_text(encoding="utf-8").startswith("# Glossary")


def test_glossary_answers_by_name_before_by_citation(example_root):
    entries = {entry.id: entry for entry in analyst.glossary(example_root).entries}
    assert entries["erp-core"].modelled_as == ["app-erp-core"]
    assert len(entries) == 11
    assert all(entries[e].facts for e in entries), "every example entity is mentioned by some fact"


def test_tables_are_byte_stable(example_root):
    assert analyst.rtm(example_root).as_dict() == analyst.rtm(example_root).as_dict()
    assert analyst.glossary(example_root).as_dict() == analyst.glossary(example_root).as_dict()
