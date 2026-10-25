"""The DORA register as the ITS templates' columns: one CSV per template the model can feed.

`dora-register --format its-csv --out <dir>` writes the register the way the reporting
templates of Commission Implementing Regulation (EU) 2024/2956 lay it out -- one CSV per
template, one column per template field, headed by its column code and name -- so whoever
prepares the filing starts from what the architecture already knows instead of from a
blank workbook.

**It is a pre-filled worksheet, not a submission**, and three things make that more than a
disclaimer:

* Only the fields the model actually carries are filled. Every other column of each
  template is present and empty, and `README.md` beside the CSVs names them, template by
  template -- the register's gap section, at the grain the templates use.
* Values are in this repository's vocabulary (`critical`, an element id), not the ITS code
  lists or the reporting taxonomy. Mapping them is the filing tool's job, and doing it here
  would be guessing at codes nothing in this repository verifies.
* The column codes and names were taken from a rendering of Annex I (springlex.eu), because
  EUR-Lex refused automated retrieval on the day this was written (2026-10-25). They are to
  be checked against the Official Journal text before a code is relied on, and the README
  says so in every export.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from . import dora

SOURCE_NOTE = (
    "Template and column identifiers from Annex I of Commission Implementing Regulation (EU) "
    "2024/2956, as rendered at springlex.eu: EUR-Lex refused automated retrieval on 2026-10-25. "
    "Check every code against the Official Journal text before relying on it."
)

# (code, name) per template, in the Annex's order. Only templates the model can feed at
# least one column of are exported; the others are named in the README as not exported.
COLUMNS: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {
    "B_02.01": (
        "Contractual arrangements – general information",
        (
            ("B_02.01.0010", "Contractual arrangement reference number"),
            ("B_02.01.0020", "Type of contractual arrangement"),
            ("B_02.01.0030", "Overarching contractual arrangement reference number"),
            ("B_02.01.0040", "Currency of the amount reported in B_02.01.0050"),
            ("B_02.01.0050", "Annual expense or estimated cost of the contractual arrangement for the past year"),
        ),
    ),
    "B_02.02": (
        "Contractual arrangements – specific information",
        (
            ("B_02.02.0010", "Contractual arrangement reference number"),
            ("B_02.02.0020", "LEI of the financial entity making use of the ICT service(s)"),
            ("B_02.02.0030", "Identification code of the ICT third-party service provider"),
            ("B_02.02.0040", "Type of code to identify the ICT third-party service provider"),
            ("B_02.02.0050", "Function identifier"),
            ("B_02.02.0060", "Type of ICT services"),
            ("B_02.02.0070", "Start date of the contractual arrangement"),
            ("B_02.02.0080", "End date of the contractual arrangement"),
            ("B_02.02.0090", "Reason of the termination or ending of the contractual arrangement"),
            ("B_02.02.0100", "Notice period for the financial entity making use of the ICT service(s)"),
            ("B_02.02.0110", "Notice period for the ICT third-party service provider"),
            ("B_02.02.0120", "Country of the governing law of the contractual arrangement"),
            ("B_02.02.0130", "Country of provision of the ICT services"),
            ("B_02.02.0140", "Storage of data"),
            ("B_02.02.0150", "Location of the data at rest (storage)"),
            ("B_02.02.0160", "Location of management of the data (processing)"),
            ("B_02.02.0170", "Sensitiveness of the data stored by the ICT third-party service provider"),
            ("B_02.02.0180", "Level of reliance on the ICT service supporting the critical or important function."),
        ),
    ),
    "B_05.01": (
        "ICT third-party service providers",
        (
            ("B_05.01.0010", "Identification code of ICT third-party service provider"),
            ("B_05.01.0020", "Type of code to identify the ICT third-party service provider"),
            ("B_05.01.0030", "Additional identification code of ICT third-party service provider"),
            ("B_05.01.0040", "Type of additional identification code to identify the ICT third-party service provider"),
            ("B_05.01.0050", "Legal name of the ICT third-party service provider"),
            ("B_05.01.0060", "Name of the ICT third-party service provider in Latin alphabet"),
            ("B_05.01.0070", "Type of person of the ICT third-party service provider"),
            ("B_05.01.0080", "Country of the ICT third-party service provider’s headquarters"),
            ("B_05.01.0090", "Currency of the amount reported in B_05.01.0100"),
            ("B_05.01.0100", "Total annual expense or estimated cost of the ICT third-party service provider"),
            ("B_05.01.0110", "Identification code of the ICT third-party service provider’s ultimate parent undertaking"),
            ("B_05.01.0120", "Type of code to identify the ICT third-party service provider’s ultimate parent undertaking"),
        ),
    ),
    "B_06.01": (
        "Functions identification",
        (
            ("B_06.01.0010", "Function Identifier"),
            ("B_06.01.0020", "Licenced activity"),
            ("B_06.01.0030", "Function name"),
            ("B_06.01.0040", "LEI of the financial entity"),
            ("B_06.01.0050", "Criticality or importance assessment"),
            ("B_06.01.0060", "Reasons for criticality or importance"),
            ("B_06.01.0070", "Date of the last assessment of criticality or importance"),
            ("B_06.01.0080", "Recovery time objective of the function"),
            ("B_06.01.0090", "Recovery point objective of the function"),
            ("B_06.01.0100", "Impact of discontinuing the function"),
        ),
    ),
}

NOT_EXPORTED = {
    "B_01.01": "Entity maintaining the register of information",
    "B_01.02": "List of entities within the scope of consolidation",
    "B_01.03": "List of branches",
    "B_02.03": "List of intra-group contractual arrangements",
    "B_03.01": "Entities signing the contractual arrangements for receiving ICT service(s)",
    "B_03.02": "ICT third-party service providers signing the contractual arrangements",
    "B_03.03": "Entities signing the contractual arrangements for providing ICT service(s) to other entities",
    "B_04.01": "Entities making use of the ICT services",
    "B_05.02": "ICT service supply chain",
    "B_07.01": "Assessments of the ICT services",
}


def _rows(register: dora.Register, leis: dict[str, str]) -> dict[str, list[dict[str, str]]]:
    """Template -> rows keyed by column code; only the codes the model can fill appear."""
    rows: dict[str, list[dict[str, str]]] = {code: [] for code in COLUMNS}
    for contract in register.contracts:
        rows["B_02.01"].append({"B_02.01.0010": contract["contractRef"]})
    for entry in register.entries:
        if not entry.contract:
            continue
        lei = leis.get(entry.id, "")
        for function in entry.functions or [""]:
            row = {"B_02.02.0010": entry.contract, "B_02.02.0050": function}
            if lei:
                row |= {"B_02.02.0030": lei, "B_02.02.0040": "LEI"}
            rows["B_02.02"].append(row)
    for provider in register.providers:
        codes = sorted({leis[e] for e in provider["elements"] if leis.get(e)})
        row = {"B_05.01.0050": provider["provider"]}
        if len(codes) == 1:  # two LEIs for one provider name is a conflict, not a choice
            row |= {"B_05.01.0010": codes[0], "B_05.01.0020": "LEI"}
        rows["B_05.01"].append(row)
    for function in register.functions:
        rows["B_06.01"].append(
            {
                "B_06.01.0010": function["id"],
                "B_06.01.0030": function["name"],
                "B_06.01.0050": function["criticality"],
            }
        )
    for template in rows:
        rows[template] = sorted({tuple(sorted(r.items())): r for r in rows[template]}.values(), key=lambda r: sorted(r.items()))
    return rows


def _csv(template: str, rows: list[dict[str, str]]) -> str:
    _title, columns = COLUMNS[template]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([f"{code} {name}" for code, name in columns])
    for row in rows:
        writer.writerow([row.get(code, "") for code, _name in columns])
    return buffer.getvalue()


def export(register: dora.Register, out_dir: Path, leis: dict[str, str]) -> list[Path]:
    """Write one CSV per template plus README.md; return the paths written."""
    if not register.in_scope:
        raise dora.DoraError(
            f"no element carries '{dora.SCOPE_PROPERTY}: {dora.SCOPE_DORA}' -- nothing to export, and an "
            "empty set of templates is a filing-shaped artefact that says nothing"
        )
    rows = _rows(register, leis)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    filled: dict[str, set[str]] = {t: {code for row in rows[t] for code, value in row.items() if value} for t in rows}
    for template in COLUMNS:
        path = out_dir / f"{template}.csv"
        path.write_text(_csv(template, rows[template]), encoding="utf-8", newline="\n")
        written.append(path)

    lines = [
        "# DORA Register of Information -- ITS template worksheets",
        "",
        f"*Generated by `ea-skills` from the approved model, as of {register.as_of}.*",
        "",
        dora.HEADER_NOTICE,
        "",
        "**These CSVs are pre-filled worksheets, not a submission.** Each has one column per "
        "template field, headed by its code and name. Only the fields the model carries are "
        "filled; values are in this repository's vocabulary (`critical`, element ids), not the "
        "ITS code lists or the reporting taxonomy.",
        "",
        f"*{SOURCE_NOTE}*",
        "",
        "## Exported templates, and the columns the model could not fill",
        "",
    ]
    for template, (title, columns) in COLUMNS.items():
        empty = [f"{code} {name}" for code, name in columns if code not in filled[template]]
        lines.append(f"### {template} {title} -- `{template}.csv`, {len(rows[template])} row(s)")
        lines.append("")
        lines.append("Filled from the model: " + (", ".join(sorted(filled[template])) or "nothing"))
        lines.append("")
        lines.append("Left empty -- the model does not carry them:")
        lines.append("")
        lines += [f"- {item}" for item in empty]
        lines.append("")
    lines += ["## Templates not exported -- nothing in the model feeds them", ""]
    lines += [f"- {code} {title}" for code, title in NOT_EXPORTED.items()]
    readme = out_dir / "README.md"
    readme.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    written.append(readme)
    return written


def provider_leis(root: Path) -> dict[str, str]:
    """element id -> providerLei, for the in-scope elements that record one."""
    from . import dsl

    model, _documents, _config = dsl.load(root, "approved")
    return {e.id: e.properties["providerLei"] for e in model.elements.values() if e.properties.get("providerLei")}
