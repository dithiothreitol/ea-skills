"""Every documented rule code must actually fire on the negative fixture.

A validator whose rules are never exercised is decoration, so the broken fixture is
part of the contract: adding a rule means adding a fixture case for it.
"""

from datetime import date

import pytest

from easkills import validate


@pytest.fixture(scope="module")
def example_report(example_root):
    return validate.validate(example_root, zone="approved", today=date(2026, 7, 30))


@pytest.fixture(scope="module")
def broken_report(broken_root):
    return validate.validate(broken_root, zone="approved", today=date(2026, 7, 30))


@pytest.fixture(scope="module")
def broken_codes(broken_report):
    return {f.code for f in broken_report.findings}


# --------------------------------------------------------------------------- positive


def test_example_model_is_clean(example_report):
    assert example_report.ok, "\n".join(f.render() for f in example_report.errors)
    assert not example_report.warnings, "\n".join(f.render() for f in example_report.warnings)


def test_example_model_counts(example_report):
    assert example_report.counts["elements"] == 20
    assert example_report.counts["relationships"] == 19
    assert example_report.counts["views"] == 4


def test_example_model_declares_its_assumptions(example_report):
    codes = [f.code for f in example_report.findings]
    assert codes.count("PROV006") == 2, "the worked example should demonstrate the 'assumed' path"


def test_example_model_uses_fact_reference_provenance(example_root):
    """The motivation layer cites facts, and those facts' quotes verify cleanly."""
    from easkills import dsl

    model, _docs, _config = dsl.load(example_root, "approved")
    requirement = model.elements["req-po-retention"]
    assert any(p.fact == "fact-po-retention" for p in requirement.provenance)
    assert requirement.applies_to == ["data-order-record", "app-erp-core"]


# --------------------------------------------------------------------------- negative

EXPECTED_ERROR_CODES = [
    "SCHEMA001",  # not an ArchiMate concept
    "SCHEMA002",  # unusable ea.config.yaml value (threshold out of range)
    "ID001",  # duplicate identifier across files
    "REF001",  # relationship endpoint missing
    "REF002",  # view references unknown element
    "PROV001",  # no provenance, not assumed
    "PROV002",  # provenance source file missing
    "PROV003",  # quote absent from the source
    "PROV005",  # assumed without rationale
    "PROV007",  # provenance references a fact missing from the register
    "PROV008",  # provenance file resolves outside the repository
    "MOT001",  # appliesTo target does not exist
    "MOT002",  # appliesTo on a non-Motivation element
    "ISO001",  # view frames an unknown concern
    "ISO002",  # stakeholder holds an unknown concern
    "STD001",  # references a standard that is not in the SIB
    "STD002",  # references a retired standard without a dispensation
    "GOV001",  # no owner in approved zone
    "GOV002",  # no review date in approved zone
    "GOV003",  # unparseable review date
    "REL001",  # relationship not permitted by the matrix
    "REL002",  # structural cycle
]

EXPECTED_WARNING_CODES = [
    "PROV004",  # quote only approximately matched
    "GOV004",  # stale review date
    "NAME001",  # placeholder in name
    "NAME004",  # duplicate name within a type
    "REL003",  # duplicate relationship
    "REF003",  # empty view
    "SMELL001",  # isolated element
    "ISO003",  # concern framed by no view
    "ISO004",  # stakeholder with no concerns
    "ISO005",  # view frames no declared concern
    "ISO006",  # concern held by no stakeholder
    "STD003",  # references a deprecated standard
]


def test_dispensation_coverage_is_informational(example_report):
    """A retired standard covered by an open dispensation reports STD004 (info),
    not an error -- the waiver is the governance mechanism working."""
    findings = [f for f in example_report.findings if f.code == "STD004"]
    assert len(findings) == 2
    assert all(f.severity == validate.SEVERITY_INFO for f in findings)
    assert "disp-onprem-legacy" in findings[0].message


@pytest.mark.parametrize("code", EXPECTED_ERROR_CODES)
def test_error_rule_fires(broken_report, code):
    matches = [f for f in broken_report.errors if f.code == code]
    assert matches, f"{code} did not fire on the negative fixture"


@pytest.mark.parametrize("code", EXPECTED_WARNING_CODES)
def test_warning_rule_fires(broken_report, code):
    matches = [f for f in broken_report.warnings if f.code == code]
    assert matches, f"{code} did not fire on the negative fixture"


def test_broken_fixture_fails_overall(broken_report):
    assert not broken_report.ok


# ------------------------------------------------------------------ robustness of the gate


def test_provenance_cannot_be_verified_against_a_file_outside_the_repository(tmp_path):
    """A quote located outside the repository is unreviewable traceability.

    Before PROV008 this passed with zero errors: the citation escaped the repository,
    the quote was found in a file no reviewer can see, and -- running in CI on
    untrusted content -- pass/fail leaked whether a string exists on the runner.
    """
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("the deployment key is hunter2\n", encoding="utf-8")
    root = tmp_path / "repo"
    (root / "model" / "approved").mkdir(parents=True)
    (root / "model/approved/m.yaml").write_text(
        "elements:\n"
        "  - id: cap-x\n    type: Capability\n    name: Capability X\n"
        "    owner: owner@example.test\n    lastReviewed: 2026-07-01\n"
        "    provenance:\n      - file: ../outside-secret.txt\n"
        "        quote: the deployment key is hunter2\n",
        encoding="utf-8",
        newline="\n",
    )
    report = validate.validate(root, zone="approved", today=date(2026, 7, 30))
    assert not report.ok
    assert [f.code for f in report.errors] == ["PROV008"]


def test_an_impossible_unquoted_date_is_a_finding_not_a_traceback(tmp_path):
    """`lastReviewed: 2026-06-31` is a one-character typo, not a reason to crash.

    PyYAML resolves unquoted ISO dates to ``datetime.date`` *while parsing*, so an
    impossible one raises a bare ValueError -- which the loaders did not catch, taking
    every command down with a traceback instead of reporting the file.
    """
    root = tmp_path / "repo"
    (root / "model" / "approved").mkdir(parents=True)
    (root / "model/approved/m.yaml").write_text(
        "elements:\n"
        "  - id: cap-x\n    type: Capability\n    name: Capability X\n"
        "    owner: owner@example.test\n    lastReviewed: 2026-06-31\n"
        "    assumed: true\n    rationale: Probe element with a date that is not a date.\n",
        encoding="utf-8",
        newline="\n",
    )
    report = validate.validate(root, zone="approved", today=date(2026, 7, 30))
    assert not report.ok
    assert "SCHEMA000" in {f.code for f in report.errors}


@pytest.mark.parametrize(
    "line",
    [
        "stalenessDays: soon",  # not a number at all
        "stalenessDays: 0",  # below the usable minimum
        "quoteMatchThreshold: 90",  # a ratio written as a percentage
        "factsRoot: ../..",  # citations would resolve outside the repository
    ],
)
def test_unusable_config_values_are_findings_not_crashes(tmp_path, line):
    """A gate that raises reports nothing at all -- the worst possible outcome."""
    root = tmp_path / "repo"
    (root / "model" / "approved").mkdir(parents=True)
    (root / "ea.config.yaml").write_text(f"name: Probe\n{line}\n", encoding="utf-8", newline="\n")
    (root / "model/approved/m.yaml").write_text(
        "elements:\n"
        "  - id: cap-x\n    type: Capability\n    name: Capability X\n"
        "    owner: owner@example.test\n    lastReviewed: 2026-07-01\n"
        "    assumed: true\n    rationale: Probe element for a config-robustness test.\n",
        encoding="utf-8",
        newline="\n",
    )
    report = validate.validate(root, zone="approved", today=date(2026, 7, 30))
    assert "SCHEMA002" in {f.code for f in report.errors}


def test_default_thresholds_still_apply_when_the_config_is_unusable(tmp_path):
    """The fallback must be the documented default, not an accidental extreme."""
    from easkills import dsl

    value, problem = dsl.config_number({"quoteMatchThreshold": 90}, "quoteMatchThreshold", 0.90, 0.0, 1.0)
    assert (value, bool(problem)) == (0.90, True)
    value, problem = dsl.config_number({"stalenessDays": True}, "stalenessDays", 365, minimum=1)
    assert (value, bool(problem)) == (365, True)
    value, problem = dsl.config_number({"stalenessDays": "180"}, "stalenessDays", 365, minimum=1)
    assert (value, problem) == (180, "")


def test_matrix_violation_names_the_permitted_alternatives(broken_report):
    finding = next(f for f in broken_report.findings if f.code == "REL001" and f.concept == "rel-illegal")
    assert "Association" in finding.message
    assert "3.2" in finding.message


def test_matrix_violation_detects_swapped_endpoints(broken_report):
    finding = next(f for f in broken_report.findings if f.code == "REL001" and f.concept == "rel-swapped")
    assert "opposite direction" in finding.message


def test_structural_cycle_reports_its_path(broken_report):
    finding = next(f for f in broken_report.errors if f.code == "REL002")
    assert "node-a" in finding.message and "node-b" in finding.message
    assert finding.file, "cycle finding should point at a file"


def test_fabricated_citation_is_an_error_not_a_warning(broken_report):
    finding = next(f for f in broken_report.findings if f.concept == "fabricated-quote" and f.code == "PROV003")
    assert finding.severity == validate.SEVERITY_ERROR


def test_paraphrased_citation_is_a_warning(broken_report):
    finding = next(f for f in broken_report.findings if f.concept == "paraphrased-quote")
    assert finding.code == "PROV004"
    assert finding.severity == validate.SEVERITY_WARNING


# --------------------------------------------------------------------------- zone rules


def test_governance_metadata_is_advisory_in_staging(tmp_path, broken_root):
    """Staging holds machine proposals: missing ownership warns, it does not block."""
    import shutil

    shutil.copytree(broken_root, tmp_path / "repo")
    staging = tmp_path / "repo" / "model" / "staging"
    # The fixture carries its own staging proposal (for ALN007). This test is about the
    # zone rules applied to the *approved* content, so that proposal is cleared first --
    # otherwise the move below lands inside it instead of becoming it.
    if staging.is_dir():
        shutil.rmtree(staging)
    staging.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp_path / "repo" / "model" / "approved"), str(staging))

    report = validate.validate(tmp_path / "repo", zone="staging", today=date(2026, 7, 30))
    codes_by_severity = {(f.code, f.severity) for f in report.findings}
    assert ("GOV001", validate.SEVERITY_WARNING) in codes_by_severity
    assert ("GOV002", validate.SEVERITY_WARNING) in codes_by_severity
    # Semantic errors are never downgraded, whatever the zone.
    assert ("REL001", validate.SEVERITY_ERROR) in codes_by_severity


def test_empty_repository_is_valid(tmp_path):
    report = validate.validate(tmp_path, zone="approved")
    assert report.ok
    assert report.counts["elements"] == 0


def test_report_serializes_to_json(example_report):
    payload = example_report.as_dict()
    assert payload["ok"] is True
    assert payload["counts"]["elements"] == 20
    assert isinstance(payload["findings"], list)
