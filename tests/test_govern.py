"""Governance records: every documented SIB/DEC/DISP/COMP rule fires on the negative
fixture, the example's governance log stays clean, and expiry is loud."""

from datetime import date

import pytest

from easkills import cli, govern, validate

TODAY = date(2026, 7, 30)


@pytest.fixture(scope="module")
def example_report(example_root):
    return govern.validate_governance(example_root, today=TODAY)


@pytest.fixture(scope="module")
def broken_report(broken_root):
    return govern.validate_governance(broken_root, today=TODAY)


# --------------------------------------------------------------------------- positive


def test_example_governance_is_clean(example_report):
    assert example_report.ok, "\n".join(f.render() for f in example_report.errors)
    assert not example_report.warnings, "\n".join(f.render() for f in example_report.warnings)


def test_example_governance_counts(example_report):
    assert example_report.counts == {
        "standards": 3,
        "decisions": 1,
        "dispensations": 1,
        "assessments": 1,
        "services": 3,
        "requests": 2,
    }


def test_open_dispensation_covers_the_pair(example_root):
    governance = govern.load(example_root)
    assert governance.covering("app-erp-core", "std-onprem-hosting", TODAY) is not None
    # After expiry the cover is gone -- no code change needed, just time passing.
    assert governance.covering("app-erp-core", "std-onprem-hosting", date(2027, 7, 1)) is None


def test_expired_dispensation_turns_std004_into_std002(example_root):
    """The example's waiver expires 2027-06-30; validated after that date, the same
    model must fail with STD002 -- expiry re-triggers review by design."""
    report = validate.validate(example_root, zone="approved", today=date(2027, 7, 15))
    codes = {f.code for f in report.errors}
    assert "STD002" in codes


# --------------------------------------------------------------------------- negative

EXPECTED_ERROR_CODES = [
    "SIB000",  # unparseable standard file
    "SIB002",  # duplicate standard id
    "SIB003",  # successor not in the SIB
    "DISP001",  # no expiry (schema)
    "DISP003",  # expired and still open
    "DISP004",  # applies to unknown element
    "DISP005",  # waives unknown standard
    "DISP007",  # expires before granted
    "DEC001",  # no rationale (schema)
    "DEC003",  # supersededBy unknown
    "DEC005",  # relatedElements unknown
    "COMP004",  # followUp references unknown records
    "COMP005",  # relatedElements unknown
    "SVC001",  # offering violates the service schema (no owner/SLA)
    "SVC002",  # duplicate service id
    "REQ003",  # request references an unknown offering
    "REQ004",  # request scope names an unknown element
    "REQ005",  # fulfilled without date or deliverable pointer
]

EXPECTED_WARNING_CODES = [
    "SIB004",  # retired/deprecated standard with no successor
    "DISP006",  # expires within the review window
    "DEC004",  # superseded without supersededBy
    "COMP003",  # non-conformant without follow-up
    "REQ006",  # open request past the offering's SLA
    "REQ007",  # declined without a reason
    "REQ008",  # requests a retired offering
]


@pytest.mark.parametrize("code", EXPECTED_ERROR_CODES)
def test_error_rule_fires(broken_report, code):
    matches = [f for f in broken_report.errors if f.code == code]
    assert matches, f"{code} did not fire on the negative fixture"


@pytest.mark.parametrize("code", EXPECTED_WARNING_CODES)
def test_warning_rule_fires(broken_report, code):
    matches = [f for f in broken_report.warnings if f.code == code]
    assert matches, f"{code} did not fire on the negative fixture"


def test_broken_governance_fails_overall(broken_report):
    assert not broken_report.ok


def test_repo_without_governance_dirs_is_valid(tmp_path):
    report = govern.validate_governance(tmp_path, today=TODAY)
    assert report.ok
    assert report.counts["standards"] == 0


# ------------------------------------------------------------------------------- CLI


def test_cli_validate_gov_exit_codes(example_root, broken_root, capsys):
    assert cli.main(["validate-gov", "--root", str(example_root), "--as-of", "2026-07-30"]) == 0
    assert cli.main(["validate-gov", "--root", str(broken_root), "--as-of", "2026-07-30"]) == 1
    capsys.readouterr()
