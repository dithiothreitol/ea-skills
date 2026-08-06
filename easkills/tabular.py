"""Turn a tabular export (CSV, and therefore Excel) into a citable source document.

The most common EA input in the world is a spreadsheet: an application inventory, a
server list, a contract register. This repository's discipline is that every fact
carries a quote located mechanically in a source document -- and a spreadsheet is not
a document a quote can be located in. Pasting one into markdown by hand breaks the
verbatim chain at exactly the point it is supposed to hold.

So the conversion is done by code and *recorded*: the generated document carries the
original file's SHA-256, its delimiter and encoding, and the row and column counts. A
quote verified against the converted document is therefore traceable to the bytes it
came from, and re-running the conversion on the same input produces the same file --
which is what makes it safe to commit both and let CI notice if they diverge.

Nothing here interprets the data. Column names are not mapped to model fields, values
are not typed, and no element is created: this produces evidence, and `ea-intake`
turns evidence into facts under the usual quote verification. A tool that guessed
which column meant "owner" would be inventing exactly the claims this pipeline exists
to make checkable.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Delimiters worth trying, in the order a European Excel export makes likely. The
# `csv` sniffer alone is unreliable on one-column files and on quoted text containing
# commas, so the choice is made by counting consistent columns instead.
CANDIDATE_DELIMITERS = (",", ";", "\t", "|")


class TabularError(RuntimeError):
    pass


@dataclass
class TabularReport:
    source: str
    target: str
    sha256: str
    delimiter: str
    encoding: str
    columns: list[str] = field(default_factory=list)
    rows: int = 0
    ragged: list[dict[str, Any]] = field(default_factory=list)
    flattened: list[int] = field(default_factory=list)  # 1-based row numbers with newlines in a cell

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "sourceSha256": self.sha256,
            "target": self.target,
            "delimiter": "\\t" if self.delimiter == "\t" else self.delimiter,
            "encoding": self.encoding,
            "columns": self.columns,
            "rows": self.rows,
            "ragged": self.ragged,
            "flattened": self.flattened,
        }


def _decode(raw: bytes) -> tuple[str, str]:
    """(text, encoding). UTF-8 with BOM first: it is what Excel writes."""
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    # Last resort: never fail on an unreadable byte, but say what was done.
    return raw.decode("utf-8", errors="replace"), "utf-8 (with replacements)"


def _pick_delimiter(text: str) -> str:
    """The delimiter that yields the most columns *consistently* across the file.

    Sniffing by frequency alone picks the comma out of ``"Smith, J.";"Sales"`` and
    produces a table whose columns shift row by row -- a source document that reads as
    authoritative and is silently misaligned.
    """
    best = (1, ",")  # (columns, delimiter); a single column is the honest fallback
    for delimiter in CANDIDATE_DELIMITERS:
        try:
            rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
        except csv.Error:
            continue
        rows = [row for row in rows if row]
        if not rows:
            continue
        widths = {len(row) for row in rows}
        columns = len(rows[0])
        if columns > best[0] and len(widths) == 1:
            best = (columns, delimiter)
    if best[0] > 1:
        return best[1]
    # No delimiter divides the file evenly. Fall back to the one giving the widest
    # header, and let the ragged-row report say what did not line up.
    widest = max(
        CANDIDATE_DELIMITERS,
        key=lambda d: len(next(iter(csv.reader(io.StringIO(text), delimiter=d)), [])),
    )
    return widest


def _cell(value: str) -> str:
    """A cell as it will appear inside a markdown table row."""
    return value.replace("|", "\\|").replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()


def build_markdown(text: str, report: TabularReport) -> str:
    rows = [row for row in csv.reader(io.StringIO(text), delimiter=report.delimiter) if any(cell.strip() for cell in row)]
    if not rows:
        raise TabularError(f"{report.source} has no rows")
    header = [_cell(cell) or f"column{index + 1}" for index, cell in enumerate(rows[0])]
    declared = len(header)
    # A row wider than the header gets extra columns rather than a truncation: a converted
    # document is quoted from, and a cell dropped here is evidence that cannot be cited at
    # all. Short rows are padded, long rows widen the table, and either way the row number
    # is reported -- the reader is told the export was ragged, never quietly shown less
    # than it contained.
    widest = max([declared] + [len(row) for row in rows[1:]])
    header += [f"column{index + 1}" for index in range(declared, widest)]
    report.columns = header

    body: list[list[str]] = []
    for number, row in enumerate(rows[1:], start=2):
        if any("\n" in cell or "\r" in cell for cell in row):
            report.flattened.append(number)
        if len(row) != declared:
            report.ragged.append({"row": number, "cells": len(row), "expected": declared})
        cells = [_cell(cell) for cell in row]
        cells += [""] * (len(header) - len(cells))
        body.append(cells)
    report.rows = len(body)

    out: list[str] = [
        f"# {report.source}",
        "",
        "> Converted from a tabular export by `python -m easkills intake-csv`. Do not edit: "
        "re-run the conversion instead, so the quotes verified against this file stay "
        "traceable to the bytes they came from.",
        "",
        f"- **Source file:** `{report.source}`",
        f"- **SHA-256:** `{report.sha256}`",
        f"- **Read as:** {report.encoding}, delimiter "
        + ("`tab`" if report.delimiter == "\t" else f"`{report.delimiter}`"),
        f"- **Shape:** {report.rows} row(s), {len(header)} column(s)",
    ]
    if report.ragged:
        out.append(
            f"- **Ragged rows:** {', '.join(str(item['row']) for item in report.ragged)} "
            f"(cell count differs from the {declared} header column(s); short rows padded, "
            "extra cells kept under generated column names -- nothing dropped)"
        )
    if report.flattened:
        out.append(
            f"- **Cells containing line breaks:** row(s) "
            f"{', '.join(str(number) for number in report.flattened)} -- flattened to single "
            "lines so each row is one quotable line"
        )
    out += [
        "",
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]
    out += ["| " + " | ".join(row) + " |" for row in body]
    out.append("")
    return "\n".join(out)


def convert(source: Path, out: Path, overwrite: bool = False) -> TabularReport:
    if not source.is_file():
        raise TabularError(f"{source} does not exist")
    if out.exists() and not overwrite:
        raise TabularError(
            f"{out} already exists -- re-run with --overwrite once you have checked the diff, "
            "so a conversion never silently replaces evidence a fact may already cite"
        )
    raw = source.read_bytes()
    if not raw.strip():
        raise TabularError(f"{source.name} is empty")
    text, encoding = _decode(raw)
    report = TabularReport(
        source=source.name,
        target=str(out),
        sha256=hashlib.sha256(raw).hexdigest(),
        delimiter=_pick_delimiter(text),
        encoding=encoding,
    )
    markdown = build_markdown(text, report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8", newline="\n")
    return report
