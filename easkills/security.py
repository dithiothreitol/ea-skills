"""Security architecture over the existing model: classification, boundaries, reach.

There is no security layer here and none is missing -- ArchiMate has none on purpose, and
every concept a security architect works with already has a governed home (`ea-regulatory`
says where). What was missing was a vocabulary the tooling can read (`genschema`:
`dataClassification`, `personalData`, `secConfidentiality`/`secIntegrity`/`secAvailability`,
`exposure`, `trustZone`) and the three questions that vocabulary makes answerable:

* **What does a publicly exposed element hold, and is anything governing it?** (`SEC001`)
* **Where does a relationship cross a trust boundary, and is either end governed?**
  (`SEC002`, and `propose --from threats` for the assessment the crossing needs)
* **If a public element were compromised, what could the attacker reach?** (`exposure`)

"Governed" has one definition, used by every rule and report here: an element is governed
when a `Requirement`, `Constraint` or `Principle` binds it through `appliesTo`, or when it
claims at least one standard from the SIB. Nothing reads the *text* of an obligation to
decide whether it is "about security" -- that is a judgement, and the rules state the
narrower, checkable fact: the model records an obligation on this element, or it does not.

Reach is not change impact. `impact` asks "if this changes, what is affected?"; `exposure`
asks "if this is compromised, what can the attacker get to?" -- and for `Serving` the two
run in opposite directions: when the order API serves the portal, a change to the API
reaches the portal, while an attacker in the portal reaches the API. So reach has its own
declared table (`REACH`), with its reason beside every entry, and a test holds it to the
oracle's relationship types exactly as `impact.PROPAGATION` is held.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import dsl, genschema, ui

OBLIGATION_TYPES = frozenset({"Requirement", "Constraint", "Principle"})
# Relationship types across which something passes between two elements -- data, a call,
# an access, a trigger. A Composition between zones is a modelling statement about
# structure, not a trust boundary being crossed, so it is not one of them.
CROSSING_TYPES = frozenset({"Flow", "Access", "Serving", "Triggering"})
SENSITIVE = ("confidential", "restricted")
CLASSIFICATION_RANK = {value: index for index, value in enumerate(genschema.DATA_CLASSIFICATIONS)}

FORWARD = "forward"
BACKWARD = "backward"
BOTH = "both"
NONE = "none"

# Which way an attacker who holds one end can move to the other, per relationship type.
REACH: dict[str, tuple[str, str]] = {
    "Serving": (BACKWARD, "the consumer calls the provider: holding the consumer reaches the service it uses"),
    "Access": (FORWARD, "whatever holds the accessor holds what it reads or writes"),
    "Flow": (FORWARD, "what flows out of a compromised element arrives at the next one"),
    "Triggering": (FORWARD, "a compromised trigger starts what it triggers"),
    "Realization": (BOTH, "a service is its realizer's behaviour; holding either is holding the other"),
    "Assignment": (BOTH, "an active structure and the behaviour assigned to it run as one"),
    "Composition": (BOTH, "a part runs inside its whole, and the whole contains the part"),
    "Aggregation": (BOTH, "aggregated elements are grouped for a reason that usually includes access"),
    "Influence": (NONE, "a motivation link, not a runtime path"),
    "Specialization": (NONE, "a type relation, not a runtime path"),
    "Association": (NONE, "meaning left to the modeller -- reported by impact as adjacency, never walked"),
}


def obligations(model: dsl.Model) -> dict[str, list[str]]:
    """Element id -> the requirements, constraints and principles that bind it."""
    bound: dict[str, list[str]] = {}
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        if element.type in OBLIGATION_TYPES:
            for target in element.applies_to:
                bound.setdefault(target, []).append(element.id)
    return bound


def governed_ids(model: dsl.Model) -> set[str]:
    """Elements an obligation binds, or that claim a standard -- the one definition."""
    governed = set(obligations(model))
    governed |= {element.id for element in model.elements.values() if element.standards}
    return governed


def effective_classification(model: dsl.Model, element: dsl.Element) -> tuple[str, list[str]]:
    """The highest classification the element holds, and which elements carry it.

    Its own `dataClassification`, and that of every element it `Access`es -- an
    application holding no classification of its own still holds the restricted record it
    reads. Returns ("", []) when nothing is classified.
    """
    candidates: list[tuple[str, str]] = []
    own = element.properties.get("dataClassification", "")
    if own in CLASSIFICATION_RANK:
        candidates.append((own, element.id))
    for relationship in model.relationships.values():
        if relationship.type == "Access" and relationship.source == element.id:
            target = model.elements.get(relationship.target)
            level = target.properties.get("dataClassification", "") if target else ""
            if level in CLASSIFICATION_RANK:
                candidates.append((level, target.id))
    if not candidates:
        return "", []
    top = max(CLASSIFICATION_RANK[level] for level, _ in candidates)
    level = genschema.DATA_CLASSIFICATIONS[top]
    return level, sorted({holder for value, holder in candidates if value == level})


def crossings(model: dsl.Model) -> list[dsl.Relationship]:
    """Relationships whose two ends declare different trust zones."""
    found = []
    for relationship in sorted(model.relationships.values(), key=lambda r: r.id):
        if relationship.type not in CROSSING_TYPES:
            continue
        source = model.elements.get(relationship.source)
        target = model.elements.get(relationship.target)
        if source is None or target is None:
            continue
        zone_a = source.properties.get("trustZone", "").strip()
        zone_b = target.properties.get("trustZone", "").strip()
        if zone_a and zone_b and zone_a != zone_b:
            found.append(relationship)
    return found


def rated_high(element: dsl.Element) -> list[str]:
    return [key for key in genschema.SECURITY_RATING_KEYS if element.properties.get(key) == "high"]


# ---------------------------------------------------------------------------- exposure


@dataclass
class Reached:
    id: str
    hops: int
    via: str  # relationship id
    from_id: str


@dataclass
class Surface:
    start: str
    reached: list[Reached] = field(default_factory=list)
    sensitive: list[str] = field(default_factory=list)
    high: list[str] = field(default_factory=list)
    personal: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)
    ungoverned: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "reached": [
                {"id": r.id, "hops": r.hops, "via": r.via, "from": r.from_id} for r in self.reached
            ],
            "sensitiveData": self.sensitive,
            "ratedHigh": self.high,
            "personalData": self.personal,
            "trustBoundariesCrossed": self.boundaries,
            "ungovernedInReach": self.ungoverned,
        }


@dataclass
class ExposureReport:
    root: Path
    zone: str
    depth: int | None
    surfaces: list[Surface] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "zone": self.zone,
            "depth": self.depth,
            "publicElements": [s.start for s in self.surfaces],
            "surfaces": [s.as_dict() for s in self.surfaces],
        }


def _adjacency(model: dsl.Model) -> dict[str, list[tuple[str, str]]]:
    """element -> [(neighbour, relationship id)] in the attacker's direction."""
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for relationship in sorted(model.relationships.values(), key=lambda r: r.id):
        if relationship.source not in model.elements or relationship.target not in model.elements:
            continue
        direction, _reason = REACH.get(relationship.type, (NONE, ""))
        if direction in (FORWARD, BOTH):
            adjacency.setdefault(relationship.source, []).append((relationship.target, relationship.id))
        if direction in (BACKWARD, BOTH):
            adjacency.setdefault(relationship.target, []).append((relationship.source, relationship.id))
    return adjacency


def exposure(root: Path, zone: str = "approved", depth: int | None = None) -> ExposureReport:
    """From every publicly exposed element, what an attacker holding it could reach."""
    model, _documents, _config = dsl.load_zone(root, zone)
    adjacency = _adjacency(model)
    governed = governed_ids(model)
    crossing_ids = {r.id for r in crossings(model)}
    report = ExposureReport(root=root, zone=zone, depth=depth)
    starts = sorted(e.id for e in model.elements.values() if e.properties.get("exposure") == "public")
    for start in starts:
        surface = Surface(start=start)
        seen = {start: Reached(start, 0, "", "")}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            hops = seen[current].hops
            if depth is not None and hops >= depth:
                continue
            for neighbour, via in adjacency.get(current, []):
                if neighbour in seen:
                    continue
                seen[neighbour] = Reached(neighbour, hops + 1, via, current)
                queue.append(neighbour)
        surface.reached = sorted(seen.values(), key=lambda r: (r.hops, r.id))
        for item in surface.reached:
            element = model.elements[item.id]
            if element.properties.get("dataClassification") in SENSITIVE:
                surface.sensitive.append(item.id)
            if rated_high(element):
                surface.high.append(item.id)
            if element.properties.get("personalData") in ("personal", "special-category"):
                surface.personal.append(item.id)
            if item.via in crossing_ids:
                surface.boundaries.append(item.via)
            if item.id not in governed and element.type not in OBLIGATION_TYPES and item.hops:
                surface.ungoverned.append(item.id)
        report.surfaces.append(surface)
    return report


def render_exposure(report: ExposureReport) -> str:
    lines = [
        ui.bold(f"Exposure -- zone '{report.zone}' at {report.root}"),
        ui.dim(
            f"{len(report.surfaces)} publicly exposed element(s); "
            + ("unbounded reach" if report.depth is None else f"reach up to {report.depth} hop(s)")
        ),
        "",
    ]
    if not report.surfaces:
        lines.append(
            ui.dim(
                "No element declares `exposure: public`, so there is no attack surface to walk. "
                "That is the right answer for a model that has recorded exposure and has none, "
                "and the wrong one for a model that has not recorded it yet."
            )
        )
        return "\n".join(lines)

    def listed(items: list[str], colour) -> str:
        return colour(", ".join(items)) if items else ui.dim("none")

    for surface in report.surfaces:
        lines.append(f"  {ui.bold(surface.start)}  {ui.dim(f'reaches {len(surface.reached) - 1} element(s)')}")
        for item in surface.reached[1:]:
            lines.append(f"      {item.hops} hop(s)  {item.id:<36} {ui.dim(f'via {item.via} from {item.from_id}')}")
        lines.append(f"      sensitive data     {listed(surface.sensitive, ui.red)}")
        lines.append(f"      rated high         {listed(surface.high, ui.yellow)}")
        lines.append(f"      personal data      {listed(surface.personal, ui.yellow)}")
        lines.append(f"      boundaries crossed {listed(surface.boundaries, ui.cyan)}")
        lines.append(f"      ungoverned         {listed(surface.ungoverned, ui.yellow)}")
        lines.append("")
    lines.append(
        ui.dim(
            "Reach follows declared directions (REACH): a consumer reaches the service it uses, "
            "an accessor reaches its data, a flow reaches its destination. Association is never "
            "walked. This is a report, not a finding: what to do about a path is a decision."
        )
    )
    return "\n".join(lines)
