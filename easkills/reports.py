"""Maintenance reports over the approved model and governance log.

All deterministic given the model state and an ``--as-of`` date; none of them gate by
default -- they exist to make rot *visible* (staleness, debt, KPI trends) and to make
the ISO 42010 conformance claim checkable rather than asserted. The delta report is
the mechanical half of continuous ingestion: what the fact register knows that the
model does not, and which evidence nothing uses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from . import dsl, facts as facts_mod, govern
from .validate import _normalize

# ------------------------------------------------------------------------- staleness


def staleness(root: Path, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    model, _documents, config = dsl.load(root, "approved")
    threshold = int(config.get("stalenessDays", 365))
    rows: list[dict[str, Any]] = []
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        if not element.last_reviewed:
            rows.append({"id": element.id, "owner": element.owner, "reviewed": None, "age": None, "state": "unreviewed"})
            continue
        try:
            reviewed = datetime.strptime(element.last_reviewed, "%Y-%m-%d").date()
        except ValueError:
            rows.append({"id": element.id, "owner": element.owner, "reviewed": element.last_reviewed, "age": None, "state": "invalid-date"})
            continue
        age = (today - reviewed).days
        rows.append(
            {
                "id": element.id,
                "owner": element.owner,
                "reviewed": element.last_reviewed,
                "age": age,
                "state": "stale" if age > threshold else "fresh",
            }
        )
    states = [r["state"] for r in rows]
    return {
        "asOf": today.isoformat(),
        "thresholdDays": threshold,
        "elements": len(rows),
        "fresh": states.count("fresh"),
        "stale": states.count("stale"),
        "unreviewed": states.count("unreviewed") + states.count("invalid-date"),
        "rows": rows,
    }


def render_staleness(data: dict[str, Any]) -> str:
    lines = [
        f"Staleness as of {data['asOf']} (threshold {data['thresholdDays']} days)",
        f"{data['elements']} elements: {data['fresh']} fresh, {data['stale']} stale, "
        f"{data['unreviewed']} unreviewed",
        "",
    ]
    flagged = [r for r in data["rows"] if r["state"] != "fresh"]
    for row in sorted(flagged, key=lambda r: (-(r["age"] or 10**6), r["id"])):
        age = f"{row['age']} days" if row["age"] is not None else "never reviewed"
        lines.append(f"  {row['state']:<11} {row['id']:<40} {age:<16} owner: {row['owner'] or '-'}")
    if not flagged:
        lines.append("  Nothing stale.")
    return "\n".join(lines)


# ------------------------------------------------------------------------------- KPI


def kpi(root: Path, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    model, _documents, config = dsl.load(root, "approved")
    register, _rdocs, _edoc = facts_mod.load(root)
    governance = govern.load(root)
    stale = staleness(root, today)

    concepts = list(model.elements.values()) + list(model.relationships.values())
    evidenced = sum(1 for c in concepts if c.provenance)
    assumed = sum(1 for c in concepts if c.assumed)
    owned = sum(1 for e in model.elements.values() if e.owner)

    applications = [e for e in model.elements.values() if e.type == "ApplicationComponent"]
    with_time = sum(1 for a in applications if a.properties.get("timeDisposition"))
    capabilities = [e for e in model.elements.values() if e.type == "Capability"]
    realized = {
        r.target
        for r in model.relationships.values()
        if r.type == "Realization" and r.target in model.elements
    }
    unsupported = [c.id for c in capabilities if c.id not in realized]

    connected: set[str] = set()
    for relationship in model.relationships.values():
        connected.update((relationship.source, relationship.target))
    for element in model.elements.values():
        if element.applies_to:
            connected.add(element.id)
            connected.update(element.applies_to)
    orphans = [e.id for e in model.elements.values() if e.id not in connected]

    dead_standards = {s.id for s in governance.standards.values() if s.lifecycle in {"deprecated", "retired"}}
    exposed = sorted(
        e.id for e in model.elements.values() if any(s in dead_standards for s in e.standards)
    )
    held = {ref for s in model.stakeholders.values() for ref in s.concerns}
    framed = {ref for v in model.views.values() for ref in v.concerns}

    def pct(part: int, whole: int) -> float:
        return round(part / whole, 4) if whole else 1.0

    return {
        "asOf": today.isoformat(),
        "size": {
            "elements": len(model.elements),
            "relationships": len(model.relationships),
            "views": len(model.views),
            "facts": len(register.facts),
            "entities": len(register.entities),
        },
        "evidence": {
            "evidencedShare": pct(evidenced, len(concepts)),
            "assumed": assumed,
        },
        "governance": {
            "ownedShare": pct(owned, len(model.elements)),
            "staleShare": pct(stale["stale"] + stale["unreviewed"], stale["elements"]),
            "openDispensations": sum(1 for d in governance.dispensations.values() if d.is_open(today)),
            "decisions": len(governance.decisions),
            "assessments": len(governance.assessments),
        },
        "portfolio": {
            "applications": len(applications),
            "timeClassifiedShare": pct(with_time, len(applications)),
            "obsolescenceExposure": exposed,
        },
        "capabilities": {
            "total": len(capabilities),
            "unsupported": unsupported,
            "applicationsPerCapability": pct(len(applications), len(capabilities)) if capabilities else None,
        },
        "quality": {
            "orphans": orphans,
        },
        "documentation": {
            "concerns": len(model.concerns),
            "unheldConcerns": sorted(set(model.concerns) - held),
            "unframedConcerns": sorted(set(model.concerns) - framed),
        },
    }


def render_kpi(data: dict[str, Any]) -> str:
    size, ev, gov, port, cap, qual, doc = (
        data["size"], data["evidence"], data["governance"], data["portfolio"],
        data["capabilities"], data["quality"], data["documentation"],
    )

    def share(value: float) -> str:
        return f"{value:.0%}"

    lines = [
        f"EA KPIs as of {data['asOf']}",
        "",
        f"Size          {size['elements']} elements, {size['relationships']} relationships, "
        f"{size['views']} views; {size['facts']} facts, {size['entities']} entities",
        f"Evidence      {share(ev['evidencedShare'])} concepts evidenced; {ev['assumed']} declared assumption(s)",
        f"Governance    {share(gov['ownedShare'])} owned; {share(gov['staleShare'])} stale/unreviewed; "
        f"{gov['openDispensations']} open dispensation(s); {gov['decisions']} decision(s); "
        f"{gov['assessments']} assessment(s)",
        f"Portfolio     {port['applications']} application(s); {share(port['timeClassifiedShare'])} TIME-classified; "
        f"obsolescence exposure: {', '.join(port['obsolescenceExposure']) or 'none'}",
        f"Capabilities  {cap['total']}; unsupported: {', '.join(cap['unsupported']) or 'none'}",
        f"Quality       orphans: {', '.join(qual['orphans']) or 'none'}",
        f"Documentation {doc['concerns']} concern(s); unheld: {', '.join(doc['unheldConcerns']) or 'none'}; "
        f"unframed: {', '.join(doc['unframedConcerns']) or 'none'}",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------------------ debt


HUB_DEGREE = 10


def debt(root: Path, today: date | None = None) -> dict[str, Any]:
    """The EA-debt register: deterministic graph queries from the smells catalogue."""
    today = today or date.today()
    model, _documents, config = dsl.load(root, "approved")
    governance = govern.load(root)
    items: list[dict[str, str]] = []

    def add(kind: str, concept: str, detail: str) -> None:
        items.append({"kind": kind, "concept": concept, "detail": detail})

    connected: dict[str, int] = {}
    for relationship in model.relationships.values():
        for end in (relationship.source, relationship.target):
            connected[end] = connected.get(end, 0) + 1
    bound: set[str] = set()
    for element in model.elements.values():
        if element.applies_to:
            bound.add(element.id)
            bound.update(element.applies_to)

    for element in sorted(model.elements.values(), key=lambda e: e.id):
        if element.id not in connected and element.id not in bound:
            add("isolated-element", element.id, f"{element.type} '{element.name}' has no relationships")
        if connected.get(element.id, 0) >= HUB_DEGREE:
            add(
                "hub-element",
                element.id,
                f"{element.type} '{element.name}' has degree {connected[element.id]} -- "
                "a change here fans out everywhere",
            )

    realized = {
        r.target for r in model.relationships.values() if r.type == "Realization" and r.target in model.elements
    }
    for capability in sorted(model.elements.values(), key=lambda e: e.id):
        if capability.type == "Capability" and capability.id not in realized:
            add("unsupported-capability", capability.id, f"nothing realizes '{capability.name}'")

    seen_names: dict[tuple[str, str], str] = {}
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        key = (element.type, element.name.casefold())
        if key in seen_names:
            add("duplicate-name", element.id, f"same name as '{seen_names[key]}' ({element.type} '{element.name}')")
        else:
            seen_names[key] = element.id

    stale_data = staleness(root, today)
    for row in stale_data["rows"]:
        if row["state"] in {"stale", "unreviewed"}:
            add("stale-content", row["id"], f"state: {row['state']}, last reviewed {row['reviewed'] or 'never'}")

    dead = {s.id: s.lifecycle for s in governance.standards.values() if s.lifecycle in {"deprecated", "retired"}}
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        for ref in element.standards:
            if ref in dead:
                covered = governance.covering(element.id, ref, today)
                note = f" (dispensation '{covered.id}' until {covered.expires})" if covered else ""
                add("dead-standard-reference", element.id, f"references {dead[ref]} standard '{ref}'{note}")

    return {"asOf": today.isoformat(), "items": items, "total": len(items)}


def render_debt(data: dict[str, Any]) -> str:
    lines = [f"EA debt register as of {data['asOf']} -- {data['total']} item(s)", ""]
    by_kind: dict[str, list[dict[str, str]]] = {}
    for item in data["items"]:
        by_kind.setdefault(item["kind"], []).append(item)
    for kind in sorted(by_kind):
        lines.append(f"{kind} ({len(by_kind[kind])}):")
        for item in by_kind[kind]:
            lines.append(f"  {item['concept']:<40} {item['detail']}")
        lines.append("")
    if not data["items"]:
        lines.append("No debt items found.")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------- ISO 42010 clause 6


def conformance(root: Path, today: date | None = None) -> dict[str, Any]:
    """The checkable subset of ISO/IEC/IEEE 42010:2022 Clause 6, honestly labelled:
    ``pass``/``fail`` where a check exists, ``gap`` where this tooling does not
    implement the clause yet -- silence is never presented as conformance."""
    model, _documents, _config = dsl.load(root, "approved")
    governance = govern.load(root)
    held = {ref for s in model.stakeholders.values() for ref in s.concerns}
    framed = {ref for v in model.views.values() for ref in v.concerns}
    assumed = [c for c in list(model.elements.values()) + list(model.relationships.values()) if c.assumed]

    def item(clause: str, requirement: str, status: str, detail: str) -> dict[str, str]:
        return {"clause": clause, "requirement": requirement, "status": status, "detail": detail}

    items = [
        item(
            "6.2",
            "AD identifies the architecture and system of interest",
            "pass" if model.name and model.documentation else "fail",
            f"name: {model.name!r}; documentation {'present' if model.documentation else 'MISSING'}",
        ),
        item(
            "6.3",
            "Stakeholders identified",
            "pass" if model.stakeholders else "fail",
            f"{len(model.stakeholders)} stakeholder(s)",
        ),
        item(
            "6.4",
            "Concerns identified and each held by a stakeholder",
            "pass" if model.concerns and set(model.concerns) <= held else "fail",
            f"{len(model.concerns)} concern(s); unheld: {', '.join(sorted(set(model.concerns) - held)) or 'none'}",
        ),
        item(
            "6.5",
            "Each view governed by a viewpoint",
            "pass" if model.views and all(v.viewpoint for v in model.views.values()) else "fail",
            f"views without a viewpoint: {', '.join(sorted(v.id for v in model.views.values() if not v.viewpoint)) or 'none'}",
        ),
        item(
            "6.6",
            "Each concern framed by at least one view",
            "pass" if model.concerns and set(model.concerns) <= framed else "fail",
            f"unframed: {', '.join(sorted(set(model.concerns) - framed)) or 'none'}",
        ),
        item(
            "6.8",
            "Known inconsistencies and gaps recorded",
            "pass",
            f"{len(assumed)} declared assumption(s) surfaced in the architecture description",
        ),
        item(
            "6.9",
            "Correspondences between AD elements",
            "gap",
            "not implemented by this tooling yet -- do not claim conformance on this clause",
        ),
        item(
            "6.10",
            "Architecture decisions recorded with rationale",
            "pass" if governance.decisions else "fail",
            f"{len(governance.decisions)} decision record(s); rationale is schema-mandatory",
        ),
    ]
    return {
        "items": items,
        "passed": sum(1 for i in items if i["status"] == "pass"),
        "failed": sum(1 for i in items if i["status"] == "fail"),
        "gaps": sum(1 for i in items if i["status"] == "gap"),
    }


def render_conformance(data: dict[str, Any]) -> str:
    lines = ["ISO/IEC/IEEE 42010:2022 Clause 6 conformance (checkable subset)", ""]
    for item in data["items"]:
        lines.append(f"  {item['status'].upper():<5} {item['clause']:<5} {item['requirement']}")
        lines.append(f"        {item['detail']}")
    lines += [
        "",
        f"{data['passed']} pass, {data['failed']} fail, {data['gaps']} gap(s) -- a 'gap' is a clause "
        "this tooling does not check; it is not silent conformance",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------------------ delta


def delta(root: Path) -> dict[str, Any]:
    """What the fact register knows that the approved model does not (and vice versa):
    the mechanical input for continuous ingestion."""
    model, _documents, _config = dsl.load(root, "approved")
    register, _rdocs, _edoc = facts_mod.load(root)

    cited_facts: set[str] = set()
    for concept in list(model.elements.values()) + list(model.relationships.values()):
        for provenance in concept.provenance:
            if provenance.fact:
                cited_facts.add(provenance.fact)

    element_terms = {_normalize(e.name) for e in model.elements.values()}
    entities_via_facts: set[str] = set()
    for fact_id in cited_facts:
        fact = register.facts.get(fact_id)
        if fact:
            entities_via_facts.update(fact.entities)

    unmodelled: list[dict[str, str]] = []
    for entity in sorted(register.entities.values(), key=lambda e: e.id):
        terms = {_normalize(entity.name)} | {_normalize(a) for a in entity.aliases}
        if entity.id in entities_via_facts or terms & element_terms:
            continue
        unmodelled.append({"entity": entity.id, "name": entity.name, "kind": entity.kind})

    unused_facts = [
        {"fact": f.id, "statement": f.statement}
        for f in sorted(register.facts.values(), key=lambda f: f.id)
        if f.id not in cited_facts
    ]
    return {"unmodelledEntities": unmodelled, "unusedFacts": unused_facts}


def render_delta(data: dict[str, Any]) -> str:
    lines = ["Delta: fact register vs approved model", ""]
    lines.append(f"Entities with no model counterpart ({len(data['unmodelledEntities'])}):")
    for row in data["unmodelledEntities"]:
        kind = f" [{row['kind']}]" if row["kind"] else ""
        lines.append(f"  {row['entity']:<30} {row['name']}{kind}")
    if not data["unmodelledEntities"]:
        lines.append("  none")
    lines.append("")
    lines.append(f"Facts no model concept cites ({len(data['unusedFacts'])}):")
    for row in data["unusedFacts"]:
        lines.append(f"  {row['fact']:<40} {row['statement'][:90]}")
    if not data["unusedFacts"]:
        lines.append("  none")
    lines += [
        "",
        "Candidates, not defects: an unmodelled entity may be out of scope, and direct "
        "file+quote citations do not count as fact use. Judgement belongs to ea-delta-ingest.",
    ]
    return "\n".join(lines)
