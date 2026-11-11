"""Quote anchoring (D10): what the two checks flag, what they deliberately do not, and the
measurement their severities rest on.

The rules were measured over every repository carrying a register before they shipped
(2026-11-11, tools/anchor_report.py, the four golden cases and the worked example):
FACT012 flagged 9 of 76 stated facts listing entities, and all nine were correct facts --
quoted with a pronoun ("its screens"), a demonstrative ("that API"), a plural or singular
the alias table does not carry, a clause whose subject the sentence elided, or a context
entity -- so it is info. PROV010, narrowed to elements whose names are names a source
uses, flagged 0 of 25, so it is a warning. These tests pin both the behaviour and the measurement, so a change to
either has to change the other in the same commit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from easkills import anchors, dsl, facts as facts_mod
from easkills.validate import SEVERITY_INFO, SEVERITY_WARNING

GOLD = ("eval/golden/clinic", "eval/golden/contested", "eval/golden/mill", "eval/golden/wodociagi", "eval/example")


def _repo(tmp_path: Path, facts_yaml: str, entities_yaml: str, model_yaml: str = "") -> Path:
    (tmp_path / "ea.config.yaml").write_text("name: T\n", encoding="utf-8")
    sources = tmp_path / "facts" / "sources"
    sources.mkdir(parents=True)
    (sources / "notes.md").write_text(
        "The order portal runs on a rented server. It has never been patched.\n"
        "The finance team owns the ledger.\n",
        encoding="utf-8",
    )
    (tmp_path / "facts" / "register").mkdir()
    (tmp_path / "facts" / "register" / "notes.yaml").write_text(facts_yaml, encoding="utf-8")
    (tmp_path / "facts" / "entities.yaml").write_text(entities_yaml, encoding="utf-8")
    (tmp_path / "model" / "approved").mkdir(parents=True)
    if model_yaml:
        (tmp_path / "model" / "approved" / "m.yaml").write_text(model_yaml, encoding="utf-8")
    return tmp_path


ENTITIES = (
    "entities:\n"
    "  - id: portal\n    name: Order Portal\n    aliases: [the portal]\n"
    "  - id: ledger\n    name: Ledger\n"
)


def _fact(fid: str, quote: str, entities: str, confidence: str = "") -> str:
    extra = f"    confidence: {confidence}\n" if confidence else ""
    return (
        f"  - id: {fid}\n    statement: Statement of {fid}.\n{extra}"
        f"    provenance:\n      - file: facts/sources/notes.md\n        quote: {quote}\n"
        f"    entities: [{entities}]\n"
    )


def test_a_quote_naming_an_alias_anchors_and_a_pronoun_does_not(tmp_path):
    root = _repo(
        tmp_path,
        "facts:\n"
        + _fact("fact-named", "The order portal runs on a rented server.", "portal")
        + _fact("fact-pronoun", "It has never been patched.", "portal")
        + _fact("fact-implied", "It has never been patched.", "portal", confidence="implied"),
        ENTITIES,
    )
    register, _docs, _entities = facts_mod.load(root)
    flagged = {f.concept: f for f in anchors.unanchored_facts(register)}
    assert set(flagged) == {"fact-pronoun"}, "the documented false-positive class, reported as such"
    assert flagged["fact-pronoun"].severity == SEVERITY_INFO
    # An implied fact is indirect by definition and says so; it is never flagged.


def test_only_elements_that_carry_a_sources_name_are_held_to_it(tmp_path):
    model = (
        "elements:\n"
        "  - id: app-ledger\n    type: ApplicationComponent\n    name: Ledger Engine\n"
        "    provenance:\n      - fact: fact-portal\n"
        "  - id: cap-ordering\n    type: Capability\n    name: Ordering\n"
        "    provenance:\n      - fact: fact-portal\n"
        "  - id: app-portal\n    type: ApplicationComponent\n    name: Order Portal\n"
        "    provenance:\n      - fact: fact-portal\n"
    )
    root = _repo(
        tmp_path,
        "facts:\n" + _fact("fact-portal", "The order portal runs on a rented server.", "portal"),
        ENTITIES,
        model,
    )
    register, _docs, _entities = facts_mod.load(root)
    built, _mdocs, _config = dsl.load(root, "approved")
    flagged = {f.concept: f for f in anchors.unanchored_elements(built, register)}
    assert set(flagged) == {"app-ledger"}, "a capability is named by the modeller; the portal answers by name"
    assert flagged["app-ledger"].severity == SEVERITY_WARNING


def test_an_element_resting_only_on_implied_facts_is_not_held_to_naming(tmp_path):
    """Found by review: FACT012 exempted implied facts as indirect by definition, PROV010
    did not -- so the same declared indirectness was forgiven in one gate and a warning in
    the other."""
    model = (
        "elements:\n"
        "  - id: app-ledger\n    type: ApplicationComponent\n    name: Ledger Engine\n"
        "    provenance:\n      - fact: fact-implied\n"
    )
    root = _repo(
        tmp_path,
        "facts:\n" + _fact("fact-implied", "It has never been patched.", "portal", confidence="implied"),
        ENTITIES,
        model,
    )
    register, _docs, _entities = facts_mod.load(root)
    built, _mdocs, _config = dsl.load(root, "approved")
    assert anchors.unanchored_elements(built, register) == []


def test_whole_word_matching_is_by_boundary_not_by_substring():
    assert anchors._names("ehr", "the ehr holds charts")
    assert not anchors._names("ehr", "ehrlich holds charts")
    assert anchors._names("e-bok", "dane w e-bok.")
    # A hyphen is a boundary, as it is for a regex word boundary: "bok" is named by "e-bok".
    # Pinned so the definition cannot drift silently between the two spellings of the check.
    assert anchors._names("bok", "e-bok")
    assert anchors._names("księgowy", "system księgowy działa")
    assert not anchors._names("księgowy", "księgowym")


@pytest.mark.parametrize(("check", "flagged", "population"), [("facts", 9, 76), ("elements", 0, 25)])
def test_the_measurement_the_severities_rest_on(repo_root, check, flagged, population):
    found = 0
    measured = 0
    for relative in GOLD:
        root = repo_root / relative
        register, _docs, _entities = facts_mod.load(root)
        if check == "facts":
            found += len(anchors.unanchored_facts(register))
            measured += sum(1 for f in register.facts.values() if f.entities and f.confidence != "implied")
        else:
            model, _mdocs, _config = dsl.load(root, "approved")
            found += len(anchors.unanchored_elements(model, register))
            measured += sum(
                1
                for e in model.elements.values()
                if anchors.names_a_thing(e.type)
                and any(p.fact and p.fact in register.facts and register.facts[p.fact].entities for p in e.provenance)
            )
    assert (found, measured) == (flagged, population), (
        "the anchoring measurement moved -- re-classify the findings and restate the severity in "
        "docs/RULES.md and this file's docstring before changing the numbers here"
    )
