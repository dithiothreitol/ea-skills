"""Quote anchoring: does the quote name the thing the claim is about? (D10)

``PROV003`` and ``FACT004`` prove a quote exists in its source. Neither proves the quote is
*about* what it is cited for: a fact "the ERP runs in the cloud" citing "The ERP core holds
the master order records" passes both, because the sentence is there. Whether a quote
supports a claim is entailment, which is judgement -- and judgement is measured outside the
core (the harness's entailment judge, D11), never decided here.

What a rule *can* check is narrower and cheaper: whether the quote names the thing at all,
through the entity alias table the register already keeps. That is a proxy, and it
misfires on exactly the sentences people write ("it runs on a single server" names
nothing). So the two checks below were measured over every repository carrying a register
before any rule fired on them, false positives counted; the severity each rule ships with
is the one that count supports (docs/RULES.md, ``FACT012`` and ``PROV010``).

Matching uses the matcher's own normal form (``textfold``) and whole words, so "EHR"
names "the EHR" and not "EHRlich"; an entity names a quote through its canonical name or
any alias the register records. ``implied`` facts are exempt from both checks: they are
indirect by definition, and the register already says so. Terms and quotes are normalized
once per call, never per element -- these checks run inside the gate the hooks run after
every write.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import oracle, textfold
from .validate import SEVERITY_INFO, SEVERITY_WARNING, Finding, _rel

if TYPE_CHECKING:  # pragma: no cover
    from . import dsl
    from .facts import Fact, Register

# Elements whose names are names a source uses: the structure of the business, application,
# technology and physical layers. A capability, a requirement, a plateau or a process is
# named by the modeller -- "Retain Purchase Orders for Seven Years" is a sentence no source
# contains -- and the measurement found every unanchored element of that kind correct.
NAMED_LAYERS = frozenset({"Business", "Application", "Technology", "Physical"})


def names_a_thing(element_type: str) -> bool:
    return oracle.layer_of(element_type) in NAMED_LAYERS and not oracle.is_behaviour(element_type)


def _names(term: str, text: str) -> bool:
    """True when ``term`` occurs in ``text`` as whole words (both in matcher form)."""
    start = text.find(term)
    while start != -1:
        end = start + len(term)
        before = text[start - 1] if start else " "
        after = text[end] if end < len(text) else " "
        if not before.isalnum() and before != "_" and not after.isalnum() and after != "_":
            return True
        start = text.find(term, start + 1)
    return False


class _Index:
    """Each entity's terms and each fact's quotes, in matcher form, computed once."""

    def __init__(self, register: "Register") -> None:
        self.register = register
        self._terms: dict[str, tuple[str, ...]] = {}
        self._quotes: dict[str, tuple[str, ...]] = {}

    def terms(self, entity_id: str) -> tuple[str, ...]:
        if entity_id not in self._terms:
            entity = self.register.entities[entity_id]
            normalized = (textfold.normalize(term) for term in [entity.name, *entity.aliases])
            self._terms[entity_id] = tuple(term for term in normalized if term)
        return self._terms[entity_id]

    def quotes(self, fact: "Fact") -> tuple[str, ...]:
        if fact.id not in self._quotes:
            self._quotes[fact.id] = tuple(textfold.normalize(p.quote) for p in fact.provenance if p.quote)
        return self._quotes[fact.id]


def unanchored_facts(register: "Register", severity: str = SEVERITY_INFO) -> list[Finding]:
    """A stated fact that lists entities none of its quotes names."""
    index = _Index(register)
    findings: list[Finding] = []
    for fact in sorted(register.facts.values(), key=lambda f: f.id):
        if fact.confidence == "implied":
            continue
        listed = [e for e in fact.entities if e in register.entities]
        if not listed:
            continue  # nothing to anchor to; unknown ids are FACT006's to report
        quotes = index.quotes(fact)
        if any(_names(term, quote) for entity_id in listed for term in index.terms(entity_id) for quote in quotes):
            continue
        findings.append(
            Finding(
                "FACT012",
                severity,
                f"no quote names {', '.join(sorted(listed))} (by name or any alias) -- the quote may be "
                "about something else; quote the sentence that names it, or add the alias the source "
                "actually uses to facts/entities.yaml",
                file=_rel(register.root, fact.source_path),
                locator=fact.locator,
                concept=fact.id,
            )
        )
    return findings


def unanchored_elements(model: "dsl.Model", register: "Register", severity: str = SEVERITY_WARNING) -> list[Finding]:
    """A named element (``names_a_thing``) citing stated facts none of whose entities
    answers to it, and none of whose quotes names it."""
    index = _Index(register)
    findings: list[Finding] = []
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        if not names_a_thing(element.type):
            continue
        cited = [register.facts[p.fact] for p in element.provenance if p.fact and p.fact in register.facts]
        cited = [fact for fact in cited if fact.entities]
        if not any(fact.confidence != "implied" for fact in cited):
            continue  # nothing cited, or only facts that declare themselves indirect
        name = textfold.normalize(element.name)
        if any(
            name in index.terms(entity_id)
            for fact in cited
            for entity_id in fact.entities
            if entity_id in register.entities
        ):
            continue
        if any(_names(name, quote) for fact in cited for quote in index.quotes(fact)):
            continue
        findings.append(
            Finding(
                "PROV010",
                severity,
                f"cites {', '.join(sorted(f.id for f in cited))}, but none of their entities answers to "
                f"'{element.name}' and no cited quote names it -- check the citation is about this element "
                "(an alias in facts/entities.yaml is how a register says two names are one thing)",
                file=_rel(model.root, element.source_path),
                locator=element.locator,
                concept=element.id,
            )
        )
    return findings
