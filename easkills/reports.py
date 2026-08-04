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

from . import dsl, facts as facts_mod, govern, ui
from .validate import _normalize

# ------------------------------------------------------------------------- staleness


def staleness(root: Path, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    model, _documents, config = dsl.load(root, "approved")
    governance = govern.load(root)
    # Reports never crash on a bad config value; the model gate reports it (SCHEMA002).
    threshold, _problem = dsl.config_number(config, "stalenessDays", 365, minimum=1)

    # Demand per element: how many service requests name it in scope. Demand-weighted
    # maintenance is the AoD answer to rot -- review what people ask about first, and
    # question whether never-requested content earns its upkeep.
    demand: dict[str, int] = {}
    for request in governance.requests.values():
        for element_id in request.scope:
            demand[element_id] = demand.get(element_id, 0) + 1

    rows: list[dict[str, Any]] = []
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        row: dict[str, Any] = {
            "id": element.id,
            "owner": element.owner,
            "demand": demand.get(element.id, 0),
        }
        if not element.last_reviewed:
            rows.append({**row, "reviewed": None, "age": None, "state": "unreviewed"})
            continue
        try:
            reviewed = datetime.strptime(element.last_reviewed, "%Y-%m-%d").date()
        except ValueError:
            rows.append({**row, "reviewed": element.last_reviewed, "age": None, "state": "invalid-date"})
            continue
        age = (today - reviewed).days
        rows.append(
            {
                **row,
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
        "neverRequested": sum(1 for r in rows if r["demand"] == 0),
        "rows": rows,
    }


def render_staleness(data: dict[str, Any]) -> str:
    fresh = ui.green(f"{data['fresh']} fresh")
    stale = ui.red(f"{data['stale']} stale") if data["stale"] else ui.dim("0 stale")
    unreviewed = (
        ui.yellow(f"{data['unreviewed']} unreviewed") if data["unreviewed"] else ui.dim("0 unreviewed")
    )
    lines = [
        ui.bold(f"Staleness as of {data['asOf']} (threshold {data['thresholdDays']} days)"),
        f"{data['elements']} elements: {fresh}, {stale}, {unreviewed}; "
        + ui.dim(f"{data.get('neverRequested', 0)} never requested by any service consumer"),
        "",
    ]
    flagged = [r for r in data["rows"] if r["state"] != "fresh"]
    for row in sorted(flagged, key=lambda r: (-r.get("demand", 0), -(r["age"] or 10**6), r["id"])):
        age = f"{row['age']} days" if row["age"] is not None else "never reviewed"
        state_field = f"{row['state']:<11}"
        state = ui.red(state_field) if row["state"] == "stale" else ui.yellow(state_field)
        identifier = "{:<40}".format(row["id"])
        demand = row.get("demand", 0)
        demand_note = ui.yellow(f"demand: {demand}") if demand else ui.dim("demand: 0")
        lines.append(
            f"  {state} {ui.bold(identifier)} {age:<16} {demand_note}  "
            f"{ui.dim('owner: ' + (row['owner'] or '-'))}"
        )
    if not flagged:
        lines.append(ui.green(f"  {ui.check()} Nothing stale."))
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

    def pct(part: int, whole: int, empty: float = 1.0) -> float:
        """``empty`` is the value for "nothing to measure".

        1.0 reads as vacuous truth for *good* shares (all zero concepts are evidenced),
        but a share of *bad* things must be 0.0 there -- an empty model reporting
        "100% stale/unreviewed" next to "100% owned" is a contradiction on the first
        screen a new repository shows.
        """
        return round(part / whole, 4) if whole else empty

    requests = list(governance.requests.values())
    open_requests = [r for r in requests if r.status == "open"]
    fulfilled = [r for r in requests if r.status == "fulfilled"]
    sla_breaches = []
    for request in open_requests:
        service = governance.services.get(request.service)
        requested = request.requested_date()
        if service and service.sla_days > 0 and requested and (today - requested).days > service.sla_days:
            sla_breaches.append(request.id)
    fulfilment_days = [
        (r.fulfilled_date() - r.requested_date()).days
        for r in fulfilled
        if r.fulfilled_date() and r.requested_date()
    ]

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
            "staleShare": pct(stale["stale"] + stale["unreviewed"], stale["elements"], empty=0.0),
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
        "service": {
            "offerings": sum(1 for s in governance.services.values() if s.lifecycle == "active"),
            "requests": len(requests),
            "open": len(open_requests),
            "fulfilled": len(fulfilled),
            "declined": sum(1 for r in requests if r.status == "declined"),
            "slaBreaches": sorted(sla_breaches),
            "avgFulfilmentDays": round(sum(fulfilment_days) / len(fulfilment_days), 1)
            if fulfilment_days
            else None,
        },
    }


def render_kpi(data: dict[str, Any]) -> str:
    size, ev, gov, port, cap, qual, doc = (
        data["size"], data["evidence"], data["governance"], data["portfolio"],
        data["capabilities"], data["quality"], data["documentation"],
    )
    svc = data["service"]

    def share(value: float) -> str:
        return f"{value:.0%}"

    def label(text: str) -> str:
        return ui.bold("{:<13}".format(text))

    def listed(items: list[str], colour) -> str:
        return colour(", ".join(items)) if items else ui.dim("none")

    lines = [
        ui.bold(f"EA KPIs as of {data['asOf']}"),
        "",
        f"{label('Size')} {size['elements']} elements, {size['relationships']} relationships, "
        f"{size['views']} views; {size['facts']} facts, {size['entities']} entities",
        f"{label('Evidence')} {share(ev['evidencedShare'])} concepts evidenced; "
        f"{ev['assumed']} declared assumption(s)",
        f"{label('Governance')} {share(gov['ownedShare'])} owned; {share(gov['staleShare'])} stale/unreviewed; "
        f"{gov['openDispensations']} open dispensation(s); {gov['decisions']} decision(s); "
        f"{gov['assessments']} assessment(s)",
        f"{label('Portfolio')} {port['applications']} application(s); "
        f"{share(port['timeClassifiedShare'])} TIME-classified; "
        f"obsolescence exposure: {listed(port['obsolescenceExposure'], ui.yellow)}",
        f"{label('Capabilities')} {cap['total']}; unsupported: {listed(cap['unsupported'], ui.red)}",
        f"{label('Quality')} orphans: {listed(qual['orphans'], ui.yellow)}",
        f"{label('Documentation')} {doc['concerns']} concern(s); "
        f"unheld: {listed(doc['unheldConcerns'], ui.red)}; "
        f"unframed: {listed(doc['unframedConcerns'], ui.red)}",
        f"{label('Service')} {svc['offerings']} active offering(s); {svc['requests']} request(s) "
        f"({svc['open']} open, {svc['fulfilled']} fulfilled, {svc['declined']} declined); "
        f"SLA breaches: {listed(svc['slaBreaches'], ui.red)}; "
        f"avg fulfilment: {svc['avgFulfilmentDays'] if svc['avgFulfilmentDays'] is not None else '—'} day(s)",
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
    lines = [ui.bold(f"EA debt register as of {data['asOf']} -- {data['total']} item(s)"), ""]
    by_kind: dict[str, list[dict[str, str]]] = {}
    for item in data["items"]:
        by_kind.setdefault(item["kind"], []).append(item)
    for kind in sorted(by_kind):
        lines.append(f"{ui.yellow(ui.bold(kind))} ({len(by_kind[kind])}):")
        for item in by_kind[kind]:
            concept = "{:<40}".format(item["concept"])
            lines.append(f"  {ui.bold(concept)} {ui.dim(item['detail'])}")
        lines.append("")
    if not data["items"]:
        lines.append(ui.green(f"{ui.check()} No debt items found."))
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------- ISO 42010 clause 6


def _clause_6_8(root: Path, assumed: list[Any]) -> tuple[str, str]:
    """ISO 42010 §6.8 -- and a check that can actually fail.

    Declaring assumptions in the YAML is not "recording" them: the clause is about the
    architecture *description*. So the pass depends on the generated document existing
    and naming every declared assumption. This used to be a hardcoded ``pass``, which
    is the decorative conformance the report exists to avoid.
    """
    if not assumed:
        return "pass", "no declared assumptions -- nothing to record"
    description = root / "docs" / "architecture-description.md"
    if not description.is_file():
        return (
            "fail",
            f"{len(assumed)} declared assumption(s), but docs/architecture-description.md "
            "does not exist -- generate it with 'python -m easkills docs'",
        )
    text = description.read_text(encoding="utf-8", errors="replace")
    missing = sorted(c.id for c in assumed if c.id not in text and (c.name or c.id) not in text)
    if missing:
        return (
            "fail",
            f"the architecture description does not record: {', '.join(missing)} -- "
            "regenerate it after the model changed",
        )
    return "pass", f"{len(assumed)} declared assumption(s), each recorded in the architecture description"


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
            *_clause_6_8(root, assumed),
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
    lines = [ui.bold("ISO/IEC/IEEE 42010:2022 Clause 6 conformance (checkable subset)"), ""]
    for item in data["items"]:
        status_field = "{:<5}".format(item["status"].upper())
        clause_field = "{:<5}".format(item["clause"])
        lines.append(f"  {ui.status(status_field)} {ui.bold(clause_field)} {item['requirement']}")
        lines.append(f"        {ui.dim(item['detail'])}")
    summary = f"{data['passed']} pass, {data['failed']} fail, {data['gaps']} gap(s)"
    lines += [
        "",
        (ui.green(summary) if not data["failed"] else ui.red(summary))
        + ui.dim(" -- a 'gap' is a clause this tooling does not check; it is not silent conformance"),
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
    lines = [ui.bold("Delta: fact register vs approved model"), ""]
    lines.append(ui.bold(f"Entities with no model counterpart ({len(data['unmodelledEntities'])}):"))
    for row in data["unmodelledEntities"]:
        kind = ui.dim(f" [{row['kind']}]") if row["kind"] else ""
        entity_field = "{:<30}".format(row["entity"])
        lines.append(f"  {ui.cyan(entity_field)} {row['name']}{kind}")
    if not data["unmodelledEntities"]:
        lines.append(ui.dim("  none"))
    lines.append("")
    lines.append(ui.bold(f"Facts no model concept cites ({len(data['unusedFacts'])}):"))
    for row in data["unusedFacts"]:
        fact_field = "{:<40}".format(row["fact"])
        lines.append(f"  {ui.cyan(fact_field)} {ui.dim(row['statement'][:90])}")
    if not data["unusedFacts"]:
        lines.append(ui.dim("  none"))
    lines += [
        "",
        ui.dim(
            "Candidates, not defects: an unmodelled entity may be out of scope, and direct "
            "file+quote citations do not count as fact use. Judgement belongs to ea-delta-ingest."
        ),
    ]
    return "\n".join(lines)
