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
    assert example_report.counts["elements"] == 15
    assert example_report.counts["relationships"] == 15
    assert example_report.counts["views"] == 2


def test_example_model_declares_its_assumptions(example_report):
    codes = [f.code for f in example_report.findings]
    assert codes.count("PROV006") == 2, "the worked example should demonstrate the 'assumed' path"


# --------------------------------------------------------------------------- negative

EXPECTED_ERROR_CODES = [
    "SCHEMA001",  # not an ArchiMate concept
    "ID001",  # duplicate identifier across files
    "REF001",  # relationship endpoint missing
    "REF002",  # view references unknown element
    "PROV001",  # no provenance, not assumed
    "PROV002",  # provenance source file missing
    "PROV003",  # quote absent from the source
    "PROV005",  # assumed without rationale
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
]


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
    assert payload["counts"]["elements"] == 15
    assert isinstance(payload["findings"], list)
