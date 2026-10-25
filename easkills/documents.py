"""Turn a document export (PDF, DOCX, PPTX, XLSX) into a citable source document.

An analyst's material is rarely a markdown file. It is the PDF of a policy, the Word
document a business unit wrote, the slide deck from a steering committee, the workbook
with one inventory per sheet. Until this module, every one of them had to be converted by
hand before `ea-intake` could cite it -- and hand conversion breaks the verbatim chain at
the one point it exists to hold: nobody can tell a quote located in a hand-made copy from a
quote located in the original.

So the conversion is done by code and recorded, exactly as `intake-csv` does it for CSV:
the generated markdown carries the original file's SHA-256, the library and version that
read it, and the shape of what was read. Re-running the conversion on the same bytes with
the same library produces the same file. A library upgrade that reads a document
differently shows up as a diff whose header names the cause.

**Nothing here interprets anything.** No heading becomes an element, no table column
becomes a field, no slide title becomes a capability. The output is evidence; `ea-intake`
turns evidence into facts under the usual quote verification.

**What a converter cannot do is said, not hidden.** A PDF page with no text layer is a
scanned image; this module does no OCR, and the page is reported as unread rather than
silently omitted -- a source document that skipped a page reads as complete. A workbook
formula with no cached value is reported the same way.

The four libraries are an optional extras group (`requirements-intake.txt`), imported only
when a file of their kind is converted. The deterministic core stays at three runtime
dependencies, and a missing library is a refusal that names the install command.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Callable

REQUIREMENTS_FILE = "requirements-intake.txt"

# suffix -> (human kind, importable module, distribution name for the version)
SUPPORTED: dict[str, tuple[str, str, str]] = {
    ".pdf": ("PDF", "pypdf", "pypdf"),
    ".docx": ("Word document", "docx", "python-docx"),
    ".pptx": ("PowerPoint deck", "pptx", "python-pptx"),
    ".xlsx": ("Excel workbook", "openpyxl", "openpyxl"),
}


class DocumentError(RuntimeError):
    pass


@dataclass
class DocumentReport:
    source: str
    target: str
    sha256: str
    kind: str
    library: str
    sections: int = 0  # pages, slides, sheets -- or top-level blocks for a Word document
    lines: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "sourceSha256": self.sha256,
            "target": self.target,
            "kind": self.kind,
            "library": self.library,
            "sections": self.sections,
            "lines": self.lines,
            "notes": self.notes,
        }


def _cell(value: Any) -> str:
    """A value as it will appear inside a markdown table row (same escaping as intake-csv)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        text = "TRUE" if value else "FALSE"
    elif isinstance(value, float) and value.is_integer():
        text = str(int(value))
    elif isinstance(value, (datetime, date, time)):
        text = value.isoformat()
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()


def _table(rows: list[list[str]]) -> list[str]:
    """A markdown table from already-escaped cells; the first row is the header."""
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    header = [cell or f"column{index + 1}" for index, cell in enumerate(padded[0])]
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * width]
    out += ["| " + " | ".join(row) + " |" for row in padded[1:]]
    return out


def _clean(text: str) -> str:
    return " ".join(text.split())


def _import(module: str) -> Any:
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise DocumentError(
            f"reading this kind of file needs the optional intake libraries ({exc.name!r} is "
            f"missing). Install them with: python -m pip install -r {REQUIREMENTS_FILE}"
        ) from None


# --------------------------------------------------------------------------- readers


def _read_pdf(path: Path, report: DocumentReport) -> list[str]:
    pypdf = _import("pypdf")
    try:
        reader = pypdf.PdfReader(str(path))
        pages = list(reader.pages)
    except Exception as exc:  # noqa: BLE001 -- any parse failure is the same refusal
        raise DocumentError(f"{path.name} cannot be read as a PDF: {exc}") from None
    out: list[str] = []
    for number, page in enumerate(pages, start=1):
        out += [f"## Page {number}", ""]
        text = page.extract_text() or ""
        lines = [_clean(line) for line in text.splitlines()]
        lines = [line for line in lines if line]
        if not lines:
            report.notes.append(
                f"page {number} has no text layer (a scanned image?) and was not read -- this "
                "converter does no OCR"
            )
            out += ["*(no extractable text on this page)*", ""]
            continue
        out += lines + [""]
    report.sections = len(pages)
    return out


def _read_docx(path: Path, report: DocumentReport) -> list[str]:
    docx = _import("docx")
    from docx.table import Table  # noqa: PLC0415 -- imported only when converting a docx
    from docx.text.paragraph import Paragraph  # noqa: PLC0415

    try:
        document = docx.Document(str(path))
    except Exception as exc:  # noqa: BLE001
        raise DocumentError(f"{path.name} cannot be read as a Word document: {exc}") from None
    out: list[str] = []
    blocks = 0
    # Body order matters: a table sits between the paragraphs that talk about it, and a
    # reader quoting "the table below" needs it below. python-docx exposes paragraphs and
    # tables as separate lists, so the body is walked directly.
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(child, document)
            text = _clean(paragraph.text)
            if not text:
                continue
            style = (paragraph.style.name if paragraph.style is not None else "") or ""
            if style == "Title":
                out += [f"# {text}", ""]
            elif style.startswith("Heading"):
                level = style.removeprefix("Heading").strip()
                depth = int(level) if level.isdigit() else 1
                out += [f"{'#' * min(depth + 1, 6)} {text}", ""]
            elif style.startswith("List"):
                out.append(f"- {text}")
            else:
                if out and out[-1].startswith("- "):
                    out.append("")
                out += [text, ""]
            blocks += 1
        elif tag == "tbl":
            table = Table(child, document)
            rows = [[_cell(cell.text) for cell in row.cells] for row in table.rows]
            rows = [row for row in rows if any(row)]
            if rows:
                if out and out[-1]:
                    out.append("")
                out += _table(rows) + [""]
                blocks += 1
    report.sections = blocks
    return out


def _shape_lines(shape: Any) -> list[str]:
    """Text and tables of one slide shape, recursing into groups, in file order."""
    out: list[str] = []
    if getattr(shape, "shape_type", None) is not None and hasattr(shape, "shapes"):
        for inner in shape.shapes:  # a group shape
            out += _shape_lines(inner)
        return out
    if getattr(shape, "has_table", False) and shape.has_table:
        rows = [[_cell(cell.text) for cell in row.cells] for row in shape.table.rows]
        rows = [row for row in rows if any(row)]
        if rows:
            out += [""] + _table(rows) + [""]
        return out
    if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
        for paragraph in shape.text_frame.paragraphs:
            text = _clean("".join(run.text for run in paragraph.runs))
            if text:
                out.append(text)
    return out


def _read_pptx(path: Path, report: DocumentReport) -> list[str]:
    pptx = _import("pptx")
    try:
        deck = pptx.Presentation(str(path))
    except Exception as exc:  # noqa: BLE001
        raise DocumentError(f"{path.name} cannot be read as a PowerPoint deck: {exc}") from None
    out: list[str] = []
    slides = list(deck.slides)
    for number, slide in enumerate(slides, start=1):
        title_shape = slide.shapes.title
        title = ""
        if title_shape is not None and title_shape.has_text_frame:
            title = _clean(title_shape.text_frame.text)
        out += [f"## Slide {number}" + (f": {title}" if title else ""), ""]
        body: list[str] = []
        for shape in slide.shapes:
            if title_shape is not None and shape.shape_id == title_shape.shape_id:
                continue
            body += _shape_lines(shape)
        out += body + [""]
        frame = slide.notes_slide.notes_text_frame if slide.has_notes_slide else None
        notes = [_clean(p.text) for p in frame.paragraphs] if frame is not None else []
        notes = [line for line in notes if line]
        if notes:
            out += ["**Speaker notes:**", ""] + notes + [""]
    report.sections = len(slides)
    return out


def _read_xlsx(path: Path, report: DocumentReport) -> list[str]:
    openpyxl = _import("openpyxl")
    try:
        values = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        formulas = openpyxl.load_workbook(str(path), read_only=True, data_only=False)
    except Exception as exc:  # noqa: BLE001
        raise DocumentError(f"{path.name} cannot be read as an Excel workbook: {exc}") from None
    out: list[str] = []
    try:
        for sheet, formula_sheet in zip(values.worksheets, formulas.worksheets):
            rows = [list(row) for row in sheet.iter_rows(values_only=True)]
            formula_rows = [list(row) for row in formula_sheet.iter_rows(values_only=True)]
            uncached = sum(
                1
                for row, formula_row in zip(rows, formula_rows)
                for value, written in zip(row, formula_row)
                if value is None and isinstance(written, str) and written.startswith("=")
            )
            cells = [[_cell(value) for value in row] for row in rows]
            cells = [row for row in cells if any(row)]
            state = "" if sheet.sheet_state == "visible" else f" ({sheet.sheet_state})"
            out += [f"## Sheet: {sheet.title}{state}", ""]
            if not cells:
                out += ["*(empty sheet)*", ""]
                continue
            width = max(max((i + 1 for i, v in enumerate(row) if v), default=0) for row in cells)
            cells = [row[:width] for row in cells]
            out += _table(cells) + [""]
            if uncached:
                report.notes.append(
                    f"sheet '{sheet.title}': {uncached} formula cell(s) carry no cached value (the "
                    "workbook was never recalculated) and appear empty -- open and save it in a "
                    "spreadsheet program, then convert again"
                )
            if state:
                report.notes.append(f"sheet '{sheet.title}' is {sheet.sheet_state} in the workbook and is included")
        report.sections = len(values.worksheets)
    finally:
        values.close()
        formulas.close()
    return out


READERS: dict[str, Callable[[Path, DocumentReport], list[str]]] = {
    ".pdf": _read_pdf,
    ".docx": _read_docx,
    ".pptx": _read_pptx,
    ".xlsx": _read_xlsx,
}


def _library_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unknown version"


def convert(source: Path, out: Path, overwrite: bool = False) -> DocumentReport:
    if not source.is_file():
        raise DocumentError(f"{source} does not exist")
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED:
        supported = ", ".join(sorted(SUPPORTED))
        hint = " For CSV, use intake-csv." if suffix == ".csv" else ""
        raise DocumentError(f"{source.name}: unsupported kind '{suffix}' (supported: {supported}).{hint}")
    if out.exists() and not overwrite:
        raise DocumentError(
            f"{out} already exists -- re-run with --overwrite once you have checked the diff, "
            "so a conversion never silently replaces evidence a fact may already cite"
        )
    raw = source.read_bytes()
    if not raw:
        raise DocumentError(f"{source.name} is empty")
    kind, _module, distribution = SUPPORTED[suffix]
    report = DocumentReport(
        source=source.name,
        target=str(out),
        sha256=hashlib.sha256(raw).hexdigest(),
        kind=kind,
        library=f"{distribution} {_library_version(distribution)}",
    )
    body = READERS[suffix](source, report)
    while body and not body[-1]:
        body.pop()
    report.lines = sum(1 for line in body if line and not line.startswith("#"))
    if not report.lines:
        raise DocumentError(
            f"{source.name}: nothing readable was found -- " + ("; ".join(report.notes) or "the document is empty")
        )

    unit = {".pdf": "page(s)", ".pptx": "slide(s)", ".xlsx": "sheet(s)", ".docx": "block(s)"}[suffix]
    header = [
        f"# {report.source}",
        "",
        f"> Converted from a {kind} by `python -m easkills intake-doc`. Do not edit: re-run the "
        "conversion instead, so the quotes verified against this file stay traceable to the "
        "bytes they came from. Nothing was interpreted -- headings, tables and slide titles are "
        "reproduced, not turned into model content.",
        "",
        f"- **Source file:** `{report.source}`",
        f"- **SHA-256:** `{report.sha256}`",
        f"- **Read with:** {report.library}"
        + (" (text layer only -- no OCR)" if suffix == ".pdf" else ""),
        f"- **Shape:** {report.sections} {unit}, {report.lines} line(s) of text",
    ]
    header += [f"- **Note:** {note}" for note in report.notes]
    document = "\n".join(header + ["", ""] + body) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(document, encoding="utf-8", newline="\n")
    return report
