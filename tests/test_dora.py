"""The DORA Register of Information: a generator that names what it does not know.

Two things are tested here that no other report in this repository has to prove. First,
that the document refuses to exist when nothing is in scope -- a page that looks like a
filing and says nothing is the worst artifact this command could produce. Second, that
its completeness claim is *tested* rather than asserted: every field the model does not
carry appears in the gap section, with element ids.
"""

from datetime import date

import pytest
import yaml
from jsonschema import Draft202012Validator

from easkills import dora, genschema

TODAY = date(2026, 7, 30)
CODES = ("REG001", "REG002", "REG003", "REG004")


@pytest.fixture(scope="module")
def finco(repo_root):
    return repo_root / "eval" / "fixtures" / "finco"


@pytest.fixture(scope="module")
def finco_broken(repo_root):
    return repo_root / "eval" / "fixtures" / "finco-broken"


@pytest.fixture(scope="module")
def clean(finco):
    return dora.build(finco, today=TODAY)


@pytest.fixture(scope="module")
def broken(finco_broken):
    return dora.build(finco_broken, today=TODAY)


# ------------------------------------------------------------------------------ scope


def test_the_worked_example_is_out_of_scope_and_says_so(example_root):
    """Aurora Foods is a food wholesaler. DORA does not apply, and tagging the example to
    demonstrate the feature would have taught the wrong thing about scope -- which is why
    this increment ships a dedicated fixture instead, following the `ea-check` precedent.
    """
    register = dora.build(example_root, today=TODAY)
    assert not register.in_scope
    assert register.ok and not register.findings
    assert "Nothing is in scope" in dora.render(register)


def test_no_scope_means_no_document_at_all(example_root):
    """Not an empty register: *no* register. An empty document that looks like a filing
    is worse than no document, and the CLI turns this refusal into exit 1 rather than
    writing the file."""
    with pytest.raises(dora.DoraError) as exc:
        dora.markdown(dora.build(example_root, today=TODAY))
    assert "nothing to register" in str(exc.value)


def test_scope_is_declared_never_inferred_from_a_type(clean):
    """`app-internal-reporting` is an application component like the others and is built
    in house. Inferring scope from a type would sweep it in, and a register padded with
    things nobody outsourced is as wrong as one missing something."""
    assert "app-internal-reporting" not in {entry.id for entry in clean.entries}
    assert len(clean.entries) == 6


# ---------------------------------------------------------------------------- the rules


@pytest.mark.parametrize("code", CODES)
def test_every_documented_reg_code_has_a_provoking_fixture(code, clean, broken):
    """The triple every rule in this repository ships with: the check, a fixture that
    violates it, a row in RULES.md. REG003 is the one the *clean* fixture carries -- an
    open waiver on a critical service is exposure, not a defect."""
    fired = {f.code for f in clean.findings} | {f.code for f in broken.findings}
    assert code in fired


def test_reg001_names_the_element_with_no_criticality(broken):
    findings = [f for f in broken.findings if f.code == "REG001"]
    assert [f.concept for f in findings] == ["app-scope-without-criticality"]
    assert all(f.severity == "warning" for f in findings)


def test_reg002_is_an_error_and_names_which_field_is_missing(broken):
    findings = {f.concept: f for f in broken.findings if f.code == "REG002"}
    assert set(findings) == {"app-critical-without-provider", "app-critical-without-contract"}
    assert all(f.severity == "error" for f in findings.values())
    # Half-filled is still a gap, and the message says *which* half -- otherwise the
    # reader has to open the file to find out what to add.
    assert "no provider and no contractRef" in findings["app-critical-without-provider"].message
    assert "no contractRef" in findings["app-critical-without-contract"].message
    assert "provider" not in findings["app-critical-without-contract"].message.split("no contractRef")[0]


def test_reg003_is_information_because_a_waiver_is_not_a_violation(clean):
    """An open dispensation is a legitimate governance record. Making this a warning
    would push people to close waivers to clear a report, which loses the record of the
    exposure -- the exact thing the register exists to disclose."""
    findings = [f for f in clean.findings if f.code == "REG003"]
    assert [f.concept for f in findings] == ["app-card-processing"]
    assert all(f.severity == "info" for f in findings)
    assert clean.ok, "the clean fixture carries REG003 and still passes"
    assert not clean.warnings, "...and passes --strict too"


def test_reg003_is_silent_for_a_standard_element_under_a_waiver(finco_broken):
    """Only critical and important functions are register events. A waiver on an ordinary
    service is internal governance and belongs in `validate-gov`, not in a filing."""
    codes = {(f.code, f.concept) for f in dora.build(finco_broken, today=TODAY).findings}
    assert ("REG003", "app-scope-without-criticality") not in codes


def test_reg003_disappears_once_the_waiver_expires(finco):
    """Every date in this report moves with `--as-of` and never with the wall clock. The
    clean fixture's waiver expires 2027-03-31; a run after it must not still disclose it.
    """
    later = dora.build(finco, today=date(2027, 4, 1))
    assert not [f for f in later.findings if f.code == "REG003"]
    assert not later.waivers


def test_reg004_fires_per_empty_section_and_only_with_content_in_scope(broken, example_root):
    sections = {f.locator for f in broken.findings if f.code == "REG004"}
    assert sections == {"contractual arrangements", "functions supported"}
    assert not any(f.code == "REG004" for f in dora.build(example_root, today=TODAY).findings), (
        "an out-of-scope repository has no empty sections, it has no register"
    )
    # No file on the finding: the defect belongs to the register, not to one element's
    # file, and pointing at an arbitrary one sends the reader somewhere nothing is wrong.
    assert all(f.file == "" for f in broken.findings if f.code == "REG004")


# ----------------------------------------------------------------- the register itself


def test_the_register_names_its_own_gaps_with_element_ids(broken):
    """The feature. A register that quietly omitted the fields it could not fill would be
    indistinguishable from a complete one, and the person filing it would find out from a
    supervisor rather than from us."""
    gaps = {gap["field"]: gap["elements"] for gap in broken.gaps}
    assert set(gaps) == {"doraCriticality", "provider", "contractRef", "functions supported"}
    assert gaps["doraCriticality"] == ["app-scope-without-criticality"]
    assert "app-critical-without-contract" in gaps["contractRef"]
    document = dora.markdown(broken)
    assert "## What this register could not fill" in document
    for element_id in gaps["contractRef"]:
        assert element_id in document.split("## What this register could not fill")[1]


def test_a_complete_register_says_so_rather_than_omitting_the_section(clean):
    assert clean.gaps == []
    assert "Every field this document asks of the model is present" in dora.markdown(clean)


def test_the_document_refuses_to_pass_as_a_filing(clean):
    """The header is the legal honesty, and it is not optional. A generated document that
    could be mistaken for an attestation is the risk this whole increment carries."""
    document = dora.markdown(clean)
    for phrase in (
        "it is not a filing",
        "No legal review has taken place",
        "no completeness against the official templates is claimed",
        "decision for the people accountable for the filing",
    ):
        assert phrase in document
    assert document.index("it is not a filing") < document.index("## ICT third-party service providers"), (
        "the caveat must come before the tables, not after them"
    )


def test_a_provider_takes_the_highest_criticality_it_supports(clean):
    """PaySwitch AG runs one critical service and one important one. Rounding down would
    understate a provider whose failure stops a critical function."""
    payswitch = next(row for row in clean.providers if row["provider"] == "PaySwitch AG")
    assert payswitch["criticality"] == "critical"
    assert payswitch["elements"] == ["app-card-processing", "service-payment-initiation"]


def test_functions_carry_the_elements_that_support_them(clean):
    execution = next(row for row in clean.functions if row["id"] == "process-payment-execution")
    assert execution["criticality"] == "critical"
    assert execution["supportedBy"] == ["app-card-processing", "app-core-ledger", "service-payment-initiation"]
    # The out-of-scope internal tool serves onboarding but is not a register dependency.
    onboarding = next(row for row in clean.functions if row["id"] == "process-customer-onboarding")
    assert "app-internal-reporting" not in onboarding["supportedBy"]


def test_the_document_is_byte_stable(clean, finco):
    assert dora.markdown(clean) == dora.markdown(dora.build(finco, today=TODAY))


def test_the_document_ends_with_a_newline_and_uses_no_carriage_returns(clean):
    document = dora.markdown(clean)
    assert document.endswith("\n") and "\r" not in document


# ---------------------------------------------------------------------- the vocabulary


def test_the_scope_property_is_a_closed_enum():
    """Under-inclusion is the failure mode that matters in a regulatory report: a missing
    row does not announce itself. `regulatoryScope: DORA` as free text would drop the
    element out of the register and nothing downstream would ever say so."""
    properties = genschema.build_schema()["$defs"]["element"]["properties"]["properties"]["properties"]
    assert properties["regulatoryScope"]["enum"] == list(genschema.REGULATORY_SCOPES)
    assert properties["doraCriticality"]["enum"] == list(genschema.CRITICALITIES)
    assert dora.SCOPE_DORA in genschema.REGULATORY_SCOPES
    assert set(dora.CRITICALITY_ORDER) == set(genschema.CRITICALITIES)


def test_the_module_reads_the_same_vocabulary_the_schema_writes():
    assert dora.documented_vocabulary() == {
        "regulatoryScope": genschema.REGULATORY_SCOPES,
        "doraCriticality": genschema.CRITICALITIES,
    }


@pytest.mark.parametrize("value", ["DORA", "dora ", "nis2"])
def test_a_scope_value_the_tool_cannot_act_on_is_a_schema_error(value, tmp_path):
    element = {
        "elements": [
            {"id": "app-x", "type": "ApplicationComponent", "name": "X", "properties": {"regulatoryScope": value}}
        ]
    }
    errors = list(Draft202012Validator(genschema.build_schema()).iter_errors(element))
    assert errors, f"{value!r} validated cleanly -- it would silently leave the register"


def test_the_fixtures_stay_the_shape_the_tests_assume(finco, finco_broken):
    """Both fixtures are hand-authored, and a later edit that quietly drops the scope
    property would make half this module pass vacuously."""
    for root, expected in ((finco, 6), (finco_broken, 4)):
        tagged = 0
        for path in (root / "model" / "approved").glob("*.yaml"):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            tagged += sum(
                1
                for element in data.get("elements", [])
                if (element.get("properties") or {}).get(dora.SCOPE_PROPERTY) == dora.SCOPE_DORA
            )
        assert tagged == expected, f"{root.name} has {tagged} tagged elements, tests assume {expected}"
