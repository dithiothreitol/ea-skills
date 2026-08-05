"""ISO/IEC/IEEE 42010:2022 §6.9 -- correspondences and correspondence rules.

A correspondence relates AD elements to one another; a correspondence rule is what that
relation has to satisfy. This repository was full of correspondences before it had the
word for them: a decision record names the elements it decides, a requirement names what
it binds, an element names the standards it follows, a concept names the facts that
evidence it. Every one of those crosses a boundary no ArchiMate relationship can reach
across -- into the governance log, into the fact register -- which is exactly the space
the clause is for. Inside the model, a relation between two elements is a *relationship*,
and the oracle already governs it.

So correspondences are **derived, never authored twice**. Asking an author to restate
`relatedElements` as a correspondence record would buy conformance with duplication, and
the two copies would drift apart within a quarter -- the failure this whole repository
exists to prevent. What is added here is the half that was actually missing: each
correspondence is named, held to a stated rule, and two rules that nothing checked before
now fail out loud:

* ``CORR001`` -- the architecture still realises a decision the governance log retired.
* ``CORR002`` -- an obligation whose only bearers are slated for elimination.

The remaining kinds cite the rule code that already enforces them, so the correspondence
table doubles as a map of which gate holds which relation together. That is deliberate:
a clause is not implemented by inventing new checks for relations that are already
checked, and pretending otherwise would be the decorative conformance this tooling
refuses everywhere else.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from . import oracle
from .validate import SEVERITY_WARNING, Finding

if TYPE_CHECKING:  # pragma: no cover -- imports for typing only, so no cycle at runtime
    from . import dsl, govern

# The TIME quadrant that makes an element a temporary bearer of anything.
ELIMINATE = "Eliminate"


@dataclass(frozen=True)
class Rule:
    """One correspondence rule: what relates to what, and what must hold of it.

    ``enforced_by`` is the honest part. A rule whose code is not ``CORR*`` is checked
    elsewhere in the gate, and saying so is more useful than duplicating the check.
    """

    kind: str
    source_kind: str
    target_kind: str
    statement: str
    enforced_by: tuple[str, ...]


RULES: tuple[Rule, ...] = (
    Rule(
        kind="realizes",
        source_kind="decision",
        target_kind="element",
        statement=(
            "The elements a decision record names realise a decision that still stands. A "
            "record that has been superseded, rejected or deprecated no longer describes "
            "the architecture, and elements pointing at one are drift the governance log "
            "cannot see."
        ),
        enforced_by=("CORR001", "DEC005"),
    ),
    Rule(
        kind="binds",
        source_kind="motivation element",
        target_kind="element",
        statement=(
            "A requirement, constraint, principle or goal binds elements that exist and can "
            "still carry it. An obligation whose only bearers are slated for elimination "
            "outlives the systems that meet it -- the retention requirement nobody notices "
            "until the system holding the records is switched off."
        ),
        enforced_by=("CORR002", "MOT001", "MOT002"),
    ),
    Rule(
        kind="governed-by",
        source_kind="element",
        target_kind="standard",
        statement=(
            "An element's standards reference resolves to a SIB entry that is not retired, "
            "unless an open dispensation covers the pair."
        ),
        enforced_by=("STD001", "STD002", "STD004"),
    ),
    Rule(
        kind="assessed-by",
        source_kind="compliance assessment",
        target_kind="element",
        statement="A compliance assessment names elements that are in the approved model.",
        enforced_by=("COMP005",),
    ),
    Rule(
        kind="evidenced-by",
        source_kind="concept",
        target_kind="fact",
        statement=(
            "A model concept's provenance resolves to a fact in the register whose quotes "
            "are located mechanically in their sources -- or the concept declares itself "
            "assumed, with a rationale."
        ),
        enforced_by=("PROV007", "PROV003", "PROV001"),
    ),
)

RULE_BY_KIND: dict[str, Rule] = {rule.kind: rule for rule in RULES}


@dataclass(frozen=True)
class Correspondence:
    """One derived relation between two AD elements, with its verdict."""

    kind: str
    source: str
    target: str
    satisfied: bool = True
    detail: str = ""
    code: str = ""  # the rule code that reports this violation
    file: str = ""  # the record the finding hangs off

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "from": self.source,
            "to": self.target,
            "satisfied": self.satisfied,
            "detail": self.detail,
            "code": self.code,
            "file": self.file,
        }


def _rel(root: Any, path: Any) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


# A decision the architecture may still realise. `proposed` is deliberately included:
# elements realising a proposal are ahead of the governance log, which is a state worth
# having, not a violation.
STANDING_DECISION_STATUSES = frozenset({"proposed", "accepted"})


def _realizes(model: dsl.Model, governance: govern.Governance) -> list[Correspondence]:
    out: list[Correspondence] = []
    for decision in sorted(governance.decisions.values(), key=lambda d: d.id):
        rel_file = _rel(governance.root, decision.source_path)
        for element_id in sorted(decision.related_elements):
            if element_id not in model.elements:
                continue  # DEC005 reports the dangling reference itself
            if decision.status and decision.status not in STANDING_DECISION_STATUSES:
                successor = f" (superseded by {decision.superseded_by})" if decision.superseded_by else ""
                out.append(
                    Correspondence(
                        kind="realizes",
                        source=decision.id,
                        target=element_id,
                        satisfied=False,
                        detail=(
                            f"'{element_id}' still realises a decision whose status is "
                            f"'{decision.status}'{successor} -- record what replaced it, or "
                            "drop the element from relatedElements"
                        ),
                        code="CORR001",
                        file=rel_file,
                    )
                )
            else:
                out.append(
                    Correspondence(kind="realizes", source=decision.id, target=element_id, file=rel_file)
                )
    return out


def _binds(model: dsl.Model) -> list[Correspondence]:
    out: list[Correspondence] = []
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        if not element.applies_to or oracle.layer_of(element.type) != "Motivation":
            continue  # MOT002 reports a selector on the wrong layer
        rel_file = _rel(model.root, element.source_path)
        bound = [model.elements[ref] for ref in sorted(set(element.applies_to)) if ref in model.elements]
        if not bound:
            continue  # MOT001 reports the dangling reference itself
        # Per-pair verdict, group-aware: one eliminated bearer among several is a plan,
        # not a gap. It becomes a gap when *every* bearer is going.
        homeless = all(b.properties.get("timeDisposition") == ELIMINATE for b in bound)
        for target in bound:
            eliminated = target.properties.get("timeDisposition") == ELIMINATE
            if homeless and eliminated:
                out.append(
                    Correspondence(
                        kind="binds",
                        source=element.id,
                        target=target.id,
                        satisfied=False,
                        detail=(
                            f"binds '{target.id}', and every element it binds is TIME "
                            f"'{ELIMINATE}' -- when they go, this obligation has no bearer "
                            "left. Bind the successor, or record the decision that retires "
                            "the obligation with them"
                        ),
                        code="CORR002",
                        file=rel_file,
                    )
                )
            else:
                out.append(
                    Correspondence(kind="binds", source=element.id, target=target.id, file=rel_file)
                )
    return out


def _governed_by(
    model: dsl.Model, governance: govern.Governance, today: date
) -> list[Correspondence]:
    out: list[Correspondence] = []
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        rel_file = _rel(model.root, element.source_path)
        for standard_id in sorted(set(element.standards)):
            standard = governance.standards.get(standard_id)
            if standard is None:
                out.append(
                    Correspondence(
                        kind="governed-by",
                        source=element.id,
                        target=standard_id,
                        satisfied=False,
                        detail=f"'{standard_id}' is not in the standards base",
                        code="STD001",
                        file=rel_file,
                    )
                )
                continue
            covered = governance.covering(element.id, standard_id, today) is not None
            if standard.lifecycle == "retired" and not covered:
                out.append(
                    Correspondence(
                        kind="governed-by",
                        source=element.id,
                        target=standard_id,
                        satisfied=False,
                        detail=f"'{standard_id}' is retired and no open dispensation covers the pair",
                        code="STD002",
                        file=rel_file,
                    )
                )
                continue
            out.append(
                Correspondence(kind="governed-by", source=element.id, target=standard_id, file=rel_file)
            )
    return out


def _assessed_by(model: dsl.Model, governance: govern.Governance) -> list[Correspondence]:
    out: list[Correspondence] = []
    for assessment in sorted(governance.assessments.values(), key=lambda a: a.id):
        rel_file = _rel(governance.root, assessment.source_path)
        for element_id in sorted(set(assessment.related_elements)):
            if element_id not in model.elements:
                continue  # COMP005 reports the dangling reference itself
            out.append(
                Correspondence(
                    kind="assessed-by", source=assessment.id, target=element_id, file=rel_file
                )
            )
    return out


def _evidenced_by(model: dsl.Model) -> list[Correspondence]:
    # The register is read here rather than passed in: it is the third artefact of this
    # AD, and a table that printed a tick beside a citation of a fact nobody wrote would
    # be worse than no table. PROV007 owns the finding; this only records the state.
    from . import facts as facts_mod

    register, _documents, _entities = facts_mod.load(model.root)
    out: list[Correspondence] = []
    concepts = list(model.elements.values()) + list(model.relationships.values())
    for concept in sorted(concepts, key=lambda c: c.id):
        rel_file = _rel(model.root, concept.source_path)
        for fact_id in sorted({p.fact for p in concept.provenance if p.fact}):
            known = fact_id in register.facts
            out.append(
                Correspondence(
                    kind="evidenced-by",
                    source=concept.id,
                    target=fact_id,
                    satisfied=known,
                    detail="" if known else f"'{fact_id}' is not in the fact register",
                    code="" if known else "PROV007",
                    file=rel_file,
                )
            )
    return out


def derive(
    model: dsl.Model, governance: govern.Governance, today: date | None = None
) -> list[Correspondence]:
    """Every correspondence this AD records, in a stable order.

    Takes loaded objects rather than a root: the governance loader already reads the
    approved model, and a second loader here would be a second chance to disagree with
    it. It also keeps this module free of imports that would close a cycle.
    """
    today = today or date.today()
    return [
        *_realizes(model, governance),
        *_binds(model),
        *_governed_by(model, governance, today),
        *_assessed_by(model, governance),
        *_evidenced_by(model),
    ]


def findings(correspondences: list[Correspondence]) -> list[Finding]:
    """Only the violations this module owns. The others are already someone's finding,
    and reporting them twice would inflate the count without adding information."""
    return [
        Finding(
            correspondence.code,
            SEVERITY_WARNING,
            correspondence.detail,
            file=correspondence.file,
            concept=correspondence.source,
        )
        for correspondence in correspondences
        if not correspondence.satisfied and correspondence.code.startswith("CORR")
    ]


def summary(correspondences: list[Correspondence]) -> dict[str, Any]:
    """Report shape: the rules first, because §6.9 asks for the rules to be recorded,
    not just the pairs they govern."""
    kinds: list[dict[str, Any]] = []
    for rule in RULES:
        of_kind = [c for c in correspondences if c.kind == rule.kind]
        kinds.append(
            {
                "kind": rule.kind,
                "relates": f"{rule.source_kind} -> {rule.target_kind}",
                "rule": rule.statement,
                "enforcedBy": list(rule.enforced_by),
                "count": len(of_kind),
                "violated": sum(1 for c in of_kind if not c.satisfied),
            }
        )
    violated = [c for c in correspondences if not c.satisfied]
    return {
        "total": len(correspondences),
        "violated": len(violated),
        "kinds": kinds,
        "items": [c.as_dict() for c in correspondences],
    }
