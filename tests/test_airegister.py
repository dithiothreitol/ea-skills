"""The EU AI Act system inventory: the second register, held to the first one's bar.

Everything ``dora-register`` had to prove, this proves again -- the refusal to produce
an empty page, the gap section naming element ids, the byte-stable document -- plus the
one thing DORA never had to face: an element in *two* registers' scope at once. The
dual-scope element is the reason ``regulatoryScope`` became a closed enum of
combinations, and the test that both registers see it is the test that neither lost a
row to the other.
"""

from datetime import date

import pytest
import yaml
from jsonschema import Draft202012Validator

from easkills import airegister, dora, genschema

TODAY = date(2026, 7, 30)
CODES = ("AIR001", "AIR002", "AIR003", "AIR004", "AIR005")


@pytest.fixture(scope="module")
def aico(repo_root):
    return repo_root / "eval" / "fixtures" / "aico"


@pytest.fixture(scope="module")
def aico_broken(repo_root):
    return repo_root / "eval" / "fixtures" / "aico-broken"


@pytest.fixture(scope="module")
def clean(aico):
    return airegister.build(aico, today=TODAY)


@pytest.fixture(scope="module")
def broken(aico_broken):
    return airegister.build(aico_broken, today=TODAY)


# ------------------------------------------------------------------------------ scope


def test_the_worked_example_is_out_of_scope_and_says_so(example_root):
    """Aurora Foods runs no AI system the Act reaches. Tagging the example to
    demonstrate the feature would have taught the wrong thing about scope -- the same
    reasoning that gave the REG family its own fixture gives the AIR family this one."""
    register = airegister.build(example_root, today=TODAY)
    assert not register.in_scope
    assert register.ok and not register.findings
    assert "Nothing is in scope" in airegister.render(register)


def test_no_scope_means_no_document_at_all(example_root):
    """Not an empty inventory: *no* inventory. The CLI turns this refusal into exit 1
    rather than writing the file."""
    with pytest.raises(airegister.AiActError) as exc:
        airegister.markdown(airegister.build(example_root, today=TODAY))
    assert "nothing to inventory" in str(exc.value)


def test_scope_is_declared_never_inferred_from_a_type(clean):
    """`app-loan-origination` is an application component like the others. Inferring
    scope from a type -- or from a name that sounds like AI -- would sweep it in, and an
    inventory padded with things the Act does not reach is as wrong as one missing
    something."""
    assert "app-loan-origination" not in {entry.id for entry in clean.entries}
    assert len(clean.entries) == 3


def test_a_dual_scope_element_appears_in_both_registers(aico):
    """The reason multi-scope exists: a bought credit-scoring service is DORA's ICT
    third-party risk and the AI Act's high-risk system at once. Before membership went
    through the shared splitter, an equality test would have dropped it from *both*
    registers silently -- the exact under-inclusion the closed vocabulary is for."""
    ai = airegister.build(aico, today=TODAY)
    ict = dora.build(aico, today=TODAY)
    assert "app-credit-scoring" in {entry.id for entry in ai.entries}
    assert [entry.id for entry in ict.entries] == ["app-credit-scoring"]


# ---------------------------------------------------------------------------- the rules


@pytest.mark.parametrize("code", CODES)
def test_every_documented_air_code_has_a_provoking_fixture(code, clean, broken):
    """The triple every rule in this repository ships with: the check, a fixture that
    violates it, a row in RULES.md. AIR003 is the one the *clean* fixture carries -- an
    open waiver on a transparency-risk system is exposure, not a defect."""
    fired = {f.code for f in clean.findings} | {f.code for f in broken.findings}
    assert code in fired


def test_air001_names_the_element_with_no_risk_class(broken):
    findings = [f for f in broken.findings if f.code == "AIR001"]
    assert [f.concept for f in findings] == ["app-scope-without-risk-class"]
    assert all(f.severity == "warning" for f in findings)


def test_air002_is_an_error_and_names_which_field_is_missing(broken):
    findings = {f.concept: f for f in broken.findings if f.code == "AIR002"}
    assert set(findings) == {"app-high-without-role", "app-high-without-oversight"}
    assert all(f.severity == "error" for f in findings.values())
    # Half-filled is still a gap, and the message says *which* half -- otherwise the
    # reader has to open the file to find out what to add.
    assert "no aiRole and no aiOversight" in findings["app-high-without-role"].message
    assert "no aiOversight" in findings["app-high-without-oversight"].message
    assert "aiRole" not in findings["app-high-without-oversight"].message.split("no aiOversight")[0]


def test_air003_is_information_because_a_waiver_is_not_a_violation(clean):
    """An open dispensation on an AI system is risk acceptance working as designed.
    Making this a warning would push people to close waivers to clear a report, which
    loses the record of the exposure -- the exact thing the inventory exists to
    disclose."""
    findings = [f for f in clean.findings if f.code == "AIR003"]
    assert [f.concept for f in findings] == ["app-support-chatbot"]
    assert all(f.severity == "info" for f in findings)
    assert clean.ok, "the clean fixture carries AIR003 and still passes"
    assert not clean.warnings, "...and passes --strict too"


def test_air003_disappears_once_the_waiver_expires(aico):
    """Every date in this report moves with `--as-of` and never with the wall clock.
    The clean fixture's waiver expires 2027-04-30; a run after it must not still
    disclose it."""
    later = airegister.build(aico, today=date(2027, 5, 1))
    assert not [f for f in later.findings if f.code == "AIR003"]
    assert not later.waivers


def test_air004_fires_per_empty_section_and_only_with_content_in_scope(broken, example_root, clean):
    sections = {f.locator for f in broken.findings if f.code == "AIR004"}
    assert sections == {"functions supported", "third-party AI providers"}
    assert not any(f.code == "AIR004" for f in airegister.build(example_root, today=TODAY).findings), (
        "an out-of-scope repository has no empty sections, it has no inventory"
    )
    assert not any(f.code == "AIR004" for f in clean.findings)
    # No file on the finding: the defect belongs to the inventory, not to one element's
    # file, and pointing at an arbitrary one sends the reader somewhere nothing is wrong.
    assert all(f.file == "" for f in broken.findings if f.code == "AIR004")


def test_air004_does_not_expect_a_provider_section_of_an_estate_that_builds_its_own(tmp_path):
    """An organisation whose only in-scope system is its own product has no third-party
    AI provider, and warning about that would train people to ignore the code. The
    provider section is expected only once some in-scope system was made by someone
    else (role deployer/importer/distributor)."""
    (tmp_path / "model" / "approved").mkdir(parents=True)
    (tmp_path / "ea.config.yaml").write_text("name: In-house\n", encoding="utf-8")
    (tmp_path / "model" / "approved" / "m.yaml").write_text(
        yaml.safe_dump(
            {
                "elements": [
                    {
                        "id": "app-own-model",
                        "type": "ApplicationComponent",
                        "name": "Own Model",
                        "properties": {"regulatoryScope": "ai-act", "aiRiskClass": "minimal", "aiRole": "provider"},
                        "assumed": True,
                        "rationale": "test fixture",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    register = airegister.build(tmp_path, today=TODAY)
    sections = {f.locator for f in register.findings if f.code == "AIR004"}
    assert sections == {"functions supported"}, "only the section the estate actually owes"


def test_air005_is_an_error_that_demands_a_decision_not_a_row(broken):
    findings = [f for f in broken.findings if f.code == "AIR005"]
    assert [f.concept for f in findings] == ["app-prohibited-practice"]
    assert all(f.severity == "error" for f in findings)
    assert "decision the board must see" in findings[0].message


# ----------------------------------------------------------------- the inventory itself


def test_the_inventory_names_its_own_gaps_with_element_ids(broken):
    """The feature, inherited from the DORA register: an inventory that quietly omitted
    the fields it could not fill would be indistinguishable from a complete one."""
    gaps = {gap["field"]: gap["elements"] for gap in broken.gaps}
    assert set(gaps) == {"aiRiskClass", "aiRole", "aiOversight", "provider", "functions supported"}
    assert gaps["aiRiskClass"] == ["app-scope-without-risk-class"]
    # Oversight is owed by high-risk systems only, and a provider only by systems
    # somebody else made -- a gap list padded with fields the Act does not want for
    # that row would train people to ignore it.
    assert gaps["aiOversight"] == ["app-high-without-oversight", "app-high-without-role"]
    assert "app-high-without-role" not in gaps["provider"]
    document = airegister.markdown(broken)
    assert "## What this inventory could not fill" in document
    for element_id in gaps["aiOversight"]:
        assert element_id in document.split("## What this inventory could not fill")[1]


def test_a_clean_inventory_still_discloses_what_it_could_not_fill(clean):
    """`app-mail-triage` serves no recorded function, and the clean fixture keeps it
    that way on purpose: a gap is a disclosure, not a defect, and the document must
    carry it without any rule firing."""
    assert [gap["field"] for gap in clean.gaps] == ["functions supported"]
    assert clean.gaps[0]["elements"] == ["app-mail-triage"]
    assert clean.ok and not clean.warnings


def test_the_document_refuses_to_pass_as_a_compliance_record(clean):
    """The header is the legal honesty, and it is not optional. A generated document
    that could be mistaken for an attestation is the risk this whole increment carries."""
    document = airegister.markdown(clean)
    for phrase in (
        "it is not a compliance record",
        "No legal review has taken place",
        "no completeness against the Act's registration or documentation duties is claimed",
        "decision for the people accountable for it",
    ):
        assert phrase in document
    assert document.index("it is not a compliance record") < document.index("## AI systems in scope"), (
        "the caveat must come before the tables, not after them"
    )


def test_a_provider_takes_the_highest_risk_it_supplies(clean):
    """Scorewell supplies one high-risk system. Rounding down would understate a
    provider whose failure or misbehaviour lands on a high-risk function."""
    scorewell = next(row for row in clean.providers if row["provider"] == "Scorewell GmbH")
    assert scorewell["risk"] == "high"
    assert scorewell["elements"] == ["app-credit-scoring"]


def test_functions_carry_the_systems_that_serve_them(clean):
    decision = next(row for row in clean.functions if row["id"] == "process-loan-decision")
    assert decision["risk"] == "high"
    assert decision["supportedBy"] == ["app-credit-scoring"]


def test_the_document_is_byte_stable(clean, aico):
    assert airegister.markdown(clean) == airegister.markdown(airegister.build(aico, today=TODAY))


def test_the_document_ends_with_a_newline_and_uses_no_carriage_returns(clean):
    document = airegister.markdown(clean)
    assert document.endswith("\n") and "\r" not in document


# ---------------------------------------------------------------------- the vocabulary


def test_the_ai_properties_are_closed_enums():
    """Under-inclusion is the failure mode that matters in a regulatory report:
    `aiRiskClass: High` as free text would classify nothing and warn nobody."""
    properties = genschema.build_schema()["$defs"]["element"]["properties"]["properties"]["properties"]
    assert properties["aiRiskClass"]["enum"] == list(genschema.AI_RISK_CLASSES)
    assert properties["aiRole"]["enum"] == list(genschema.AI_ROLES)
    assert airegister.SCOPE_AI_ACT in genschema.REGULATORY_SCOPES
    assert set(airegister.RISK_ORDER) == set(genschema.AI_RISK_CLASSES)
    assert airegister.SOURCED_ROLES <= set(genschema.AI_ROLES)


def test_the_module_reads_the_same_vocabulary_the_schema_writes():
    assert airegister.documented_vocabulary() == {
        "regulatoryScope": genschema.REGULATORY_SCOPES,
        "aiRiskClass": genschema.AI_RISK_CLASSES,
        "aiRole": genschema.AI_ROLES,
    }


@pytest.mark.parametrize(
    ("key", "value"),
    [("aiRiskClass", "High"), ("aiRiskClass", "high "), ("aiRole", "operator"), ("regulatoryScope", "dora ai-act")],
)
def test_a_value_the_tool_cannot_act_on_is_a_schema_error(key, value):
    """The reordered multi-scope value is in this list on purpose: the combinations are
    enumerated in alphabetical order, and 'dora ai-act' failing loudly here is what
    keeps a hand-typed variant from becoming a silent row-drop."""
    element = {
        "elements": [{"id": "app-x", "type": "ApplicationComponent", "name": "X", "properties": {key: value}}]
    }
    errors = list(Draft202012Validator(genschema.build_schema()).iter_errors(element))
    assert errors, f"{key}: {value!r} validated cleanly -- it would silently leave the inventory"


def test_the_fixtures_stay_the_shape_the_tests_assume(aico, aico_broken):
    """Both fixtures are hand-authored, and a later edit that quietly drops the scope
    property would make half this module pass vacuously."""
    for root, expected in ((aico, 3), (aico_broken, 4)):
        tagged = 0
        for path in (root / "model" / "approved").glob("*.yaml"):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            tagged += sum(
                1
                for element in data.get("elements", [])
                if airegister.SCOPE_AI_ACT
                in genschema.split_regulatory_scopes((element.get("properties") or {}).get(airegister.SCOPE_PROPERTY))
            )
        assert tagged == expected, f"{root.name} has {tagged} tagged elements, tests assume {expected}"
