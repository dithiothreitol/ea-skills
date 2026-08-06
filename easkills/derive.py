"""ArchiMate derivation rules DR1-DR8: which relationships a model *implies*.

Two faithful models of one sentence can share no edge and still say the same thing. A
measured run wrote `SchedPro --Serving--> Weekend Run Planning` plus
`Dispatch --Assignment--> Weekend Run Planning` where gold wrote
`SchedPro --Serving--> Dispatch`; every endpoint matched, no relationship did, and the
score read 0%. That is not a scoring accident -- it is the specification's own
abstraction machinery being absent: gold's edge is *derivable* from the candidate's two,
by DR4, which the standard states in one sentence.

This module implements the eight rules of **Appendix B.2, "Derivation Rules for Valid
Relationships"** -- the derivations that "are certainly true in any model where these
rules apply". The potential (uncertain) derivations of B.3 are deliberately **not**
implemented: they are probabilistic by the specification's own description, and a
deterministic core has no business guessing.

Every derived relationship is filtered through the vendored relationship matrix, so the
B.4 restrictions that the matrix was built from apply for free. The one B.4 restriction a
type matrix cannot express -- *no derivation through an intermediate element in a third
domain* -- is checked explicitly here.

Nothing in this module validates or repairs a model. It answers one question, for the
scorer and for anyone who asks it: **is this relationship implied by that model, and
along which path?**
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from . import dsl, oracle

# Structural strength (B.2.2): "Realization (weakest), Assignment, Aggregation,
# Composition (strongest)". DR2 replaces a chain with the weakest link in it.
STRENGTH: dict[str, int] = {
    "Realization": 0,
    "Assignment": 1,
    "Aggregation": 2,
    "Composition": 3,
}

# B.4 groups layers into four "domains"; the location element "counts as a core element".
DOMAIN_OF_LAYER: dict[str, str] = {
    "Strategy": "Strategy",
    "Business": "Core",
    "Application": "Core",
    "Technology": "Core",
    "Physical": "Core",
    "Other": "Core",
    "Motivation": "Motivation",
    "Implementation": "Implementation",
}

# B.1: "these derivation rules do not work on relationships with grouping". Junction is a
# connector rather than an element and the specification derives nothing through it, so
# both are refused as endpoints and as intermediates instead of being guessed at.
NON_DERIVABLE_TYPES = frozenset({"Grouping", "Junction"})

# A chain of three model relationships already covers every abstraction the runs produce
# (the measured case needs two). The bound is what keeps the closure finite and cheap.
DEFAULT_MAX_DEPTH = 3
# Deterministic backstop for a pathological model: expansion stops at this many edges,
# reached in sorted order so the truncation is reproducible rather than arbitrary.
MAX_CLOSURE_EDGES = 4000


@dataclass(frozen=True)
class Rule:
    """One rule of Appendix B.2, kept as data so the report can cite it."""

    code: str
    clause: str
    statement: str


RULES: tuple[Rule, ...] = (
    Rule("DR1", "B.2.1", "Specialization is transitive."),
    Rule(
        "DR2",
        "B.2.2",
        "Two structural relationships in line combine into the weakest of the two.",
    ),
    Rule(
        "DR3",
        "B.2.3",
        "A structural relationship followed by a dependency yields that dependency: the "
        "dependency's source moves back along the structural chain.",
    ),
    Rule(
        "DR4",
        "B.2.3",
        "A structural relationship opposing a dependency yields that dependency: the "
        "dependency's target moves back along the structural chain.",
    ),
    Rule(
        "DR5",
        "B.2.4",
        "A structural relationship followed by a dynamic relationship yields that "
        "dynamic relationship.",
    ),
    Rule(
        "DR6",
        "B.2.4",
        "A structural relationship opposing a flow yields that flow, with the target "
        "moved back along the structural chain.",
    ),
    Rule(
        "DR7",
        "B.2.4",
        "A triggering relationship followed by a structural one yields a triggering "
        "relationship to the part.",
    ),
    Rule("DR8", "B.2.4", "Triggering is transitive."),
)

RULE_BY_CODE = {rule.code: rule for rule in RULES}


@dataclass(frozen=True)
class Edge:
    """A relationship reduced to what derivation cares about."""

    type: str
    source: str
    target: str


@dataclass(frozen=True)
class Derivation:
    """How an edge is implied: which rules, through which elements, using which edges."""

    edge: Edge
    rules: tuple[str, ...] = ()
    via: tuple[str, ...] = ()
    used: frozenset[str] = frozenset()

    @property
    def depth(self) -> int:
        """How many of the model's own relationships the derivation consumes."""
        return len(self.used)

    @property
    def is_derived(self) -> bool:
        return bool(self.rules)


def _is_structural(relationship_type: str) -> bool:
    return relationship_type in oracle.STRUCTURAL_RELATIONSHIPS


def _is_dependency(relationship_type: str) -> bool:
    return relationship_type in oracle.DEPENDENCY_RELATIONSHIPS


def _is_dynamic(relationship_type: str) -> bool:
    return relationship_type in oracle.DYNAMIC_RELATIONSHIPS


def _weakest(left: str, right: str) -> str:
    return left if STRENGTH[left] <= STRENGTH[right] else right


def _combine(left: Edge, right: Edge) -> Iterable[tuple[str, Edge, str]]:
    """Yield ``(rule code, derived edge, joining element)`` for every rule that fires.

    The eight rules are transcribed one for one from B.2, in the specification's own
    ``p(a,b):S`` shape, with ``left`` playing p and ``right`` playing q.
    """
    in_line = left.target == right.source
    opposed = left.target == right.target

    if in_line and left.type == "Specialization" and right.type == "Specialization":
        yield "DR1", Edge("Specialization", left.source, right.target), left.target
    if in_line and _is_structural(left.type) and _is_structural(right.type):
        yield "DR2", Edge(_weakest(left.type, right.type), left.source, right.target), left.target
    if in_line and _is_structural(left.type) and _is_dependency(right.type):
        yield "DR3", Edge(right.type, left.source, right.target), left.target
    if opposed and _is_structural(left.type) and _is_dependency(right.type):
        # r(c,a): the dependency keeps its source, its target moves to p's source.
        yield "DR4", Edge(right.type, right.source, left.source), left.target
    if in_line and _is_structural(left.type) and _is_dynamic(right.type):
        yield "DR5", Edge(right.type, left.source, right.target), left.target
    if opposed and _is_structural(left.type) and right.type == "Flow":
        yield "DR6", Edge("Flow", right.source, left.source), left.target
    if in_line and left.type == "Triggering" and _is_structural(right.type):
        yield "DR7", Edge("Triggering", left.source, right.target), left.target
    if in_line and left.type == "Triggering" and right.type == "Triggering":
        yield "DR8", Edge("Triggering", left.source, right.target), left.target


def _domain(model: dsl.Model, element_id: str) -> str:
    element = model.elements.get(element_id)
    if element is None:
        return "Core"
    return DOMAIN_OF_LAYER.get(oracle.layer_of(element.type), "Core")


def _admissible(model: dsl.Model, edge: Edge, via: tuple[str, ...]) -> bool:
    """Is this derived edge one the specification allows to exist?

    Three gates. The endpoints must be real elements the rules apply to; the derived type
    must be permitted between those two element types by the vendored matrix (which is
    where the rest of B.4 already lives); and no intermediate element may sit in a domain
    distinct from both endpoints' -- the one B.4 restriction that is a property of the
    *path*, not of the type pair.
    """
    if edge.source == edge.target:
        return False
    source = model.elements.get(edge.source)
    target = model.elements.get(edge.target)
    if source is None or target is None:
        return False
    if source.type in NON_DERIVABLE_TYPES or target.type in NON_DERIVABLE_TYPES:
        return False
    if any(
        (model.elements[i].type in NON_DERIVABLE_TYPES)
        for i in via
        if i in model.elements
    ):
        return False
    if edge.type not in oracle.allowed_relationships(source.type, target.type):
        return False
    endpoints = {_domain(model, edge.source), _domain(model, edge.target)}
    return all(_domain(model, intermediate) in endpoints for intermediate in via)


def closure(model: dsl.Model, *, max_depth: int = DEFAULT_MAX_DEPTH) -> dict[Edge, Derivation]:
    """Every relationship the model states or implies, with the shortest derivation.

    The model's own relationships are included at depth 1 (``is_derived`` false), so a
    caller can tell "you drew this" from "this follows from what you drew".
    """
    known: dict[Edge, Derivation] = {}
    for relationship in sorted(model.relationships.values(), key=lambda r: r.id):
        edge = Edge(relationship.type, relationship.source, relationship.target)
        known.setdefault(edge, Derivation(edge=edge, used=frozenset({relationship.id})))

    frontier = dict(known)
    for _round in range(max(0, max_depth - 1)):
        additions: dict[Edge, Derivation] = {}
        for left in sorted(frontier.values(), key=_order):
            for right in sorted(known.values(), key=_order):
                for pair in ((left, right), (right, left)):
                    first, second = pair
                    if first.used & second.used:
                        continue  # one relationship may not do duty twice in one chain
                    if first.depth + second.depth > max_depth:
                        continue
                    for code, edge, join in _combine(first.edge, second.edge):
                        via = first.via + (join,) + second.via
                        if edge in known or not _admissible(model, edge, via):
                            continue
                        candidate = Derivation(
                            edge=edge,
                            rules=first.rules + (code,) + second.rules,
                            via=via,
                            used=first.used | second.used,
                        )
                        current = additions.get(edge)
                        if current is None or candidate.depth < current.depth:
                            additions[edge] = candidate
        if not additions or len(known) >= MAX_CLOSURE_EDGES:
            break
        known.update(additions)
        frontier = additions
    return known


def _order(derivation: Derivation) -> tuple:
    """Total order over derivations, so the closure is byte-stable across runs."""
    return (
        derivation.depth,
        derivation.edge.type,
        derivation.edge.source,
        derivation.edge.target,
        derivation.rules,
    )


def describe(model: dsl.Model, derivation: Derivation) -> str:
    """One-line citation: the rules used and the elements abstracted away."""
    if not derivation.is_derived:
        return "stated directly"
    names = [
        model.elements[i].name if i in model.elements else i
        for i in derivation.via
    ]
    rules = "+".join(dict.fromkeys(derivation.rules))  # order-preserving de-duplication
    return "derived {rules} via {names}".format(rules=rules, names=", ".join(names))
