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

from . import correspond, cost, dsl, facts as facts_mod, genschema, govern, ui
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
    # Only a *recognised* disposition counts as classified: a mistyped one is not
    # portfolio management, and counting it made the KPI disagree with the AD.
    with_time = sum(
        1 for a in applications if a.properties.get("timeDisposition") in genschema.TIME_DISPOSITIONS
    )
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

# Every kind the register can emit, in one place. A debt item is only useful if the
# reader knows what it means, so a doc test reads this tuple and fails when a kind is
# missing from the CLI reference or from `ea-health`, which is where the honest response
# to each one is written down.
DEBT_KINDS = (
    "dead-standard-reference",
    "duplicate-name",
    "duplicate-service",
    "hub-element",
    "isolated-element",
    "overlapping-applications",
    "rationalization-candidate",
    "stale-content",
    "unsupported-capability",
)

# The three overlap queries: the kinds that carry structured extras beyond
# kind/concept/detail. That is why docs/CLI.md documents *their* JSON shape -- a
# machine-readable contract is a CLI-reference concern -- while what to do about any
# kind belongs where the response is written down, in `ea-health`.
OVERLAP_KINDS = ("duplicate-service", "overlapping-applications", "rationalization-candidate")

# --- overlap and rationalization -------------------------------------------------
#
# Three queries that answer "does this portfolio do the same job twice?". They report;
# they never conclude. Duplication is sometimes *deliberate* -- a second claims system
# for resilience, a regional instance kept for data residency -- and a tool that cannot
# tell drift from design must therefore print the data a human needs to tell them apart,
# which is what the realizers' portfolio properties are doing below.

# Only application components count as realizers here. A capability realized by a
# component *and* by a business role is division of labour, not duplicate functionality
# -- the golden set's Appointment Booking (booking portal + front desk) is exactly that
# shape, and flagging it would be the RDY008 mistake again: for an advisory report the
# only real failure mode is noise.
RATIONALIZATION_REALIZER_TYPES = ("ApplicationComponent",)

# Two shared capabilities, not one. One capability realized by two components is already
# reported as a rationalization candidate; a *pair* only becomes a merge conversation
# when the overlap is repeated, which is the signal one shared capability cannot carry.
OVERLAP_MIN_SHARED = 2

SERVICE_TYPES = ("ApplicationService", "BusinessService", "TechnologyService")

# The provider of a service is whatever realizes it (component -> application service) or
# is assigned to it (role -> business service). Serving is the wrong direction: it points
# at the consumer.
PROVIDING_RELATIONSHIPS = ("Realization", "Assignment")

# Printed first for every realizer, present or not, because "not recorded" is itself the
# finding half the time: a rationalization decision taken without knowing either system's
# disposition is a coin toss with a meeting attached.
PORTFOLIO_KEYS = ("timeDisposition", "lifecycle")


def _portfolio_note(properties: dict[str, Any]) -> str:
    """The properties a rationalization decision is actually taken on.

    *Every* property is printed, not a fixed vocabulary: organisations score fit under
    their own key names (``functionalFit``, ``fit-score``, ``tech_health``), and a
    report that read only keys this repository invented would print ``not recorded``
    over data the operator had carefully filled in.
    """
    parts = [f"{key}: {properties.get(key) or 'not recorded'}" for key in PORTFOLIO_KEYS]
    parts += [f"{key}: {value}" for key, value in sorted(properties.items()) if key not in PORTFOLIO_KEYS]
    return ", ".join(parts)


def _capability_realizers(model: dsl.Model) -> dict[str, list[dsl.Element]]:
    """Capability id -> the application components that realize it, id-ordered."""
    realizers: dict[str, dict[str, dsl.Element]] = {}
    for relationship in model.relationships.values():
        if relationship.type != "Realization":
            continue
        source = model.elements.get(relationship.source)
        target = model.elements.get(relationship.target)
        if source is None or target is None:
            continue
        if target.type != "Capability" or source.type not in RATIONALIZATION_REALIZER_TYPES:
            continue
        # Keyed by id: two Realization edges between the same pair are one realizer, not
        # two, and counting them twice would invent an overlap out of a modelling slip.
        realizers.setdefault(target.id, {})[source.id] = source
    return {cap: [by_id[i] for i in sorted(by_id)] for cap, by_id in realizers.items()}


def _rationalization_items(model: dsl.Model) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for capability_id, apps in sorted(_capability_realizers(model).items()):
        if len(apps) < 2:
            continue
        capability = model.elements[capability_id]
        items.append(
            {
                "kind": "rationalization-candidate",
                "concept": capability_id,
                "detail": (
                    f"'{capability.name}' is realized by {len(apps)} application components: "
                    + ", ".join(app.id for app in apps)
                ),
                "realizers": [
                    {"id": app.id, "name": app.name, "properties": dict(sorted(app.properties.items()))}
                    for app in apps
                ],
            }
        )
    return items


def _overlap_items(model: dsl.Model) -> list[dict[str, Any]]:
    """Application pairs realizing the same capabilities more than once."""
    capabilities_of: dict[str, set[str]] = {}
    for capability_id, apps in _capability_realizers(model).items():
        for app in apps:
            capabilities_of.setdefault(app.id, set()).add(capability_id)

    items: list[dict[str, Any]] = []
    application_ids = sorted(capabilities_of)
    for index, left in enumerate(application_ids):
        for right in application_ids[index + 1 :]:
            shared = sorted(capabilities_of[left] & capabilities_of[right])
            if len(shared) < OVERLAP_MIN_SHARED:
                continue
            items.append(
                {
                    "kind": "overlapping-applications",
                    "concept": left,
                    "detail": (
                        f"shares {len(shared)} realized capabilities with '{right}': " + ", ".join(shared)
                    ),
                    "pair": [left, right],
                    "shared": shared,
                }
            )
    return items


def _service_providers(model: dsl.Model) -> dict[str, list[str]]:
    providers: dict[str, set[str]] = {}
    for relationship in model.relationships.values():
        if relationship.type not in PROVIDING_RELATIONSHIPS:
            continue
        target = model.elements.get(relationship.target)
        if target is None or target.type not in SERVICE_TYPES:
            continue
        if relationship.source in model.elements:
            providers.setdefault(target.id, set()).add(relationship.source)
    return {service: sorted(ids) for service, ids in providers.items()}


def _duplicate_service_items(model: dsl.Model) -> list[dict[str, Any]]:
    """Services with one name offered by different providers.

    The plain ``duplicate-name`` query compares type *and* name, so it cannot see an
    application service and a business service called the same thing -- and it says
    nothing about who offers them, which is the only fact that separates "two teams
    built the same thing" from "someone typed the same name twice".

    Two exclusions keep this out of noise: providers must be *disjoint* (one component
    publishing two same-named services is a modelling slip, not portfolio duplication),
    and a pair already joined by a relationship is skipped -- an application service
    realizing an identically named business service is idiomatic layering, and flagging
    it would punish correct ArchiMate.
    """
    related: set[frozenset[str]] = {
        frozenset((r.source, r.target)) for r in model.relationships.values() if r.source != r.target
    }
    providers = _service_providers(model)
    groups: dict[str, list[dsl.Element]] = {}
    for element in model.elements.values():
        if element.type in SERVICE_TYPES and element.name.strip():
            groups.setdefault(_normalize(element.name), []).append(element)

    items: list[dict[str, Any]] = []
    for _name, group in sorted(groups.items()):
        ordered = sorted(group, key=lambda e: e.id)
        for position, service in enumerate(ordered):
            mine = set(providers.get(service.id, ()))
            if not mine:
                continue
            for other in ordered[:position]:
                theirs = set(providers.get(other.id, ()))
                if not theirs or mine & theirs:
                    continue
                if frozenset((service.id, other.id)) in related:
                    continue
                items.append(
                    {
                        "kind": "duplicate-service",
                        "concept": service.id,
                        "detail": (
                            f"{service.type} '{service.name}' shares its name with {other.type} "
                            f"'{other.id}'; provided by {', '.join(sorted(mine))} rather than "
                            f"{', '.join(sorted(theirs))}"
                        ),
                        "duplicateOf": other.id,
                        "providers": sorted(mine),
                        "otherProviders": sorted(theirs),
                    }
                )
                # One partner per service: the first (id-ordered) match is enough to start
                # the conversation, and a group of four would otherwise print six lines
                # saying the same thing.
                break
    return items


def debt(root: Path, today: date | None = None) -> dict[str, Any]:
    """The EA-debt register: deterministic graph queries from the smells catalogue."""
    today = today or date.today()
    model, _documents, config = dsl.load(root, "approved")
    governance = govern.load(root)
    items: list[dict[str, Any]] = []

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

    # Overlap: the portfolio doing one job twice. These carry structured extras beyond
    # kind/concept/detail, so they are appended whole rather than through add().
    items.extend(_rationalization_items(model))
    items.extend(_overlap_items(model))
    items.extend(_duplicate_service_items(model))

    stale_data = staleness(root, today)
    for row in stale_data["rows"]:
        if row["state"] in {"stale", "unreviewed"}:
            add("stale-content", row["id"], f"state: {row['state']}, last reviewed {row['reviewed'] or 'never'}")

    dead = {s.id: s.lifecycle for s in governance.standards.values() if s.lifecycle in {"deprecated", "retired"}}
    dead_standard_refs: list[tuple[str, str]] = []
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        for ref in element.standards:
            if ref in dead:
                covered = governance.covering(element.id, ref, today)
                note = f" (dispensation '{covered.id}' until {covered.expires})" if covered else ""
                add("dead-standard-reference", element.id, f"references {dead[ref]} standard '{ref}'{note}")
                dead_standard_refs.append((element.id, ref))

    report: dict[str, Any] = {"asOf": today.isoformat(), "items": items, "total": len(items)}

    # Cost is *only* present when the operator configured rates. Not an empty section,
    # not zeroes: an unpriced repository must see byte-identical output to the release
    # before this one, or every existing report diff becomes unreadable for a feature
    # nobody switched on.
    costed = cost.price(
        cost.measure(
            model,
            governance,
            stale_data["rows"],
            stale_data["thresholdDays"],
            {capability: len(apps) for capability, apps in _capability_realizers(model).items()},
            dead_standard_refs,
            today,
        ),
        config,
    )
    if costed is not None:
        report["cost"] = costed
    return report


def render_debt(data: dict[str, Any]) -> str:
    lines = [ui.bold(f"EA debt register as of {data['asOf']} -- {data['total']} item(s)"), ""]
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for item in data["items"]:
        by_kind.setdefault(item["kind"], []).append(item)
    for kind in sorted(by_kind):
        lines.append(f"{ui.yellow(ui.bold(kind))} ({len(by_kind[kind])}):")
        for item in by_kind[kind]:
            concept = "{:<40}".format(item["concept"])
            lines.append(f"  {ui.bold(concept)} {ui.dim(item['detail'])}")
            # A rationalization candidate is unreadable without the realizers' portfolio
            # properties next to it -- "two systems do this" is a question, "two systems
            # do this, both Tolerate, neither with a lifecycle" is a decision.
            for realizer in item.get("realizers", ()):
                label = "{:<38}".format(realizer["id"])
                lines.append(f"    {label} {ui.dim(_portfolio_note(realizer['properties']))}")
        lines.append("")
    if not data["items"]:
        lines.append(ui.green(f"{ui.check()} No debt items found."))
    if data.get("cost"):
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(cost.render(data["cost"]))
    return "\n".join(lines).rstrip() + "\n"


# ------------------------------------------------------------------------- roadmap


def roadmap(root: Path, today: date | None = None) -> dict[str, Any]:
    """The Implementation & Migration layer read as a plan: plateaus in date order,
    what each one holds, the gaps between them, and the portfolio decisions no plateau
    carries. That last number is the one worth looking at -- a TIME disposition with no
    plateau is an intention nobody has scheduled."""
    today = today or date.today()
    model, _documents, _config = dsl.load(root, "approved")

    plateaus = [e for e in model.elements.values() if e.type == "Plateau"]
    membership: dict[str, list[str]] = {}
    for relationship in model.relationships.values():
        if relationship.source in {p.id for p in plateaus} and relationship.type in {
            "Aggregation",
            "Composition",
        }:
            membership.setdefault(relationship.source, []).append(relationship.target)

    rows: list[dict[str, Any]] = []
    for plateau in plateaus:
        raw = plateau.properties.get("plateauDate", "")
        try:
            reached: date | None = datetime.strptime(raw, "%Y-%m-%d").date() if raw else None
        except ValueError:
            reached = None  # PLAT003 reports it; the report shows the raw value
        rows.append(
            {
                "id": plateau.id,
                "name": plateau.name,
                "date": raw,
                "state": "unscheduled" if reached is None else ("reached" if reached < today else "planned"),
                "includes": sorted(set(membership.get(plateau.id, []))),
            }
        )
    # Undated plateaus sort last: they have no place in the sequence, which is the
    # finding PLAT001 makes, and inventing one here would hide it.
    rows.sort(key=lambda r: (r["date"] == "", r["date"], r["id"]))

    gaps = []
    plateau_ids = {p.id for p in plateaus}
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        if element.type != "Gap":
            continue
        related = sorted(
            {
                far
                for r in model.relationships.values()
                for near, far in ((r.source, r.target), (r.target, r.source))
                if near == element.id and far in plateau_ids
            }
        )
        gaps.append({"id": element.id, "name": element.name, "plateaus": related})

    scheduled = {member for row in rows for member in row["includes"]}
    unscheduled = [
        {
            "id": e.id,
            "name": e.name,
            "timeDisposition": e.properties.get("timeDisposition", ""),
        }
        for e in sorted(model.elements.values(), key=lambda e: e.id)
        if e.properties.get("timeDisposition") in {"Migrate", "Eliminate"} and e.id not in scheduled
    ]

    return {
        "asOf": today.isoformat(),
        "plateaus": rows,
        "gaps": gaps,
        "unscheduledIntent": unscheduled,
        "counts": {
            "plateaus": len(rows),
            "gaps": len(gaps),
            "scheduled": len(scheduled),
            "unscheduledIntent": len(unscheduled),
        },
    }


def render_roadmap(data: dict[str, Any]) -> str:
    counts = data["counts"]
    lines = [
        ui.bold(f"Roadmap as of {data['asOf']} -- {counts['plateaus']} plateau(s), {counts['gaps']} gap(s)"),
        "",
    ]
    if not data["plateaus"]:
        lines.append(
            ui.dim(
                "No plateaus. The model records what is, not what is planned -- add "
                "Plateau elements with a plateauDate to make the migration a model rather "
                "than a slide."
            )
        )
        return "\n".join(lines) + "\n"

    for row in data["plateaus"]:
        marker = ui.dim("[reached]") if row["state"] == "reached" else ui.green("[planned]")
        if row["state"] == "unscheduled":
            marker = ui.red("[no date]")
        lines.append(f"  {marker} {ui.bold(row['date'] or '????-??-??')}  {row['name']} ({row['id']})")
        for member in row["includes"]:
            lines.append(f"      {ui.cyan(member)}")
        if not row["includes"]:
            lines.append(f"      {ui.dim('nothing aggregated -- the plateau holds no elements')}")
    lines.append("")

    if data["gaps"]:
        lines.append(ui.bold(f"Gaps ({len(data['gaps'])}):"))
        for gap in data["gaps"]:
            between = ", ".join(gap["plateaus"]) or ui.red("no plateau")
            lines.append(f"  {ui.bold(gap['id'])} {gap['name']} {ui.dim('-- ' + between)}")
        lines.append("")

    if data["unscheduledIntent"]:
        lines.append(ui.yellow(ui.bold(f"Intent with no plan ({len(data['unscheduledIntent'])}):")))
        for row in data["unscheduledIntent"]:
            lines.append(
                f"  {ui.bold('{:<40}'.format(row['id']))} {row['timeDisposition']} "
                + ui.dim("-- decided, but no plateau carries it")
            )
    else:
        lines.append(ui.green(f"{ui.check()} Every Migrate/Eliminate disposition is in a plateau."))
    return "\n".join(lines).rstrip() + "\n"


# -------------------------------------------------------- ISO 42010 §6.9 correspondences


def correspondences(root: Path, today: date | None = None) -> dict[str, Any]:
    """What relates to what across the AD, and the rule each relation is held to."""
    today = today or date.today()
    model, _documents, _config = dsl.load(root, "approved")
    governance = govern.load(root)
    data = correspond.summary(correspond.derive(model, governance, today))
    data["asOf"] = today.isoformat()
    return data


def render_correspondences(data: dict[str, Any]) -> str:
    lines = [
        ui.bold(
            f"Correspondences (ISO 42010 §6.9) as of {data['asOf']} -- "
            f"{data['total']} relation(s), {data['violated']} violated"
        ),
        "",
    ]
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for item in data["items"]:
        by_kind.setdefault(item["kind"], []).append(item)
    for kind in data["kinds"]:
        items = by_kind.get(kind["kind"], [])
        if not items:
            continue
        header = f"{kind['kind']} ({kind['relates']}) -- {len(items)}"
        lines.append(ui.cyan(ui.bold(header)))
        lines.append(f"  {ui.dim('rule: ' + kind['rule'])}")
        lines.append(f"  {ui.dim('enforced by: ' + ', '.join(kind['enforcedBy']))}")
        for item in items:
            pair = "{:<40}".format(f"{item['from']} -> {item['to']}")
            if item["satisfied"]:
                lines.append(f"  {ui.green(ui.check())} {pair}")
            else:
                lines.append(f"  {ui.red('x')} {ui.bold(pair)} {ui.red(item['code'])} {item['detail']}")
        lines.append("")
    if not data["items"]:
        lines.append(
            ui.dim(
                "No correspondences. Nothing in this repository relates the model to its "
                "decisions, its standards or its evidence -- which is what the clause is for."
            )
        )
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


def _clause_6_9(correspondences: list[correspond.Correspondence]) -> tuple[str, str]:
    """ISO 42010 §6.9 -- correspondences, and the rules they are held to.

    Derived from what the AD already records (``easkills/correspond.py``), so the clause
    passes on relations that exist and are checked, not on a section somebody wrote.
    An AD with none is reported as a `gap` rather than a vacuous pass: nothing tying the
    model to its decisions, its standards and its evidence is a state to see, not to
    quietly tick off.
    """
    if not correspondences:
        return (
            "gap",
            "no correspondences recorded -- nothing relates the model to its decisions, "
            "standards or fact register",
        )
    violated = [c for c in correspondences if not c.satisfied]
    kinds = sorted({c.kind for c in correspondences})
    counted = f"{len(correspondences)} correspondence(s) over {len(kinds)} rule(s): {', '.join(kinds)}"
    if violated:
        listed = ", ".join(f"{c.source} -> {c.target} ({c.code})" for c in violated[:5])
        more = f", and {len(violated) - 5} more" if len(violated) > 5 else ""
        return "fail", f"{counted}; {len(violated)} violated: {listed}{more}"
    return "pass", f"{counted}; every one satisfied"


def _clause_6_10(root: Path, governance: govern.Governance) -> tuple[str, str]:
    """ISO 42010 §6.10 -- decisions *and* their rationale, recorded in the description.

    Same correction as §6.8: a decision record in the governance log is a decision the
    architects can find, not one the description records. The clause is about the AD, so
    the pass depends on the generated document naming each standing decision.
    """
    if not governance.decisions:
        return "fail", "no decision records -- governance-log/decisions/ is empty"
    standing = [
        d
        for d in sorted(governance.decisions.values(), key=lambda d: d.id)
        if d.status in correspond.STANDING_DECISION_STATUSES
    ]
    total = f"{len(governance.decisions)} decision record(s); rationale is schema-mandatory"
    if not standing:
        return "fail", f"{total}, but none of them still stands"
    description = root / "docs" / "architecture-description.md"
    if not description.is_file():
        return (
            "fail",
            f"{total}, but docs/architecture-description.md does not exist -- "
            "generate it with 'python -m easkills docs'",
        )
    text = description.read_text(encoding="utf-8", errors="replace")
    # An empty title must not match everything: `"" in text` is always true, which
    # would turn a nameless decision into a recorded one.
    missing = sorted(
        d.id for d in standing if d.id not in text and not (d.title and d.title in text)
    )
    if missing:
        return "fail", f"{total}, but the architecture description does not record: {', '.join(missing)}"
    return "pass", f"{total}, each standing one recorded in the architecture description"


def conformance(root: Path, today: date | None = None) -> dict[str, Any]:
    """The checkable subset of ISO/IEC/IEEE 42010:2022 Clause 6, honestly labelled:
    ``pass``/``fail`` where a check exists, ``gap`` where this tooling does not
    implement the clause yet -- silence is never presented as conformance."""
    today = today or date.today()
    model, _documents, _config = dsl.load(root, "approved")
    governance = govern.load(root)
    derived = correspond.derive(model, governance, today)
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
            "Correspondences between AD elements, and the rules they are held to",
            *_clause_6_9(derived),
        ),
        item(
            "6.10",
            "Architecture decisions recorded with rationale",
            *_clause_6_10(root, governance),
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
