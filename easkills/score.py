"""Golden-set scoring: compare a candidate repository against a gold one.

The harness closes the loop the research opened: extraction quality is a measured
property, not a vibe. A skill change is evaluated by running the pipeline on a golden
case's sources into a scratch repository and scoring the result here -- precision,
recall and F1 per category, computed deterministically:

* **entities**    matched when their term sets (name + aliases, normalized) intersect;
* **facts**       matched by normalized-statement similarity (one-to-one, greedy best
                  match at or above ``FACT_MATCH_THRESHOLD``);
* **elements**    matched by (ArchiMate type, normalized name) -- the standard basis
                  for model comparison in the EA-model literature;
* **relationships** matched by type plus endpoints that map through element matches.

Candidate *quality* is not inferred from matching alone: the candidate's own gates
(model and fact-register validators) run too, because a candidate that matches gold
while failing provenance verification is a fabrication that happens to be right.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import dsl, facts as facts_mod
from . import validate as validate_mod
from .validate import _normalize

FACT_MATCH_THRESHOLD = 0.85


@dataclass(frozen=True)
class CategoryScore:
    gold: int
    candidate: int
    matched: int

    @property
    def precision(self) -> float:
        return self.matched / self.candidate if self.candidate else 1.0

    @property
    def recall(self) -> float:
        return self.matched / self.gold if self.gold else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "gold": self.gold,
            "candidate": self.candidate,
            "matched": self.matched,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


def _score_entities(gold: facts_mod.Register, candidate: facts_mod.Register) -> CategoryScore:
    def terms(entity: facts_mod.Entity) -> frozenset[str]:
        return frozenset({_normalize(entity.name)} | {_normalize(a) for a in entity.aliases}) - {""}

    available = {e.id: terms(e) for e in candidate.entities.values()}
    matched = 0
    for gold_entity in sorted(gold.entities.values(), key=lambda e: e.id):
        gold_terms = terms(gold_entity)
        hit = next(
            (cid for cid, cterms in sorted(available.items()) if gold_terms & cterms),
            None,
        )
        if hit is not None:
            matched += 1
            del available[hit]
    return CategoryScore(gold=len(gold.entities), candidate=len(candidate.entities), matched=matched)


def _score_facts(gold: facts_mod.Register, candidate: facts_mod.Register) -> CategoryScore:
    available = {f.id: _normalize(f.statement) for f in candidate.facts.values()}
    matched = 0
    for gold_fact in sorted(gold.facts.values(), key=lambda f: f.id):
        gold_statement = _normalize(gold_fact.statement)
        best_id, best_ratio = None, 0.0
        for cid, statement in sorted(available.items()):
            ratio = difflib.SequenceMatcher(None, gold_statement, statement).ratio()
            if ratio > best_ratio:
                best_id, best_ratio = cid, ratio
        if best_id is not None and best_ratio >= FACT_MATCH_THRESHOLD:
            matched += 1
            del available[best_id]
    return CategoryScore(gold=len(gold.facts), candidate=len(candidate.facts), matched=matched)


def _element_key(element: dsl.Element) -> tuple[str, str]:
    return (element.type, _normalize(element.name))


def _score_elements(
    gold: dsl.Model, candidate: dsl.Model
) -> tuple[CategoryScore, dict[str, str]]:
    """Returns the score plus the gold-id -> candidate-id map the relationship
    scorer needs."""
    available: dict[tuple[str, str], str] = {}
    for element in sorted(candidate.elements.values(), key=lambda e: e.id):
        available.setdefault(_element_key(element), element.id)
    mapping: dict[str, str] = {}
    for gold_element in sorted(gold.elements.values(), key=lambda e: e.id):
        key = _element_key(gold_element)
        if key in available:
            mapping[gold_element.id] = available.pop(key)
    return (
        CategoryScore(gold=len(gold.elements), candidate=len(candidate.elements), matched=len(mapping)),
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
    for gold_rel in sorted(gold.relationships.values(), key=lambda r: r.id):
        source = element_map.get(gold_rel.source)
        target = element_map.get(gold_rel.target)
        if source is None or target is None:
            continue
        key = (gold_rel.type, source, target)
        bucket = available.get(key)
        if bucket:
            bucket.pop()
            matched += 1
            if not bucket:
                del available[key]
    return CategoryScore(
        gold=len(gold.relationships), candidate=len(candidate.relationships), matched=matched
    )


@dataclass
class ScoreReport:
    gold_root: Path
    candidate_root: Path
    categories: dict[str, CategoryScore]
    gates: dict[str, dict[str, int]]

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
            "minF1": round(self.min_f1, 4),
            "gates": self.gates,
            "gatesOk": self.gates_ok,
        }

    def render(self) -> str:
        lines = [
            f"Golden-set score: candidate {self.candidate_root}",
            f"           gold: {self.gold_root}",
            "",
            f"{'category':<15} {'gold':>5} {'cand':>5} {'match':>6} {'prec':>7} {'recall':>7} {'F1':>7}",
        ]
        for name, score in self.categories.items():
            lines.append(
                f"{name:<15} {score.gold:>5} {score.candidate:>5} {score.matched:>6} "
                f"{score.precision:>7.2%} {score.recall:>7.2%} {score.f1:>7.2%}"
            )
        lines.append("")
        for gate, counts in self.gates.items():
            verdict = "PASS" if counts["errors"] == 0 else "FAIL"
            lines.append(f"candidate gate {gate}: {counts['errors']} error(s), {counts['warnings']} warning(s) -- {verdict}")
        lines += [
            "",
            f"min F1 across categories: {self.min_f1:.2%}"
            + ("" if self.gates_ok else "  (candidate fails its own gates -- matching numbers are not trustworthy)"),
        ]
        return "\n".join(lines)


def score(candidate_root: Path, gold_root: Path) -> ScoreReport:
    gold_register, _d, _e = facts_mod.load(gold_root)
    candidate_register, _d, _e = facts_mod.load(candidate_root)
    gold_model, _docs, _config = dsl.load(gold_root, "approved")
    candidate_model, _docs, _config = dsl.load(candidate_root, "approved")

    element_score, element_map = _score_elements(gold_model, candidate_model)
    categories = {
        "entities": _score_entities(gold_register, candidate_register),
        "facts": _score_facts(gold_register, candidate_register),
        "elements": element_score,
        "relationships": _score_relationships(gold_model, candidate_model, element_map),
    }

    model_report = validate_mod.validate(candidate_root, zone="approved")
    facts_report = facts_mod.validate_facts(candidate_root)
    gates = {
        "model": {"errors": len(model_report.errors), "warnings": len(model_report.warnings)},
        "facts": {"errors": len(facts_report.errors), "warnings": len(facts_report.warnings)},
    }
    return ScoreReport(
        gold_root=gold_root, candidate_root=candidate_root, categories=categories, gates=gates
    )
