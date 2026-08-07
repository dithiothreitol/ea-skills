"""Per-layer definition of done (the RDY family).

"Is the application layer finished?" used to be answerable only by an architect's
feeling. This is the mechanical half: a checklist per ArchiMate layer, each item a rule
that **names the elements failing it**.

Three design commitments, each paid for by an earlier defect in this repository:

* **Every finding names its items.** The 0.11.0 scorer lesson: a count without names is
  a hand-diff waiting to happen. Three separate investigations of a fallen category were
  exactly that before the scorer started naming things.
* **Nothing here is an error.** A layer that is not finished is not a *wrong* model, and
  a report that blocked a commit for incompleteness would be switched off in a week.
  `--strict` is how a repository that claims completeness opts into the gate.
* **An empty layer is shown, never flagged.** A repository that has not started the
  technology layer is not breaking it -- the same rule that keeps `PLAT005` silent when
  there are no plateaus. The layer table prints `empty` so the shape is visible without
  inventing a finding for it.

What this is *not*: a quality judgement. Every checkpoint here is about whether the
model records something, not whether what it records is right. The judgement half lives
in `ea-model` and `ea-capability-map` under "When is this layer done".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import dsl, facts as facts_mod, oracle, reference as reference_mod, ui
from .validate import SEVERITY_INFO, SEVERITY_WARNING, Finding

# Layers in reading order; the report iterates this, so a layer cannot be silently
# dropped from the checklist by being forgotten in one function.
LAYERS = ("Strategy", "Business", "Application", "Technology", "Motivation")

# Relationship types that count as "this element realizes that one". Assignment is
# included for Strategy because a Resource is *assigned* to a Capability rather than
# realizing it -- the matrix says so, and a checklist that ignored it would report a
# properly modelled capability as unsupported.
REALIZING = frozenset({"Realization", "Assignment"})

# Structural containment. A part contributes through its whole: the worked example's
# `PostgreSQL 16` is composed into the ERP application server, and the server is what
# serves the ERP. Writing this checklist without containment reported that -- correct,
# idiomatic ArchiMate -- as unfinished technology, which is how a readiness report earns
# a reputation for noise and gets ignored.
CONTAINMENT = frozenset({"Composition", "Aggregation"})

# `topics:` values the fact register uses that name an ArchiMate layer. Topics are free
# tags by schema, so anything unrecognised is ignored rather than guessed at: `risk` and
# `integration` are real topics in the golden set and neither is a layer.
TOPIC_LAYERS: dict[str, str] = {
    "strategy": "Strategy",
    "capability": "Strategy",
    "business": "Business",
    "process": "Business",
    "application": "Application",
    "data": "Application",
    "technology": "Technology",
    "infrastructure": "Technology",
    "motivation": "Motivation",
    "requirement": "Motivation",
}

MOTIVATION_OBLIGATIONS = frozenset({"Requirement", "Constraint"})
ACTOR_TYPES = frozenset({"BusinessActor", "BusinessRole"})
SERVICE_TYPES = frozenset({"ApplicationService"})
PROCESS_TYPES = frozenset({"BusinessProcess", "BusinessFunction"})
NODE_TYPES = frozenset({"Node", "Device", "SystemSoftware"})

# Property an architect records a known weakness under (`ea-capability-map`'s idiom).
ASSESSMENT_PROPERTY = "assessment"


@dataclass
class LayerReadiness:
    layer: str
    elements: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.elements

    def as_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "elements": len(self.elements),
            "empty": self.empty,
            "findings": [f.as_dict() for f in self.findings],
        }


@dataclass
class ReadinessReport:
    root: Path
    zone: str
    layers: list[LayerReadiness] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_WARNING]

    @property
    def infos(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_INFO]

    @property
    def ok(self) -> bool:
        """Always true: nothing here is an error. Kept so the report reads like the
        others rather than tempting a caller to invent its own verdict."""
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "zone": self.zone,
            "ok": self.ok,
            "counts": self.counts,
            "summary": {
                "errors": 0,
                "warnings": len(self.warnings),
                "info": len(self.infos),
            },
            "layers": [layer.as_dict() for layer in self.layers],
            "findings": [f.as_dict() for f in self.findings],
        }

    def render(self) -> str:
        lines = [
            ui.bold(f"Layer readiness -- zone '{self.zone}' at {self.root}"),
            ui.dim(
                f"{self.counts.get('elements', 0)} elements across {len(LAYERS)} checked layer(s); "
                f"{len(self.warnings)} open checkpoint(s)"
            ),
            "",
        ]
        for layer in self.layers:
            if layer.empty:
                lines.append(f"  {ui.dim(f'{layer.layer:<12}')} {ui.dim('empty -- nothing modelled here yet')}")
                continue
            state = (
                ui.green(f"{ui.check()} complete")
                if not layer.findings
                else ui.yellow(f"{len(layer.findings)} open")
            )
            lines.append(f"  {ui.bold(f'{layer.layer:<12}')} {len(layer.elements)} element(s), {state}")
            for finding in layer.findings:
                lines.append(f"      {ui.severity(f'{finding.severity.upper():<7}')} {ui.bold(finding.code)}  "
                             f"{ui.cyan(finding.concept)}")
                lines.append(f"              {finding.message}")
        cross = [f for f in self.findings if f.code == "RDY010"]
        if cross:
            lines.append("")
            lines.append(ui.bold("Across layers"))
            for finding in cross:
                lines.append(f"      {ui.severity(f'{finding.severity.upper():<7}')} {ui.bold(finding.code)}")
                lines.append(f"              {finding.message}")
        lines += [
            "",
            ui.dim(
                "Nothing here is an error: an unfinished layer is not a wrong model. "
                "`--strict` is how a repository that claims completeness gates on it. "
                "Whether what is recorded is *right* is the judgement half -- see ea-model."
            ),
            "",
            ui.verdict(True, 0, len(self.warnings)),
        ]
        return "\n".join(lines)


def _rel(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


@dataclass(frozen=True)
class _Graph:
    """The adjacency the checkpoints ask about, computed once."""

    incoming: dict[str, set[str]]  # element id -> relationship types arriving
    outgoing: dict[str, set[str]]  # element id -> relationship types leaving
    realizes: dict[str, set[str]]  # element id -> ids it realizes/is assigned to
    realized_by: dict[str, set[str]]  # element id -> ids realizing/assigned to it
    served: dict[str, set[str]]  # element id -> ids it serves
    associated_types: dict[str, set[str]]  # element id -> types of elements it is linked to
    contained_in: dict[str, set[str]]  # element id -> ids that compose/aggregate it

    def contributes(self, element_id: str) -> bool:
        """Whether this element, or a whole it is part of, serves or realizes anything.

        Walked upwards and cycle-guarded: `REL002` forbids containment cycles, but a
        report must not hang on the model it is reporting about.
        """
        seen: set[str] = set()
        frontier = [element_id]
        while frontier:
            current = frontier.pop()
            if current in seen:
                continue
            seen.add(current)
            if self.served.get(current) or self.realizes.get(current):
                return True
            frontier.extend(self.contained_in.get(current, ()))
        return False


def _graph(model: dsl.Model) -> _Graph:
    incoming: dict[str, set[str]] = {}
    outgoing: dict[str, set[str]] = {}
    realizes: dict[str, set[str]] = {}
    realized_by: dict[str, set[str]] = {}
    served: dict[str, set[str]] = {}
    associated: dict[str, set[str]] = {}
    contained: dict[str, set[str]] = {}
    for relationship in model.relationships.values():
        source, target = relationship.source, relationship.target
        if source not in model.elements or target not in model.elements:
            continue  # REF001 is the gate's business; a dangling edge proves nothing here
        outgoing.setdefault(source, set()).add(relationship.type)
        incoming.setdefault(target, set()).add(relationship.type)
        associated.setdefault(source, set()).add(model.elements[target].type)
        associated.setdefault(target, set()).add(model.elements[source].type)
        if relationship.type in REALIZING:
            realizes.setdefault(source, set()).add(target)
            realized_by.setdefault(target, set()).add(source)
        if relationship.type == "Serving":
            served.setdefault(source, set()).add(target)
        if relationship.type in CONTAINMENT:
            contained.setdefault(target, set()).add(source)
    return _Graph(incoming, outgoing, realizes, realized_by, served, associated, contained)


def _has_recorded_gap(element: dsl.Element, model: dsl.Model, graph: _Graph) -> bool:
    """Whether the model already *records* that this capability is not supported.

    Two idioms count, because both are taught: the `assessment:` property
    (`ea-capability-map`: "record the weakness as a property ... not as a missing
    element") and an associated `Gap` or `Assessment` element. A capability whose
    weakness is written down is examined, and RDY001 is about the unexamined ones.
    """
    if element.properties.get(ASSESSMENT_PROPERTY, "").strip():
        return True
    return bool({"Gap", "Assessment"} & graph.associated_types.get(element.id, set()))


def analyse(root: Path, zone: str = "approved") -> ReadinessReport:
    """Per-layer readiness of the model in ``zone``."""
    if zone not in dsl.ZONES:
        raise ValueError(f"unknown zone '{zone}'")
    model, _documents, _config = dsl.load_zone(root, zone)
    graph = _graph(model)

    report = ReadinessReport(root=root, zone=zone)
    by_layer: dict[str, LayerReadiness] = {layer: LayerReadiness(layer=layer) for layer in LAYERS}
    for element in model.elements.values():
        layer = oracle.layer_of(element.type)
        if layer in by_layer:
            by_layer[layer].elements.append(element.id)
    for layer in by_layer.values():
        layer.elements.sort()

    findings: list[Finding] = []
    findings += _strategy(root, model, graph, zone)
    findings += _business(root, model, graph)
    findings += _application(root, model, graph)
    findings += _technology(root, model, graph)
    findings += _motivation(root, model)
    cross = _cross_layer(root, model, by_layer)

    for finding in findings:
        element = model.elements.get(finding.concept)
        layer = oracle.layer_of(element.type) if element is not None else "Other"
        if layer in by_layer:
            by_layer[layer].findings.append(finding)
    for layer in by_layer.values():
        layer.findings.sort(key=lambda f: (f.code, f.concept, f.message))

    report.layers = [by_layer[layer] for layer in LAYERS]
    # `message` is in the key so ties cannot fall back on dict order: RDY010 carries no
    # concept, and byte-stable output is a tested property of every report here.
    report.findings = sorted(findings + cross, key=lambda f: (f.code, f.concept, f.message))
    report.counts = {
        "elements": len(model.elements),
        "relationships": len(model.relationships),
        "checkpointsOpen": sum(1 for f in report.findings if f.severity == SEVERITY_WARNING),
    }
    return report


def _finding(code: str, severity: str, message: str, root: Path, element: dsl.Element) -> Finding:
    return Finding(
        code,
        severity,
        message,
        file=_rel(root, element.source_path),
        locator=element.locator,
        concept=element.id,
    )


def _sorted(model: dsl.Model, types: frozenset[str] | set[str]) -> list[dsl.Element]:
    return sorted((e for e in model.elements.values() if e.type in types), key=lambda e: e.id)


def _strategy(root: Path, model: dsl.Model, graph: _Graph, zone: str) -> list[Finding]:
    findings: list[Finding] = []
    packs = _reference_nodes(root)
    for capability in _sorted(model, {"Capability"}):
        if not graph.realized_by.get(capability.id) and not _has_recorded_gap(capability, model, graph):
            findings.append(
                _finding(
                    "RDY001",
                    SEVERITY_WARNING,
                    f"nothing realizes '{capability.name}' and the model records no gap or "
                    "assessment for it -- either an application/process realizes it and the edge "
                    f"is missing, or the weakness is real and belongs in properties "
                    f"({ASSESSMENT_PROPERTY}:) or as a Gap element",
                    root,
                    capability,
                )
            )
        if packs is not None and capability.id not in packs:
            findings.append(
                _finding(
                    "RDY002",
                    SEVERITY_INFO,
                    f"'{capability.name}' is not mapped to any reference node -- a local capability "
                    "the reference does not anchor, which is usually the business doing something "
                    "its blueprint never heard of. Confirm it is that, and not a mapping nobody wrote",
                    root,
                    capability,
                )
            )
    return findings


def _reference_nodes(root: Path) -> set[str] | None:
    """Element ids any reference mapping anchors, or ``None`` when no pack exists.

    ``None`` rather than an empty set on purpose: with no reference model there is no
    question to answer, and RDY002 must stay silent rather than report every capability.
    A refused pack (ALN001) counts as no pack -- `align` is where that is reported, and
    reporting an unverified taxonomy's absence as a readiness gap would be a second,
    quieter place for the same failure.
    """
    packs = reference_mod.load(root)
    usable = [pack for pack in packs if not pack.refused and pack.nodes]
    if not usable:
        return None
    return {
        element_id
        for pack in usable
        for mapping in pack.mappings
        for element_id in mapping.elements
    }


def _business(root: Path, model: dsl.Model, graph: _Graph) -> list[Finding]:
    findings: list[Finding] = []
    for process in _sorted(model, PROCESS_TYPES):
        anchors = graph.realizes.get(process.id, set())
        anchored = any(
            model.elements[target].type in {"Capability", "BusinessService", "ApplicationService"}
            for target in anchors
            if target in model.elements
        )
        if not anchored:
            findings.append(
                _finding(
                    "RDY003",
                    SEVERITY_WARNING,
                    f"'{process.name}' realizes no capability and no service -- a process that "
                    "attaches to neither cannot be read as delivering anything, and will not "
                    "appear in any portfolio or capability view",
                    root,
                    process,
                )
            )
    for actor in _sorted(model, ACTOR_TYPES):
        if not graph.incoming.get(actor.id) and not graph.outgoing.get(actor.id) and not actor.applies_to:
            findings.append(
                _finding(
                    "RDY004",
                    SEVERITY_WARNING,
                    f"{actor.type} '{actor.name}' is attached to nothing -- assign it to the "
                    "behaviour it performs, or the service it consumes, or drop it",
                    root,
                    actor,
                )
            )
    return findings


def _application(root: Path, model: dsl.Model, graph: _Graph) -> list[Finding]:
    findings: list[Finding] = []
    for component in _sorted(model, {"ApplicationComponent"}):
        missing = [
            key for key in ("lifecycle", "timeDisposition") if not component.properties.get(key, "").strip()
        ]
        if missing:
            findings.append(
                _finding(
                    "RDY005",
                    SEVERITY_WARNING,
                    f"'{component.name}' carries no {' and no '.join(missing)} -- the application "
                    "portfolio (TIME quadrants, obsolescence exposure) is derived from these, so "
                    "the component is invisible to every portfolio report until they are set",
                    root,
                    component,
                )
            )
        if not graph.contributes(component.id):
            findings.append(
                _finding(
                    "RDY006",
                    SEVERITY_WARNING,
                    f"'{component.name}' realizes nothing -- an application that supports no "
                    "capability and publishes no service is either unmodelled work or a system "
                    "nobody can justify keeping",
                    root,
                    component,
                )
            )
    for service in _sorted(model, SERVICE_TYPES):
        if not graph.contributes(service.id):
            findings.append(
                _finding(
                    "RDY007",
                    SEVERITY_WARNING,
                    f"'{service.name}' serves nobody -- a published service with no recorded "
                    "consumer cannot be impact-assessed, and is the first thing a rationalization "
                    "review gets wrong",
                    root,
                    service,
                )
            )
    return findings


def _technology(root: Path, model: dsl.Model, graph: _Graph) -> list[Finding]:
    findings: list[Finding] = []
    for node in _sorted(model, NODE_TYPES):
        if not graph.contributes(node.id):
            findings.append(
                _finding(
                    "RDY008",
                    SEVERITY_WARNING,
                    f"{node.type} '{node.name}' serves and realizes nothing -- infrastructure "
                    "nothing runs on cannot be costed, retired or impact-assessed",
                    root,
                    node,
                )
            )
    return findings


def _motivation(root: Path, model: dsl.Model) -> list[Finding]:
    findings: list[Finding] = []
    for obligation in _sorted(model, MOTIVATION_OBLIGATIONS):
        if not obligation.applies_to:
            findings.append(
                _finding(
                    "RDY009",
                    SEVERITY_WARNING,
                    f"{obligation.type} '{obligation.name}' binds nothing (`appliesTo` absent) -- "
                    "an obligation with no bearer is a sentence in a document, and no context pack "
                    "will ever serve it to the team it was written for",
                    root,
                    obligation,
                )
            )
    return findings


def _cross_layer(root: Path, model: dsl.Model, by_layer: dict[str, LayerReadiness]) -> list[Finding]:
    """RDY010: the evidence covers a layer the model does not."""
    register, _documents, _entities = facts_mod.load(root)
    mentioned: dict[str, list[str]] = {}
    for fact in register.facts.values():
        for topic in fact.topics:
            layer = TOPIC_LAYERS.get(str(topic).strip().casefold())
            if layer:
                mentioned.setdefault(layer, []).append(fact.id)
    findings: list[Finding] = []
    for layer in LAYERS:
        fact_ids = sorted(set(mentioned.get(layer, [])))
        if not fact_ids or not by_layer[layer].empty:
            continue
        shown = ", ".join(fact_ids[:8]) + ("..." if len(fact_ids) > 8 else "")
        first = register.facts[fact_ids[0]]
        findings.append(
            Finding(
                "RDY010",
                SEVERITY_WARNING,
                f"the fact register covers the {layer} layer ({len(fact_ids)} fact(s): {shown}) "
                f"and the model holds no {layer} element -- evidence was gathered and never "
                "modelled, which is the one kind of incompleteness the sources can prove",
                file=_rel(root, first.source_path),
            )
        )
    return findings
