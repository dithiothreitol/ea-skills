"""The analyst's two derived tables: requirement traceability and the glossary.

Neither holds anything new. Every row of the traceability matrix is already recorded --
`appliesTo` says what a requirement binds, `provenance` says what evidences it, a
`Realization` says what meets it, a decision or assessment names the elements it is about
-- and every glossary row is the entity table plus where each entity turns up. What was
missing was the *join*, which an analyst used to do by hand in a spreadsheet that went stale
the day it was finished. Derived here, it is as current as the model and costs nothing.

Both are reports: nothing in them is a finding and neither gates. The flags a row carries
(`unbound`, `unrealized`, `assumed`) are facts about the row, stated so a reader sees the gap
without having to notice an empty cell.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import dsl, facts as facts_mod, govern, ui
from .validate import _normalize

# Motivation elements AD-09 lets bind architecture through `appliesTo`, in reading order.
TRACED_TYPES = ("Requirement", "Constraint", "Principle", "Goal")


@dataclass
class TraceRow:
    id: str
    type: str
    name: str
    binds: list[str] = field(default_factory=list)
    realized_by: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    assumed: bool = False
    decisions: list[str] = field(default_factory=list)
    assessments: list[str] = field(default_factory=list)

    @property
    def flags(self) -> list[str]:
        flags = []
        if not self.binds:
            flags.append("unbound")
        if not self.realized_by:
            flags.append("unrealized")
        if self.assumed:
            flags.append("assumed")
        return flags

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "binds": self.binds,
            "realizedBy": self.realized_by,
            "facts": self.facts,
            "sources": self.sources,
            "assumed": self.assumed,
            "decisions": self.decisions,
            "assessments": self.assessments,
            "flags": self.flags,
        }


@dataclass
class TraceMatrix:
    root: Path
    zone: str
    rows: list[TraceRow] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "zone": self.zone,
            "rows": [row.as_dict() for row in self.rows],
            "flagged": {
                flag: sorted(row.id for row in self.rows if flag in row.flags)
                for flag in ("unbound", "unrealized", "assumed")
            },
        }


def rtm(root: Path, zone: str = "approved") -> TraceMatrix:
    """Requirement -> what it binds, what meets it, what evidences it, what decided it."""
    model, _documents, _config = dsl.load_zone(root, zone)
    register, _rdocs, _edoc = facts_mod.load(root)
    governance = govern.load(root)

    realized_by: dict[str, set[str]] = {}
    for relationship in model.relationships.values():
        if relationship.type == "Realization" and relationship.source in model.elements:
            realized_by.setdefault(relationship.target, set()).add(relationship.source)

    matrix = TraceMatrix(root=root, zone=zone)
    order = {kind: index for index, kind in enumerate(TRACED_TYPES)}
    traced = sorted(
        (e for e in model.elements.values() if e.type in order), key=lambda e: (order[e.type], e.id)
    )
    for element in traced:
        row = TraceRow(id=element.id, type=element.type, name=element.name, assumed=element.assumed)
        row.binds = sorted(element.applies_to)
        row.realized_by = sorted(realized_by.get(element.id, set()))
        sources: set[str] = set()
        for provenance in element.provenance:
            if provenance.fact:
                row.facts.append(provenance.fact)
                fact = register.facts.get(provenance.fact)
                for evidence in fact.provenance if fact else []:
                    sources.add(evidence.file)
            elif provenance.file:
                sources.add(provenance.file)
        row.facts = sorted(set(row.facts))
        row.sources = sorted(sources)
        about = {element.id, *element.applies_to}
        row.decisions = sorted(d.id for d in governance.decisions.values() if about & set(d.related_elements))
        row.assessments = sorted(a.id for a in governance.assessments.values() if about & set(a.related_elements))
        matrix.rows.append(row)
    return matrix


def render_rtm(matrix: TraceMatrix) -> str:
    lines = [
        ui.bold(f"Requirement traceability -- zone '{matrix.zone}' at {matrix.root}"),
        ui.dim(f"{len(matrix.rows)} traced element(s): {', '.join(TRACED_TYPES)}"),
        "",
    ]
    if not matrix.rows:
        lines.append(ui.dim("Nothing to trace: the model holds no requirement, constraint, principle or goal."))
        return "\n".join(lines)

    def listed(items: list[str]) -> str:
        return ", ".join(items) if items else ui.dim("none")

    for row in matrix.rows:
        flags = "  " + ui.yellow(" ".join(f"[{flag}]" for flag in row.flags)) if row.flags else ""
        lines.append(f"  {ui.bold(row.id)}  {ui.cyan(row.type)}  {row.name}{flags}")
        lines.append(f"      binds        {listed(row.binds)}")
        lines.append(f"      realized by  {listed(row.realized_by)}")
        if row.facts or row.sources:
            evidence = listed(row.facts) + (f" {ui.dim('->')} {', '.join(row.sources)}" if row.sources else "")
        else:
            evidence = ui.yellow("assumed -- no evidence") if row.assumed else ui.dim("none")
        lines.append(f"      evidence     {evidence}")
        lines.append(f"      decisions    {listed(row.decisions)}")
        lines.append(f"      assessments  {listed(row.assessments)}")
    lines += [
        "",
        ui.dim(
            "Derived from appliesTo, Realization edges, provenance and the governance log -- "
            "edit those, never this table. A flag is a fact about the row, not a finding."
        ),
    ]
    return "\n".join(lines)


RTM_COLUMNS = ("id", "type", "name", "binds", "realizedBy", "facts", "sources", "decisions", "assessments", "flags")


def rtm_table(matrix: TraceMatrix) -> list[list[str]]:
    rows = [list(RTM_COLUMNS)]
    for row in matrix.rows:
        data = row.as_dict()
        rows.append([data[c] if isinstance(data[c], str) else "; ".join(data[c]) for c in RTM_COLUMNS])
    return rows


# --------------------------------------------------------------------------- glossary


@dataclass
class GlossaryEntry:
    id: str
    name: str
    kind: str
    aliases: list[str] = field(default_factory=list)
    documentation: str = ""
    facts: list[str] = field(default_factory=list)
    modelled_as: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "aliases": self.aliases,
            "documentation": self.documentation,
            "facts": self.facts,
            "modelledAs": self.modelled_as,
        }


@dataclass
class Glossary:
    root: Path
    entries: list[GlossaryEntry] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "entries": [entry.as_dict() for entry in self.entries],
            "unmodelled": sorted(entry.id for entry in self.entries if not entry.modelled_as),
        }


def glossary(root: Path) -> Glossary:
    """The entity table, with the facts that mention each entity and the model elements
    that answer to it -- by name or alias, or by citing a fact that mentions it."""
    register, _documents, _entities = facts_mod.load(root)
    model, _mdocs, _config = dsl.load(root, "approved")

    by_term: dict[str, set[str]] = {}
    for element in model.elements.values():
        by_term.setdefault(_normalize(element.name), set()).add(element.id)
    cites: dict[str, set[str]] = {}  # fact id -> elements citing it
    for concept in list(model.elements.values()):
        for provenance in concept.provenance:
            if provenance.fact:
                cites.setdefault(provenance.fact, set()).add(concept.id)

    result = Glossary(root=root)
    for entity in sorted(register.entities.values(), key=lambda e: (e.name.casefold(), e.id)):
        facts = sorted(f.id for f in register.facts.values() if entity.id in f.entities)
        named = set()
        for term in [entity.name, *entity.aliases]:
            named |= by_term.get(_normalize(term), set())
        cited = {element for fact_id in facts for element in cites.get(fact_id, set())}
        # Citing a fact that mentions the entity is weaker evidence than carrying its name,
        # so it only counts when no element answers by name -- otherwise one fact mentioning
        # three systems would list all three under each of them.
        modelled = sorted(named) if named else sorted(cited)
        result.entries.append(
            GlossaryEntry(
                id=entity.id,
                name=entity.name,
                kind=entity.kind,
                aliases=sorted(entity.aliases),
                documentation=entity.documentation,
                facts=facts,
                modelled_as=modelled,
            )
        )
    return result


def render_glossary(data: Glossary) -> str:
    lines = [ui.bold(f"Glossary at {data.root}"), ui.dim(f"{len(data.entries)} term(s)"), ""]
    if not data.entries:
        lines.append(ui.dim("No entities: the glossary is the entity table, and facts/entities.yaml is empty."))
        return "\n".join(lines)
    for entry in data.entries:
        kind = f" ({entry.kind})" if entry.kind else ""
        lines.append(f"  {ui.bold(entry.name)}{ui.dim(kind)}")
        if entry.aliases:
            lines.append(f"      also called  {', '.join(entry.aliases)}")
        if entry.documentation:
            lines.append(f"      {entry.documentation.strip()}")
        lines.append(f"      facts        {', '.join(entry.facts) or ui.dim('none')}")
        lines.append(
            f"      modelled as  {', '.join(entry.modelled_as) or ui.yellow('no element carries this name or cites its facts')}"
        )
    return "\n".join(lines)


GLOSSARY_COLUMNS = ("name", "kind", "aliases", "documentation", "facts", "modelledAs")


def glossary_table(data: Glossary) -> list[list[str]]:
    rows = [list(GLOSSARY_COLUMNS)]
    for entry in data.entries:
        values = entry.as_dict()
        rows.append(
            [values[c] if isinstance(values[c], str) else "; ".join(values[c]) for c in GLOSSARY_COLUMNS]
        )
    return rows


# ------------------------------------------------------------------------------ output


def as_csv(rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue()


def as_markdown(title: str, rows: list[list[str]]) -> str:
    def cell(value: str) -> str:
        return " ".join(value.split()).replace("|", "\\|")

    out = [f"# {title}", "", "| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])]
    out += ["| " + " | ".join(cell(value) for value in row) + " |" for row in rows[1:]]
    return "\n".join(out) + "\n"


def write_table(path: Path, title: str, rows: list[list[str]]) -> None:
    """CSV for a `.csv` target (a spreadsheet is where analysts read these), else markdown."""
    text = as_csv(rows) if path.suffix.lower() == ".csv" else as_markdown(title, rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
