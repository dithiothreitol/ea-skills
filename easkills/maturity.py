"""Architecture-practice maturity, from measured signals only (the `maturity` command).

Five dimensions, each scored 1-5 against **thresholds written down in a table and pinned
by a test** (`docs/CLI.md`). No questionnaire, no self-assessment, and above all **no
composite number**: a single "we are a 3.4" is how maturity becomes theatre, because it
can be moved by the cheapest dimension and it hides which one moved. The output is a
level per dimension plus the *named items* blocking the next one -- the list is the
deliverable, the level is the headline.

Three properties make the levels honest rather than decorative:

* **Every signal already exists.** Evidence share, expiring waivers, ISO clause results,
  source and reference coverage, staleness and ownership are all computed elsewhere and
  gated elsewhere. This report reads them; it defines nothing new to measure, so a level
  cannot rise without something the rest of the tooling also agrees improved.
* **Level 1 is "measured", not "bad".** A repository that has just started scores 1 and
  is not failing anything. The gates begin at level 2.
* **Unmeasurable is not satisfied.** Reference coverage with no reference pack is `None`,
  and the gate it guards stays shut with "no pack, so this cannot be measured" as the
  blocker. Scoring level 5 for owning no yardstick is the vacuous-100% trap `align`
  already refuses; it would be worse here, because maturity is the number that travels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from . import alignment, dsl, govern, intake, reports, ui

LEVELS = {
    1: "measured",
    2: "started",
    3: "managed",
    4: "governed",
    5: "sustained",
}

SHARE = "share"
COUNT = "count"


@dataclass(frozen=True)
class Gate:
    """One threshold, and the level it unlocks."""

    level: int
    metric: str
    minimum: float | None = None
    maximum: float | None = None

    def satisfied(self, value: float | None) -> bool:
        if value is None:
            return False  # unmeasurable is never satisfied -- see the module docstring
        if self.minimum is not None and value < self.minimum:
            return False
        if self.maximum is not None and value > self.maximum:
            return False
        return True

    @property
    def threshold(self) -> str:
        if self.minimum is not None:
            return f">= {self.minimum:g}"
        return f"<= {self.maximum:g}"


@dataclass(frozen=True)
class Dimension:
    key: str
    title: str
    question: str
    gates: tuple[Gate, ...]


# The single definition of the ladder. `docs/CLI.md` carries the same twenty rows and a
# test compares the two, so a threshold cannot be changed in code without the sentence
# that explains it moving with it -- the constants-versus-doc pattern `impact` uses for
# REARCHITECTING_STAKEHOLDERS.
DIMENSIONS: tuple[Dimension, ...] = (
    Dimension(
        "evidence",
        "Evidence",
        "How much of the model is traceable to a source rather than asserted?",
        (
            Gate(2, "evidencedShare", minimum=0.50),
            Gate(3, "evidencedShare", minimum=0.75),
            Gate(4, "evidencedShare", minimum=0.90),
            Gate(5, "evidencedShare", minimum=0.98),
        ),
    ),
    Dimension(
        "governance",
        "Governance",
        "Are the exceptions bounded, the standards live, and the decisions written down?",
        (
            Gate(2, "expiredDispensations", maximum=0),
            Gate(3, "uncoveredDeadStandardRefs", maximum=0),
            Gate(4, "decisionsRecorded", minimum=1),
            Gate(5, "assessmentsWithoutFollowUp", maximum=0),
        ),
    ),
    Dimension(
        "documentation",
        "Documentation",
        "Does the description satisfy the standard it claims, and does its loop close?",
        (
            Gate(2, "isoClausesPassed", minimum=4),
            Gate(3, "isoClausesFailed", maximum=0),
            Gate(4, "openIsoLoopItems", maximum=0),
            Gate(5, "isoClauseGaps", maximum=0),
        ),
    ),
    Dimension(
        "coverage",
        "Coverage",
        "Did we model what we were told, and what a business like this has?",
        (
            Gate(2, "sourceCoverage", minimum=0.50),
            Gate(3, "sourceCoverage", minimum=0.80),
            Gate(4, "sourceCoverage", minimum=1.0),
            # The only cross-yardstick gate, and the only one that can be unmeasurable.
            Gate(5, "referenceCoverage", minimum=0.80),
        ),
    ),
    Dimension(
        "operations",
        "Operations",
        "Is the content owned, and is anyone re-reading it?",
        (
            Gate(2, "ownedShare", minimum=0.50),
            Gate(3, "ownedShare", minimum=1.0),
            Gate(4, "staleShare", maximum=0.20),
            Gate(5, "staleShare", maximum=0.0),
        ),
    ),
)

BY_KEY = {dimension.key: dimension for dimension in DIMENSIONS}


@dataclass
class Metric:
    key: str
    value: float | None
    unit: str
    label: str
    items: list[str] = field(default_factory=list)
    unmeasurable: str = ""  # why, when `value` is None
    population: int | None = None  # what the value was computed over

    def rendered(self) -> str:
        if self.value is None:
            return "not measurable"
        return f"{self.value:.0%}" if self.unit == SHARE else f"{self.value:g}"


@dataclass
class DimensionResult:
    dimension: Dimension
    level: int
    next_gate: Gate | None
    metric: Metric | None

    @property
    def blockers(self) -> list[str]:
        return list(self.metric.items) if self.metric else []

    def as_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension.key,
            "title": self.dimension.title,
            "level": self.level,
            "label": LEVELS[self.level],
            "nextLevel": self.next_gate.level if self.next_gate else None,
            "blockedBy": (
                {
                    "metric": self.next_gate.metric,
                    "threshold": self.next_gate.threshold,
                    "observed": self.metric.rendered() if self.metric else None,
                    "unmeasurable": self.metric.unmeasurable if self.metric else "",
                    "items": self.blockers,
                }
                if self.next_gate
                else None
            ),
        }


@dataclass
class MaturityReport:
    root: Path
    as_of: str
    results: list[DimensionResult] = field(default_factory=list)
    metrics: dict[str, Metric] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Always true. A level is a description, not a verdict -- nothing here is a
        defect, and a maturity report that failed a build would be switched off."""
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "asOf": self.as_of,
            # Deliberately no aggregate. See the module docstring: one number is how
            # maturity stops describing anything.
            "dimensions": [result.as_dict() for result in self.results],
            "metrics": {
                key: {
                    "value": metric.value,
                    "unit": metric.unit,
                    "label": metric.label,
                    "items": metric.items,
                    "unmeasurable": metric.unmeasurable,
                }
                for key, metric in sorted(self.metrics.items())
            },
        }

    def render(self) -> str:
        lines = [
            ui.bold(f"Architecture maturity as of {self.as_of} at {self.root}"),
            ui.dim("  five dimensions, no composite -- a single number hides which one moved"),
            "",
        ]
        for result in self.results:
            bar = "#" * result.level + "." * (5 - result.level)
            lines.append(
                f"  {ui.bold('{:<14}'.format(result.dimension.title))} "
                f"{ui.cyan(bar)} {result.level}/5 {ui.dim(LEVELS[result.level])}"
            )
            if result.next_gate is None:
                continue
            metric = result.metric
            observed = metric.rendered() if metric else "?"
            reason = metric.unmeasurable if metric and metric.unmeasurable else ""
            detail = reason or (
                f"{result.next_gate.metric} {observed}, needs {result.next_gate.threshold}"
            )
            lines.append(f"      {ui.yellow(f'to reach {result.next_gate.level}')}: {ui.dim(detail)}")
            if result.blockers:
                shown = ", ".join(result.blockers[:6])
                more = f" (+{len(result.blockers) - 6} more)" if len(result.blockers) > 6 else ""
                lines.append(f"      {ui.dim('blocked by: ' + shown + more)}")
        lines += [
            "",
            ui.dim(
                "The named lists are the deliverable; the levels are the headline. Nothing here "
                "is an error -- a young repository scores 1 and is failing nothing."
            ),
            "",
            ui.verdict(True, 0, 0),
        ]
        return "\n".join(lines)


# ------------------------------------------------------------------------ the signals


def _parse(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _metric(
    key: str,
    value: float,
    unit: str,
    label: str,
    items: list[str],
    population: int,
    nothing: str,
) -> Metric:
    """A metric, or an honest `None` when its population is empty.

    **The first output of this report told an empty repository it was `sustained` on
    Evidence and Operations**, because a share over nothing is 1.0 and a count of
    problems over nothing is 0. That is the vacuous-100% trap arriving in the one report
    where it does most damage: a maturity level is the number that leaves the repository
    and goes into a slide. An empty population is now unmeasurable, the gate stays shut,
    and the blocker says which apparatus does not exist yet.
    """
    if population == 0:
        return Metric(key, None, unit, label, [], unmeasurable=nothing, population=0)
    return Metric(key, value, unit, label, items, population=population)


def measure(root: Path, today: date) -> dict[str, Metric]:
    """Read every signal the ladder scores. Nothing is computed twice: each value comes
    from the report that already owns it, so a level cannot disagree with its gate."""
    model, _documents, _config = dsl.load(root, "approved")
    governance = govern.load(root)
    kpi = reports.kpi(root, today=today)
    conformance = reports.conformance(root, today=today)
    stale = reports.staleness(root, today=today)

    concepts = list(model.elements.values()) + list(model.relationships.values())
    metrics: dict[str, Metric] = {
        "evidencedShare": _metric(
            "evidencedShare",
            kpi["evidence"]["evidencedShare"],
            SHARE,
            "concepts carrying provenance rather than an assumption",
            sorted(c.id for c in concepts if not c.provenance),
            len(concepts),
            "nothing is modelled yet, so there is no evidence share to measure",
        )
    }

    expired = sorted(
        d.id
        for d in governance.dispensations.values()
        if d.status != "closed" and (_parse(d.expires) is None or _parse(d.expires) < today)
    )
    metrics["expiredDispensations"] = _metric(
        "expiredDispensations",
        len(expired),
        COUNT,
        "waivers past their expiry and still open",
        expired,
        len(governance.dispensations),
        "no dispensations recorded -- 'none expired' would be true of a repository with no governance",
    )

    dead = {s.id for s in governance.standards.values() if s.lifecycle in {"deprecated", "retired"}}
    uncovered = sorted(
        element.id
        for element in model.elements.values()
        for ref in element.standards
        if ref in dead and governance.covering(element.id, ref, today) is None
    )
    metrics["uncoveredDeadStandardRefs"] = _metric(
        "uncoveredDeadStandardRefs",
        len(uncovered),
        COUNT,
        "elements on a deprecated or retired standard with no waiver",
        uncovered,
        len(governance.standards),
        "no standards base -- nothing can be on a dead standard because nothing is on any",
    )
    # No population guard: this gate asks for at least one decision, so zero records
    # already fails it. Nothing is claimed vacuously.
    metrics["decisionsRecorded"] = Metric(
        "decisionsRecorded", len(governance.decisions), COUNT, "architecture decision records", []
    )
    open_assessments = sorted(
        a.id
        for a in governance.assessments.values()
        if a.verdict == "non-conformant" and not a.follow_up
    )
    metrics["assessmentsWithoutFollowUp"] = _metric(
        "assessmentsWithoutFollowUp",
        len(open_assessments),
        COUNT,
        "non-conformant assessments with nothing recorded to follow",
        open_assessments,
        len(governance.assessments),
        "no compliance assessments -- nothing has been checked, so nothing is following up",
    )

    failed = sorted(i["clause"] for i in conformance["items"] if i["status"] == "fail")
    gaps = sorted(i["clause"] for i in conformance["items"] if i["status"] == "gap")
    metrics["isoClausesPassed"] = Metric(
        "isoClausesPassed", conformance["passed"], COUNT, "ISO 42010 Clause 6 checks passing", failed + gaps
    )
    metrics["isoClausesFailed"] = Metric(
        "isoClausesFailed", conformance["failed"], COUNT, "ISO 42010 Clause 6 checks failing", failed
    )
    metrics["isoClauseGaps"] = Metric(
        "isoClauseGaps",
        conformance["gaps"],
        COUNT,
        "ISO 42010 clauses this tooling cannot check and nothing else answers",
        gaps,
    )
    loop = sorted(
        set(kpi["documentation"]["unheldConcerns"]) | set(kpi["documentation"]["unframedConcerns"])
    )
    metrics["openIsoLoopItems"] = _metric(
        "openIsoLoopItems",
        len(loop),
        COUNT,
        "concerns nobody holds, or that no view frames",
        loop,
        kpi["documentation"]["concerns"],
        "no concerns declared -- a closed loop over nothing is not a closed loop",
    )

    coverage = intake.coverage(root)
    sentences = sum(f.sentences for f in coverage.files)
    metrics["sourceCoverage"] = _metric(
        "sourceCoverage",
        coverage.ratio,
        SHARE,
        "substantive source statements some fact cites",
        sorted(f.file for f in coverage.files if f.covered < f.sentences),
        sentences,
        "no source documents -- there is nothing whose coverage could be measured",
    )

    metrics["referenceCoverage"] = _reference_coverage(root)

    metrics["ownedShare"] = _metric(
        "ownedShare",
        kpi["governance"]["ownedShare"],
        SHARE,
        "elements with a named owner",
        sorted(e.id for e in model.elements.values() if not e.owner),
        len(model.elements),
        "no elements -- ownership of nothing is not ownership",
    )
    metrics["staleShare"] = _metric(
        "staleShare",
        kpi["governance"]["staleShare"],
        SHARE,
        "elements past the staleness threshold or never reviewed",
        sorted(r["id"] for r in stale["rows"] if r["state"] != "fresh"),
        len(model.elements),
        "no elements -- nothing can be stale because nothing is there",
    )
    return metrics


def _reference_coverage(root: Path) -> Metric:
    """Reference coverage, or an honest `None`.

    `None` when there is no usable pack, and the gate stays shut. Reporting 100% for a
    repository that owns no yardstick would hand out the top level for having measured
    nothing -- the same trap `--min-coverage` refuses to pass vacuously.
    """
    try:
        report = alignment.align(root, zone="approved")
    except alignment.AlignmentError:
        return Metric(
            "referenceCoverage", None, SHARE, "reference nodes answered", [],
            unmeasurable="the reference packs could not be read",
        )
    usable = [pack for pack in report.packs if not pack.refused and pack.ratio is not None]
    if not usable:
        return Metric(
            "referenceCoverage", None, SHARE, "reference nodes answered", [],
            unmeasurable="no reference pack, so there is no second yardstick to score against",
        )
    # Unweighted mean across packs: a pack is a yardstick somebody chose, and weighting
    # by node count would let a large taxonomy drown a small, more relevant one.
    ratio = sum(pack.ratio for pack in usable) / len(usable)
    # Gaps *and* partials: both are what a run to raise this number would work on, and a
    # blocker list holding only gaps reads as "nothing to do" for a repository whose
    # shortfall is entirely half-credits -- which is exactly the worked example's shape.
    short = sorted(
        node.id
        for pack in usable
        for node in pack.nodes
        if node.status in {alignment.STATUS_GAP, alignment.STATUS_PARTIAL}
    )
    return Metric("referenceCoverage", ratio, SHARE, "reference nodes answered", short)


def assess(root: Path, today: date | None = None) -> MaturityReport:
    today = today or date.today()
    metrics = measure(root, today)
    report = MaturityReport(root=root, as_of=today.isoformat(), metrics=metrics)
    for dimension in DIMENSIONS:
        level = 1
        blocking: Gate | None = None
        for gate in dimension.gates:
            if gate.satisfied(metrics[gate.metric].value):
                level = gate.level
                continue
            blocking = gate
            break
        report.results.append(
            DimensionResult(
                dimension=dimension,
                level=level,
                next_gate=blocking,
                metric=metrics[blocking.metric] if blocking else None,
            )
        )
    return report
