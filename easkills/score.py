"""Golden-set scoring: compare a candidate repository against a gold one.

The harness closes the loop the research opened: extraction quality is a measured
property, not a vibe. A skill change is evaluated by running the pipeline on a golden
case's sources into a scratch repository and scoring the result here -- precision,
recall and F1 per category, computed deterministically:

* **entities**    matched when their term sets (name + aliases, normalized) intersect;
* **facts**       matched by the *source ground they cover*: the spans their verified
                  quotes occupy in the shared sources, with statement similarity
                  deciding full or partial credit;
* **elements**    matched by (ArchiMate type, name) -- with names resolved through the
                  entity alias tables, and a type disagreement inside one layer scored
                  as half a match;
* **relationships** matched by type plus endpoints that map through element matches; an
                  edge the candidate did not draw but its model *implies* under the
                  specification's derivation rules (`derive.py`) is half a match, and a
                  label-independent structural count is reported alongside.

Candidate *quality* is not inferred from matching alone: the candidate's own gates
(model and fact-register validators) run too, because a candidate that matches gold
while failing provenance verification is a fabrication that happens to be right.

**What this score is, and is not.** It measures agreement with one gold repository, so
it is a regression signal for a change in the skills -- not an absolute grade. An
end-to-end run (2026-08-05) exposed how sharply that mattered: a model that recalled
100% of gold's elements and relationships scored 15% and **0%** because it wrote
"Electronic Health Record System" where gold wrote "EHR", and because one unmatched
element zeroes every relationship touching it. The matching below is the answer to that
run: use the knowledge the repository already has (aliases), separate a disagreement
about labels from a disagreement about content, and stop punishing a register for being
more atomic than gold.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import derive, dsl, facts as facts_mod, oracle, ui
from . import validate as validate_mod
from .validate import _normalize

FACT_MATCH_THRESHOLD = 0.85
# Two facts cover the same ground when their evidence overlaps by at least this share of
# the shorter one -- which is what makes splitting one gold fact into two atomic ones a
# match rather than a miss.
SPAN_OVERLAP_THRESHOLD = 0.5
# Credit for "found it, disagree about its label": a type difference inside one
# ArchiMate layer, or matching evidence under a diverging statement. Half, deliberately:
# the thing was located, its classification is contested.
PARTIAL_CREDIT = 0.5


@dataclass(frozen=True)
class CategoryScore:
    """Credit is asymmetric on purpose.

    One gold fact may be covered by two candidate facts, and one candidate element may
    answer a gold element under a different type. Collapsing that into a single
    ``matched`` count forced a choice between punishing the candidate for being more
    atomic and crediting it twice; keeping the two numerators apart does neither.

    Every score also carries **which items** it is about. A number alone sent every
    investigation of a fallen category back through two YAML trees by hand; the four
    label tuples below are the same information the ratio was computed from, so the
    question "what did it miss, and what did it invent" is answered by reading the report.
    """

    gold: int
    candidate: int
    matched: float  # credit on the candidate side -- the precision numerator
    matched_gold: float | None = None  # credit on the gold side; defaults to `matched`
    partial: int = 0  # how many of those credits were half (reported, never hidden)
    unmatched_gold: tuple[str, ...] = ()  # gold items that earned no credit at all
    unmatched_candidate: tuple[str, ...] = ()  # candidate items nothing in gold answers
    partial_gold: tuple[str, ...] = ()  # gold items credited half
    partial_candidate: tuple[str, ...] = ()  # candidate items credited half
    # `partial` is a count of halved *credits*, and the label tuples are a count of items:
    # a halved element is one credit and two labels (gold's type and the candidate's),
    # while a halved fact is scored once per numerator. Kept separate rather than derived,
    # because deriving it needs exactly that distinction as a hidden rule.

    @property
    def gold_credit(self) -> float:
        return self.matched if self.matched_gold is None else self.matched_gold

    @property
    def precision(self) -> float:
        return min(1.0, self.matched / self.candidate) if self.candidate else 1.0

    @property
    def recall(self) -> float:
        return min(1.0, self.gold_credit / self.gold) if self.gold else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "gold": self.gold,
            "candidate": self.candidate,
            "matched": round(self.matched, 2),
            "matchedGold": round(self.gold_credit, 2),
            "partial": self.partial,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            # Uncapped and sorted: this is the machine-readable half of the diagnosis.
            "unmatchedGold": list(self.unmatched_gold),
            "unmatchedCandidate": list(self.unmatched_candidate),
            "partialGold": list(self.partial_gold),
            "partialCandidate": list(self.partial_candidate),
        }


def _score_entities(gold: facts_mod.Register, candidate: facts_mod.Register) -> CategoryScore:
    def terms(entity: facts_mod.Entity) -> frozenset[str]:
        return frozenset({_normalize(entity.name)} | {_normalize(a) for a in entity.aliases}) - {""}

    available = {e.id: terms(e) for e in candidate.entities.values()}
    matched = 0
    missed: list[str] = []
    for gold_entity in sorted(gold.entities.values(), key=lambda e: e.id):
        gold_terms = terms(gold_entity)
        hit = next(
            (cid for cid, cterms in sorted(available.items()) if gold_terms & cterms),
            None,
        )
        if hit is not None:
            matched += 1
            del available[hit]
        else:
            missed.append(gold_entity.id)
    return CategoryScore(
        gold=len(gold.entities),
        candidate=len(candidate.entities),
        matched=matched,
        unmatched_gold=tuple(missed),
        unmatched_candidate=tuple(sorted(available)),
    )


def _alias_classes(*registers: facts_mod.Register) -> dict[str, str]:
    """Union the term sets of every entity in every register, and return term -> class.

    The repository already knows that "EHR" and "Electronic Health Record System" are
    one thing -- it is written in `facts/entities.yaml`. The scorer used to ignore that
    and compare raw element names, so two faithful models disagreed to 0%.
    """
    parent: dict[str, str] = {}

    def find(term: str) -> str:
        parent.setdefault(term, term)
        while parent[term] != term:
            parent[term] = parent[parent[term]]
            term = parent[term]
        return term

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)  # smallest term is the class representative

    for register in registers:
        for entity in register.entities.values():
            terms = [_normalize(entity.name)] + [_normalize(alias) for alias in entity.aliases]
            terms = [term for term in terms if term]
            for term in terms[1:]:
                union(terms[0], term)
    return {term: find(term) for term in parent}


def _canonical(name: str, classes: dict[str, str]) -> str:
    key = _normalize(name)
    return classes.get(key, key)


def _fact_spans(register: facts_mod.Register) -> dict[str, list[tuple[str, int, int]]]:
    """Where each fact's verified quotes sit in the normalized source text.

    Facts are judged on the ground their evidence covers, not on how many sentences
    they were split into -- the register's own discipline pushes towards atomic facts,
    and statement-similarity matching punished exactly that.
    """
    facts_root = register.facts_root()
    cache: dict[str, str] = {}
    spans: dict[str, list[tuple[str, int, int]]] = {}
    for fact in register.facts.values():
        for provenance in fact.provenance:
            if not provenance.file or not provenance.quote:
                continue
            if provenance.file not in cache:
                path = (facts_root / provenance.file).resolve()
                cache[provenance.file] = (
                    _normalize(path.read_text(encoding="utf-8", errors="replace"))
                    if path.is_file()
                    else ""
                )
            text = cache[provenance.file]
            start = text.find(_normalize(provenance.quote))
            if start >= 0:
                spans.setdefault(fact.id, []).append(
                    (provenance.file, start, start + len(_normalize(provenance.quote)))
                )
    return spans


def _span_length(spans: list[tuple[str, int, int]]) -> int:
    return sum(end - start for _file, start, end in spans)


def _span_overlap(left: list[tuple[str, int, int]], right: list[tuple[str, int, int]]) -> int:
    total = 0
    for lfile, lstart, lend in left:
        for rfile, rstart, rend in right:
            if lfile == rfile:
                total += max(0, min(lend, rend) - max(lstart, rstart))
    return total


def _covers(a: list[tuple[str, int, int]], b: list[tuple[str, int, int]]) -> bool:
    shorter = min(_span_length(a), _span_length(b))
    return shorter > 0 and _span_overlap(a, b) >= SPAN_OVERLAP_THRESHOLD * shorter


def _score_facts(gold: facts_mod.Register, candidate: facts_mod.Register) -> CategoryScore:
    """Credit evidence coverage; let the statement decide full or half credit.

    Spans answer "was this ground covered?", which survives splitting and merging.
    Statement similarity still matters: matching evidence under a statement that says
    something else is half a match, not a match -- otherwise the register could describe
    anything as long as it quoted the right sentence.
    """
    gold_spans = _fact_spans(gold)
    candidate_spans = _fact_spans(candidate)
    # Keyed per side, never merged: a candidate is usually a *copy* of gold with the same
    # fact ids, and one shared dict silently compared every statement with itself.
    gold_statements = {f.id: _normalize(f.statement) for f in gold.facts.values()}
    candidate_statements = {f.id: _normalize(f.statement) for f in candidate.facts.values()}

    def credit(
        statement: str, source_spans: list[tuple[str, int, int]],
        others: dict[str, list], other_statements: dict[str, str],
    ) -> float:
        overlapping = [oid for oid, ospans in sorted(others.items()) if _covers(source_spans, ospans)]
        if not overlapping:
            return 0.0
        best = max(
            difflib.SequenceMatcher(None, statement, other_statements[oid]).ratio()
            for oid in overlapping
            if oid in other_statements
        )
        return 1.0 if best >= FACT_MATCH_THRESHOLD else PARTIAL_CREDIT

    def fallback_similarity() -> CategoryScore:
        """Sources not shared (or quotes unlocatable): fall back to statements alone."""
        available = dict(candidate_statements)
        matched = 0
        missed: list[str] = []
        for gold_fact in sorted(gold.facts.values(), key=lambda f: f.id):
            best_id, best_ratio = None, 0.0
            for cid, statement in sorted(available.items()):
                ratio = difflib.SequenceMatcher(None, gold_statements[gold_fact.id], statement).ratio()
                if ratio > best_ratio:
                    best_id, best_ratio = cid, ratio
            if best_id is not None and best_ratio >= FACT_MATCH_THRESHOLD:
                matched += 1
                del available[best_id]
            else:
                missed.append(gold_fact.id)
        return CategoryScore(
            gold=len(gold.facts),
            candidate=len(candidate.facts),
            matched=matched,
            unmatched_gold=tuple(missed),
            unmatched_candidate=tuple(sorted(available)),
        )

    if not gold_spans or not candidate_spans:
        return fallback_similarity()

    def side(
        ids: list[str], statements: dict[str, str], spans: dict[str, list],
        others: dict[str, list], other_statements: dict[str, str],
    ) -> tuple[float, list[str], list[str]]:
        total, missed, half = 0.0, [], []
        for fact_id in ids:
            value = credit(statements[fact_id], spans.get(fact_id, []), others, other_statements)
            total += value
            if value == 0.0:
                missed.append(fact_id)
            elif value == PARTIAL_CREDIT:
                half.append(fact_id)
        return total, missed, half

    recall_credit, missed_gold, half_gold = side(
        sorted(gold.facts), gold_statements, gold_spans, candidate_spans, candidate_statements
    )
    precision_credit, missed_candidate, half_candidate = side(
        sorted(candidate.facts), candidate_statements, candidate_spans, gold_spans, gold_statements
    )
    return CategoryScore(
        gold=len(gold.facts),
        candidate=len(candidate.facts),
        matched=precision_credit,
        matched_gold=recall_credit,
        partial=len(half_gold) + len(half_candidate),
        unmatched_gold=tuple(missed_gold),
        unmatched_candidate=tuple(missed_candidate),
        partial_gold=tuple(half_gold),
        partial_candidate=tuple(half_candidate),
    )


def _element_label(element: dsl.Element) -> str:
    return f"{element.type} {element.name}"


def _relationship_label(model: dsl.Model, relationship: dsl.Relationship) -> str:
    """Name the endpoints, not their ids -- gold and candidate never share ids."""

    def name(element_id: str) -> str:
        element = model.elements.get(element_id)
        return element.name if element else element_id

    return f"{relationship.type} {name(relationship.source)} -> {name(relationship.target)}"


def _score_elements(
    gold: dsl.Model, candidate: dsl.Model, classes: dict[str, str]
) -> tuple[CategoryScore, dict[str, str]]:
    """Score elements and return the gold-id -> candidate-id map relationships need.

    Two passes. First an exact match on (type, canonical name); then, among what is
    left, a *same layer, different type* match at half credit -- ApplicationInterface
    versus ApplicationService for one sentence in an interview is a disagreement about
    classification, not a missing element, and scoring it zero told a model that had
    found everything that it had found nothing.
    """
    exact: dict[tuple[str, str], list[str]] = {}
    by_name: dict[tuple[str, str], list[str]] = {}
    for element in sorted(candidate.elements.values(), key=lambda e: e.id):
        name = _canonical(element.name, classes)
        exact.setdefault((element.type, name), []).append(element.id)
        by_name.setdefault((oracle.layer_of(element.type), name), []).append(element.id)

    mapping: dict[str, str] = {}
    taken: set[str] = set()
    credit = 0.0
    missed: list[str] = []
    half_gold: list[str] = []
    half_candidate: list[str] = []
    for gold_element in sorted(gold.elements.values(), key=lambda e: e.id):
        name = _canonical(gold_element.name, classes)
        bucket = [cid for cid in exact.get((gold_element.type, name), []) if cid not in taken]
        if bucket:
            mapping[gold_element.id] = bucket[0]
            taken.add(bucket[0])
            credit += 1.0
            continue
        bucket = [
            cid
            for cid in by_name.get((oracle.layer_of(gold_element.type), name), [])
            if cid not in taken
        ]
        if bucket:
            mapping[gold_element.id] = bucket[0]
            taken.add(bucket[0])
            credit += PARTIAL_CREDIT
            half_gold.append(_element_label(gold_element))
            half_candidate.append(_element_label(candidate.elements[bucket[0]]))
        else:
            missed.append(_element_label(gold_element))
    extra = [
        _element_label(element)
        for element in sorted(candidate.elements.values(), key=lambda e: e.id)
        if element.id not in taken
    ]
    return (
        CategoryScore(
            gold=len(gold.elements),
            candidate=len(candidate.elements),
            matched=credit,
            partial=len(half_gold),
            unmatched_gold=tuple(missed),
            unmatched_candidate=tuple(extra),
            partial_gold=tuple(half_gold),
            partial_candidate=tuple(half_candidate),
        ),
        mapping,
    )


def _score_relationships(
    gold: dsl.Model, candidate: dsl.Model, element_map: dict[str, str]
) -> CategoryScore:
    available: dict[tuple[str, str, str], list[str]] = {}
    for relationship in sorted(candidate.relationships.values(), key=lambda r: r.id):
        key = (relationship.type, relationship.source, relationship.target)
        available.setdefault(key, []).append(relationship.id)
    matched = 0
    used: set[str] = set()
    unresolved: list[dsl.Relationship] = []
    for gold_rel in sorted(gold.relationships.values(), key=lambda r: r.id):
        source = element_map.get(gold_rel.source)
        target = element_map.get(gold_rel.target)
        bucket = available.get((gold_rel.type, source, target)) if source and target else None
        if bucket:
            used.add(bucket.pop())
            matched += 1
            if not bucket:
                del available[(gold_rel.type, source, target)]
        else:
            unresolved.append(gold_rel)

    # Second pass: is the edge the candidate did not draw one its model *implies*?
    # ArchiMate's own abstraction rules answer that (derive.py, Appendix B.2), and until
    # they existed this whole category read 0% whenever two models differed in
    # granularity. Half credit: the connection is there, the grain is contested.
    implied = derive.closure(candidate) if unresolved else {}
    missed: list[str] = []
    derived_gold: list[str] = []
    supporting: set[str] = set()
    for gold_rel in unresolved:
        source = element_map.get(gold_rel.source)
        target = element_map.get(gold_rel.target)
        derivation = (
            implied.get(derive.Edge(gold_rel.type, source, target)) if source and target else None
        )
        if derivation is not None and derivation.is_derived:
            derived_gold.append(
                f"{_relationship_label(gold, gold_rel)} ({derive.describe(candidate, derivation)})"
            )
            supporting |= derivation.used - used
        else:
            missed.append(_relationship_label(gold, gold_rel))

    extra: list[str] = []
    derived_candidate: list[str] = []
    for relationship in sorted(candidate.relationships.values(), key=lambda r: r.id):
        if relationship.id in used:
            continue
        label = _relationship_label(candidate, relationship)
        # An edge that carries a derivation of a gold edge is not an invention; it is the
        # same content at a finer grain, so it earns the same half credit on this side.
        (derived_candidate if relationship.id in supporting else extra).append(label)

    return CategoryScore(
        gold=len(gold.relationships),
        candidate=len(candidate.relationships),
        matched=matched + PARTIAL_CREDIT * len(derived_candidate),
        matched_gold=matched + PARTIAL_CREDIT * len(derived_gold),
        partial=len(derived_gold) + len(derived_candidate),
        unmatched_gold=tuple(missed),
        unmatched_candidate=tuple(extra),
        partial_gold=tuple(derived_gold),
        partial_candidate=tuple(derived_candidate),
    )


def _structural_relationships(
    gold: dsl.Model, candidate: dsl.Model, classes: dict[str, str]
) -> CategoryScore:
    """The same graph, judged on endpoint *names* rather than matched elements.

    Reported beside the strict count as a diagnostic, never gated: when the strict
    number collapses because one element was labelled differently, this says whether
    the shape was actually right. The 0%-versus-91% gap in the 2026-08-05 end-to-end
    run was entirely this distinction.
    """

    def key(model: dsl.Model, relationship: dsl.Relationship) -> tuple[str, str, str] | None:
        source = model.elements.get(relationship.source)
        target = model.elements.get(relationship.target)
        if source is None or target is None:
            return None
        return (
            relationship.type,
            _canonical(source.name, classes),
            _canonical(target.name, classes),
        )

    available: dict[tuple[str, str, str], int] = {}
    for relationship in candidate.relationships.values():
        item = key(candidate, relationship)
        if item:
            available[item] = available.get(item, 0) + 1
    matched = 0
    for relationship in gold.relationships.values():
        item = key(gold, relationship)
        if item and available.get(item):
            available[item] -= 1
            matched += 1
    return CategoryScore(
        gold=len(gold.relationships), candidate=len(candidate.relationships), matched=matched
    )


@dataclass
class ScoreReport:
    gold_root: Path
    candidate_root: Path
    categories: dict[str, CategoryScore]
    gates: dict[str, dict[str, int]]
    # Diagnostics are reported and never gated: they explain a number, they are not one.
    diagnostics: dict[str, CategoryScore] = field(default_factory=dict)

    @property
    def min_f1(self) -> float:
        return min(score.f1 for score in self.categories.values())

    @property
    def gates_ok(self) -> bool:
        return all(counts["errors"] == 0 for counts in self.gates.values())

    def as_dict(self) -> dict[str, Any]:
        return {
            "gold": str(self.gold_root),
            "candidate": str(self.candidate_root),
            "categories": {name: score.as_dict() for name, score in self.categories.items()},
            "diagnostics": {name: score.as_dict() for name, score in self.diagnostics.items()},
            "minF1": round(self.min_f1, 4),
            "gates": self.gates,
            "gatesOk": self.gates_ok,
        }

    RENDER_LIMIT = 8  # the terminal gets a readable sample; `--json` gets all of it

    def _render_unmatched(self) -> list[str]:
        lines: list[str] = []
        for name, score in self.categories.items():
            for side, items in (
                ("gold", score.unmatched_gold),
                ("cand", score.unmatched_candidate),
                ("half", score.partial_gold),
            ):
                if not items:
                    continue
                shown = ", ".join(items[: self.RENDER_LIMIT])
                if len(items) > self.RENDER_LIMIT:
                    shown += f" (+{len(items) - self.RENDER_LIMIT} more)"
                lines.append(f"  {name:<15} {side}: {shown}")
        return lines

    def render(self) -> str:
        lines = [
            ui.bold(f"Golden-set score: candidate {self.candidate_root}"),
            ui.dim(f"           gold: {self.gold_root}"),
            "",
            ui.dim(f"{'category':<15} {'gold':>5} {'cand':>5} {'match':>6} {'prec':>7} {'recall':>7} {'F1':>7}"),
        ]
        for name, score in self.categories.items():
            f1_field = f"{score.f1:>7.2%}"
            f1_styled = ui.green(f1_field) if score.f1 >= 1.0 else ui.yellow(f1_field)
            note = ui.dim(f"  ({score.partial} half)") if score.partial else ""
            lines.append(
                f"{ui.bold(f'{name:<15}')} {score.gold:>5} {score.candidate:>5} {score.matched:>6.1f} "
                f"{score.precision:>7.2%} {score.recall:>7.2%} {f1_styled}{note}"
            )
        for name, score in self.diagnostics.items():
            lines.append(
                ui.dim(
                    f"{name:<15} {score.gold:>5} {score.candidate:>5} {score.matched:>6.1f} "
                    f"{score.precision:>7.2%} {score.recall:>7.2%} {score.f1:>7.2%}  diagnostic, not gated"
                )
            )
        detail = self._render_unmatched()
        if detail:
            lines += ["", ui.dim("what did not match (gold side = missed, cand side = unsupported):")]
            lines += detail
        lines.append("")
        for gate, counts in self.gates.items():
            verdict = ui.status("PASS") if counts["errors"] == 0 else ui.status("FAIL")
            lines.append(
                f"candidate gate {gate}: {counts['errors']} error(s), "
                f"{counts['warnings']} warning(s) -- {verdict}"
            )
        summary = f"min F1 across categories: {self.min_f1:.2%}"
        lines += [
            "",
            (ui.green(summary) if self.min_f1 >= 1.0 else ui.yellow(summary))
            + ("" if self.gates_ok else ui.red("  (candidate fails its own gates -- matching numbers are not trustworthy)")),
        ]
        return "\n".join(lines)


def score(candidate_root: Path, gold_root: Path) -> ScoreReport:
    gold_register, _d, _e = facts_mod.load(gold_root)
    candidate_register, _d, _e = facts_mod.load(candidate_root)
    gold_model, _docs, _config = dsl.load(gold_root, "approved")
    candidate_model, _docs, _config = dsl.load(candidate_root, "approved")

    # The entity tables of *both* repositories define the vocabulary the comparison uses.
    classes = _alias_classes(gold_register, candidate_register)
    element_score, element_map = _score_elements(gold_model, candidate_model, classes)
    categories = {
        "entities": _score_entities(gold_register, candidate_register),
        "facts": _score_facts(gold_register, candidate_register),
        "elements": element_score,
        "relationships": _score_relationships(gold_model, candidate_model, element_map),
    }
    diagnostics = {
        "rel-structural": _structural_relationships(gold_model, candidate_model, classes),
    }

    model_report = validate_mod.validate(candidate_root, zone="approved")
    facts_report = facts_mod.validate_facts(candidate_root)
    gates = {
        "model": {"errors": len(model_report.errors), "warnings": len(model_report.warnings)},
        "facts": {"errors": len(facts_report.errors), "warnings": len(facts_report.warnings)},
    }
    return ScoreReport(
        gold_root=gold_root,
        candidate_root=candidate_root,
        categories=categories,
        gates=gates,
        diagnostics=diagnostics,
    )
