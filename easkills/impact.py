"""Impact analysis: the deterministic half of change triage (TOGAF Phase H).

``ea-change-triage`` already states the rule that decides a change's class -- *"count
the stakeholder groups whose concerns are touched; two or more means re-architecting"*
-- and then asks a human to do the counting by eye. This module does the counting, and
nothing else: the classification stays a recorded judgement, because one of the three
tests ("does it invalidate an assumption or decision?") is not arithmetic and saying
otherwise would be the decorative determinism this repository refuses.

**Propagation is declared, never inferred.** The vendored matrix answers which
relationships are *permitted*; it says nothing about which way a change travels. That
is a semantic reading of the ArchiMate specification, so it lives in one table
(``PROPAGATION``) with its reasoning attached, and a test asserts that every
relationship type the oracle knows has an entry -- otherwise a future ArchiMate version
would add a type through which impact silently stops flowing.

``Association`` is the honest hole: ArchiMate leaves its meaning to the modeller, so
this module refuses to traverse it and reports those edges separately as adjacency of
unknown direction. Inventing a direction would let the blast radius look thorough while
being made up.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import dsl, govern, ui

# Which way a change travels along each relationship type, and why. "forward" means
# from `source` to `target`: change the source, the target feels it.
FORWARD = "forward"
BACKWARD = "backward"
BOTH = "both"
NONE = "none"

PROPAGATION: dict[str, tuple[str, str]] = {
    "Serving": (FORWARD, "the served element depends on the one serving it"),
    "Realization": (FORWARD, "what is realized depends on whatever realizes it"),
    "Assignment": (FORWARD, "behaviour depends on the active element assigned to it"),
    "Triggering": (FORWARD, "the triggered element depends on its trigger"),
    "Flow": (FORWARD, "the receiver depends on what is sent to it"),
    "Access": (BACKWARD, "the accessor depends on the data it reads or writes"),
    "Specialization": (BACKWARD, "the specialised element depends on the general one"),
    "Composition": (BOTH, "whole and part share fate"),
    "Aggregation": (BOTH, "an aggregate and its members share fate, more weakly"),
    "Influence": (FORWARD, "a motivation element influenced by another moves with it"),
    "Association": (
        NONE,
        "ArchiMate leaves association's meaning to the modeller; a direction here would "
        "be invented, so these edges are reported as adjacency and never traversed",
    ),
}

# The applicability selector is not a relationship, but it carries impact: change the
# element a requirement binds and the requirement's satisfaction is in question.
APPLIES_TO_REASON = "the obligation is bound to this element, so a change puts its satisfaction in question"

# ea-change-triage's documented threshold: two or more stakeholder groups means
# re-architecting. Defined here so the report and the skill cannot disagree.
REARCHITECTING_STAKEHOLDERS = 2


@dataclass(frozen=True)
class Hop:
    """One step of the blast radius: what was reached, from where, and along what."""

    element: str
    via: str  # relationship id, or "appliesTo"
    kind: str  # relationship type, or "appliesTo"
    frm: str
    distance: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "element": self.element,
            "via": self.via,
            "kind": self.kind,
            "from": self.frm,
            "distance": self.distance,
        }


@dataclass
class ImpactReport:
    root: Path
    scope: str
    depth: int | None
    as_of: str
    scope_name: str = ""
    affected: list[Hop] = field(default_factory=list)
    stakeholders: list[dict[str, Any]] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    views: list[str] = field(default_factory=list)
    decisions: list[dict[str, str]] = field(default_factory=list)
    obligations: list[dict[str, str]] = field(default_factory=list)
    standards: list[dict[str, str]] = field(default_factory=list)
    dispensations: list[dict[str, str]] = field(default_factory=list)
    demand: list[dict[str, str]] = field(default_factory=list)
    adjacent: list[dict[str, str]] = field(default_factory=list)
    unowned: list[str] = field(default_factory=list)

    @property
    def elements(self) -> list[str]:
        """Every element in the blast radius, the scope itself first."""
        return [self.scope] + [hop.element for hop in self.affected]

    @property
    def triage_class(self) -> str:
        """The mechanical half of the Phase H test, never the whole verdict."""
        if len(self.stakeholders) >= REARCHITECTING_STAKEHOLDERS:
            return "re-architecting"
        return "incremental-or-simplification"

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "scope": self.scope,
            "scopeName": self.scope_name,
            "asOf": self.as_of,
            "depth": self.depth,
            "counts": {
                "elements": len(self.elements),
                "stakeholders": len(self.stakeholders),
                "concerns": len(self.concerns),
                "views": len(self.views),
                "decisions": len(self.decisions),
                "obligations": len(self.obligations),
                "standards": len(self.standards),
                "demand": len(self.demand),
            },
            "elements": self.elements,
            "affected": [hop.as_dict() for hop in self.affected],
            "stakeholders": self.stakeholders,
            "concerns": self.concerns,
            "views": self.views,
            "decisions": self.decisions,
            "obligations": self.obligations,
            "standards": self.standards,
            "dispensations": self.dispensations,
            "demand": self.demand,
            "adjacent": self.adjacent,
            "unowned": self.unowned,
            "triage": {
                "stakeholderGroups": len(self.stakeholders),
                "threshold": REARCHITECTING_STAKEHOLDERS,
                "mechanicalClass": self.triage_class,
                "notEvaluated": [
                    "whether the change invalidates a recorded assumption, decision or "
                    "capability boundary -- that test is judgement, and ea-change-triage owns it"
                ],
            },
        }


class ImpactError(RuntimeError):
    pass


def _edges(model: dsl.Model) -> dict[str, list[tuple[str, str, str, str]]]:
    """Adjacency as ``{element: [(neighbour, via, kind, reason)]}``, propagation applied.

    Built once and sorted, so a traversal over it is deterministic regardless of the
    order the model files happened to be read in.
    """
    out: dict[str, list[tuple[str, str, str, str]]] = {}

    def add(frm: str, to: str, via: str, kind: str, reason: str) -> None:
        if frm in model.elements and to in model.elements:
            out.setdefault(frm, []).append((to, via, kind, reason))

    for relationship in model.relationships.values():
        direction, reason = PROPAGATION.get(relationship.type, (NONE, "unknown relationship type"))
        if direction in (FORWARD, BOTH):
            add(relationship.source, relationship.target, relationship.id, relationship.type, reason)
        if direction in (BACKWARD, BOTH):
            add(relationship.target, relationship.source, relationship.id, relationship.type, reason)
    for element in model.elements.values():
        for bound in element.applies_to:
            add(bound, element.id, "appliesTo", "appliesTo", APPLIES_TO_REASON)

    for key in out:
        out[key] = sorted(set(out[key]))
    return out


def analyse(root: Path, scope: str, depth: int | None = None, today: date | None = None) -> ImpactReport:
    today = today or date.today()
    model, _documents, _config = dsl.load(root, "approved")
    governance = govern.load(root)
    if scope not in model.elements:
        raise ImpactError(f"'{scope}' is not an element in the approved model")

    report = ImpactReport(
        root=root,
        scope=scope,
        depth=depth,
        as_of=today.isoformat(),
        scope_name=model.elements[scope].name,
    )

    # Breadth-first so `distance` is the shortest path, and the first way an element is
    # reached is the one worth reporting: a reviewer wants the closest cause, not every
    # path there is.
    edges = _edges(model)
    seen = {scope}
    queue: deque[tuple[str, int]] = deque([(scope, 0)])
    while queue:
        current, distance = queue.popleft()
        if depth is not None and distance >= depth:
            continue
        for neighbour, via, kind, _reason in edges.get(current, []):
            if neighbour in seen:
                continue
            seen.add(neighbour)
            report.affected.append(
                Hop(element=neighbour, via=via, kind=kind, frm=current, distance=distance + 1)
            )
            queue.append((neighbour, distance + 1))
    report.affected.sort(key=lambda hop: (hop.distance, hop.element))
    affected = set(report.elements)

    # Association: adjacency without a direction. Reported next to the radius, never in
    # it -- a reviewer still needs to know these exist.
    for relationship in sorted(model.relationships.values(), key=lambda r: r.id):
        if PROPAGATION.get(relationship.type, (NONE, ""))[0] != NONE:
            continue
        for near, far in ((relationship.source, relationship.target), (relationship.target, relationship.source)):
            if near in affected and far in model.elements and far not in affected:
                report.adjacent.append(
                    {"element": far, "via": relationship.id, "kind": relationship.type, "from": near}
                )

    # Stakeholders, through the ISO 42010 apparatus: an affected element shows up in a
    # view, the view frames concerns, and somebody holds them. This is the number the
    # Phase H test turns on.
    touched_views = sorted(
        v.id for v in model.views.values() if set(v.include) & affected
    )
    report.views = touched_views
    touched_concerns: set[str] = set()
    for view_id in touched_views:
        touched_concerns.update(model.views[view_id].concerns)
    report.concerns = sorted(touched_concerns & set(model.concerns))
    for stakeholder in sorted(model.stakeholders.values(), key=lambda s: s.id):
        held = sorted(set(stakeholder.concerns) & touched_concerns)
        if held:
            report.stakeholders.append(
                {"id": stakeholder.id, "name": stakeholder.name, "concerns": held}
            )

    for element_id in sorted(affected):
        element = model.elements[element_id]
        if not element.owner:
            report.unowned.append(element_id)
        for standard_id in sorted(set(element.standards)):
            standard = governance.standards.get(standard_id)
            report.standards.append(
                {
                    "element": element_id,
                    "standard": standard_id,
                    "lifecycle": standard.lifecycle if standard else "unknown",
                }
            )

    for element in sorted(model.elements.values(), key=lambda e: e.id):
        bound = sorted(set(element.applies_to) & affected)
        if bound:
            report.obligations.append(
                {"id": element.id, "type": element.type, "name": element.name, "binds": ", ".join(bound)}
            )

    for decision in sorted(governance.decisions.values(), key=lambda d: d.id):
        named = sorted(set(decision.related_elements) & affected)
        if named:
            report.decisions.append(
                {
                    "id": decision.id,
                    "title": decision.title,
                    "status": decision.status,
                    "elements": ", ".join(named),
                }
            )

    for dispensation in sorted(governance.dispensations.values(), key=lambda d: d.id):
        if set(dispensation.applies_to) & affected and dispensation.is_open(today):
            report.dispensations.append(
                {
                    "id": dispensation.id,
                    "waives": dispensation.waives_standard or dispensation.waives_rule,
                    "expires": dispensation.expires,
                }
            )

    for request in sorted(governance.requests.values(), key=lambda r: r.id):
        named = sorted(set(request.scope) & affected)
        if named:
            report.demand.append(
                {
                    "id": request.id,
                    "requestedBy": request.requested_by,
                    "status": request.status,
                    "elements": ", ".join(named),
                }
            )

    return report


def render(report: ImpactReport, model_names: dict[str, str] | None = None) -> str:
    names = model_names or {}
    depth = f"depth {report.depth}" if report.depth is not None else "unbounded"
    lines = [
        ui.bold(f"Impact of a change to {report.scope_name or report.scope} (`{report.scope}`)"),
        ui.dim(
            f"as of {report.as_of}; {depth}; {len(report.elements)} element(s) in the blast radius, "
            f"{len(report.stakeholders)} stakeholder group(s) touched"
        ),
        "",
    ]

    lines.append(ui.bold(f"Blast radius ({len(report.elements)}):"))
    lines.append(f"  {ui.cyan('{:<38}'.format(report.scope))} {ui.dim('the change itself')}")
    for hop in report.affected:
        label = "{:<38}".format(hop.element)
        lines.append(
            f"  {ui.cyan(label)} {ui.dim(f'{hop.distance} hop(s) via {hop.kind} {hop.via} from {hop.frm}')}"
        )
    lines.append("")

    lines.append(ui.bold(f"Stakeholder groups touched ({len(report.stakeholders)}):"))
    for stakeholder in report.stakeholders:
        lines.append(f"  {ui.bold(stakeholder['name'])} {ui.dim('via ' + ', '.join(stakeholder['concerns']))}")
    if not report.stakeholders:
        lines.append(
            ui.dim("  none -- no view showing an affected element frames a held concern. "
                   "That may be a gap in the views rather than an absence of impact.")
        )
    lines.append("")

    for title, rows, formatter in (
        (
            "Decisions naming affected elements",
            report.decisions,
            lambda r: f"  {ui.bold(r['id'])} {ui.dim(r['status'])} -- {r['title']} ({r['elements']})",
        ),
        (
            "Obligations binding affected elements",
            report.obligations,
            lambda r: f"  {ui.bold(r['id'])} {ui.dim(r['type'])} -- {r['name']} (binds {r['binds']})",
        ),
        (
            "Open dispensations in the radius",
            report.dispensations,
            lambda r: f"  {ui.bold(r['id'])} waives {r['waives']} until {r['expires']}",
        ),
        (
            "Consumers who asked about these elements",
            report.demand,
            lambda r: f"  {ui.bold(r['id'])} {ui.dim(r['status'])} -- {r['requestedBy']} ({r['elements']})",
        ),
        (
            "Standards the affected elements are built on",
            report.standards,
            lambda r: "  {} {} {}".format(
                ui.bold("{:<38}".format(r["element"])), r["standard"], ui.dim(r["lifecycle"])
            ),
        ),
        (
            "Adjacent by association (direction unknown, not traversed)",
            report.adjacent,
            # str.format, not a nested f-string: quoting a dict key inside an f-string
            # expression is a 3.12+ syntax, and this package supports 3.11.
            lambda r: "  {} {}".format(
                ui.cyan(r["element"]),
                ui.dim("via {} {} from {}".format(r["kind"], r["via"], r["from"])),
            ),
        ),
    ):
        if rows:
            lines.append(ui.bold(f"{title} ({len(rows)}):"))
            lines += [formatter(row) for row in rows]
            lines.append("")

    if report.unowned:
        lines.append(
            ui.yellow(
                f"{len(report.unowned)} affected element(s) have no owner: {', '.join(report.unowned)} "
                "-- nobody to consult about the change."
            )
        )
        lines.append("")

    verdict = (
        ui.red(f"{len(report.stakeholders)} stakeholder group(s) >= {REARCHITECTING_STAKEHOLDERS}: "
               "re-architecting by the Phase H test")
        if len(report.stakeholders) >= REARCHITECTING_STAKEHOLDERS
        else ui.green(f"{len(report.stakeholders)} stakeholder group(s) < {REARCHITECTING_STAKEHOLDERS}: "
                      "the stakeholder test does not force re-architecting")
    )
    lines += [
        ui.bold("Phase H triage -- the arithmetic half:"),
        f"  {verdict}",
        ui.dim(
            "  Not evaluated here: whether the change invalidates a recorded assumption, "
            "decision or capability boundary. That test is judgement; ea-change-triage owns "
            "it, and a class is a recorded decision, not a command's exit code."
        ),
    ]
    return "\n".join(lines)
