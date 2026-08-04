"""Every documented fact-register rule code must actually fire on the negative fixture,
and the worked example's register must stay clean -- same contract as the model rules."""

import pytest

from easkills import facts, validate


@pytest.fixture(scope="module")
def example_report(example_root):
    return facts.validate_facts(example_root)


@pytest.fixture(scope="module")
def broken_report(broken_root):
    return facts.validate_facts(broken_root)


# --------------------------------------------------------------------------- positive


def test_example_register_is_clean(example_report):
    assert example_report.ok, "\n".join(f.render() for f in example_report.errors)
    assert not example_report.warnings, "\n".join(f.render() for f in example_report.warnings)


def test_example_register_counts(example_report):
    assert example_report.counts["facts"] == 25
    assert example_report.counts["entities"] == 11
    assert example_report.counts["sources"] == 2


def test_example_demonstrates_multi_source_provenance(example_root):
    register, _docs, _entities = facts.load(example_root)
    fact = register.facts["fact-po-retention"]
    assert len({p.file for p in fact.provenance}) == 2, (
        "the worked example should show one fact merged from quotes in two sources"
    )


def test_example_demonstrates_implied_confidence(example_root):
    register, _docs, _entities = facts.load(example_root)
    assert any(f.confidence == "implied" for f in register.facts.values())


# --------------------------------------------------------------------------- negative

EXPECTED_ERROR_CODES = [
    "FACT000",  # unparseable register file
    "FACT001",  # schema violation (unknown key / missing statement)
    "FACT002",  # duplicate fact id
    "FACT003",  # provenance source file missing
    "FACT004",  # quote absent from the source
    "FACT006",  # unknown entity reference
    "FACT008",  # evidence file resolves outside the repository
    "ENT001",  # duplicate entity id
    "ENT002",  # alias collides with another entity's name
]

EXPECTED_WARNING_CODES = [
    "FACT005",  # quote only approximately matched
    "FACT007",  # duplicate statement
    "ENT003",  # entity never referenced
    "SRC001",  # source never cited
]


@pytest.mark.parametrize("code", EXPECTED_ERROR_CODES)
def test_error_rule_fires(broken_report, code):
    matches = [f for f in broken_report.errors if f.code == code]
    assert matches, f"{code} did not fire on the negative fixture"


@pytest.mark.parametrize("code", EXPECTED_WARNING_CODES)
def test_warning_rule_fires(broken_report, code):
    matches = [f for f in broken_report.warnings if f.code == code]
    assert matches, f"{code} did not fire on the negative fixture"


def test_broken_register_fails_overall(broken_report):
    assert not broken_report.ok


def test_fabricated_citation_is_an_error_not_a_warning(broken_report):
    finding = next(f for f in broken_report.findings if f.concept == "fact-fabricated-quote")
    assert finding.code == "FACT004"
    assert finding.severity == validate.SEVERITY_ERROR


def test_paraphrased_citation_is_a_warning(broken_report):
    finding = next(f for f in broken_report.findings if f.concept == "fact-paraphrased-quote")
    assert finding.code == "FACT005"
    assert finding.severity == validate.SEVERITY_WARNING


def test_entity_collision_names_both_entities(broken_report):
    finding = next(f for f in broken_report.errors if f.code == "ENT002")
    assert "ent-portal" in finding.message


def test_facts_have_no_assumed_escape_hatch():
    """The schema must reject an unsourced fact outright; unlike model concepts there
    is no 'assumed: true' path for facts."""
    from jsonschema import Draft202012Validator

    from easkills import genschema

    validator = Draft202012Validator(genschema.build_facts_schema())
    document = {"facts": [{"id": "fact-x", "statement": "something plausible", "assumed": True}]}
    messages = [e.message for e in validator.iter_errors(document)]
    assert any("provenance" in m for m in messages)
    assert any("assumed" in m for m in messages)


# --------------------------------------------------------------------------- edges


def test_empty_repository_register_is_valid(tmp_path):
    report = facts.validate_facts(tmp_path)
    assert report.ok
    assert report.counts["facts"] == 0


def test_report_serializes_to_json(example_report):
    payload = example_report.as_dict()
    assert payload["ok"] is True
    assert payload["counts"]["facts"] == 25
    assert isinstance(payload["findings"], list)
