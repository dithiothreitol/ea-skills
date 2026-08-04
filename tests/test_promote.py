"""Promotion is the only staging -> approved write path, and its gate judges the
merged result by approved-zone standards. Staging itself validates as an overlay."""

import shutil
from datetime import date
from pathlib import Path

import pytest

from easkills import cli, dsl, promote, validate

TODAY = date(2026, 8, 1)


@pytest.fixture()
def repo(tmp_path, example_root) -> Path:
    """A copy of the worked example with an empty staging zone."""
    target = tmp_path / "repo"
    shutil.copytree(example_root, target)
    (target / "model" / "staging").mkdir(exist_ok=True)
    return target


GOOD_STAGING = """\
elements:
  - id: app-service-desk-tool
    type: ApplicationComponent
    name: Service Desk Tool
    documentation: Where the service desk keys in e-mailed spreadsheet orders.
    owner: it-service@aurorafoods.example
    lastReviewed: 2026-07-31
    provenance:
      - fact: fact-manual-order-entry

relationships:
  - id: rel-service-desk-tool-realizes-order-management
    type: Realization
    source: app-service-desk-tool
    target: cap-order-management
    provenance:
      - fact: fact-manual-order-entry
"""

UNGOVERNED_STAGING = """\
elements:
  - id: app-proposed
    type: ApplicationComponent
    name: Proposed Application
    provenance:
      - fact: fact-manual-order-entry

relationships:
  - id: rel-proposed-realizes-order-management
    type: Realization
    source: app-proposed
    target: cap-order-management
    provenance:
      - fact: fact-manual-order-entry
"""


def _stage(repo: Path, name: str, content: str) -> Path:
    path = repo / "model" / "staging" / name
    path.write_text(content, encoding="utf-8")
    return path


# ------------------------------------------------------------------- overlay semantics


def test_staging_relationship_may_reference_approved_elements(repo):
    """Staging is a delta: a proposed relationship to an approved element is not REF001."""
    _stage(repo, "proposal.yaml", GOOD_STAGING)
    report = validate.validate(repo, zone="staging", today=TODAY)
    assert not [f for f in report.errors if f.code == "REF001"], report.render()
    assert report.ok


def test_staging_same_id_is_an_update_proposal_not_a_duplicate(repo):
    _stage(
        repo,
        "update.yaml",
        """\
elements:
  - id: app-wms
    type: ApplicationComponent
    name: Warehouse Management System
    documentation: Updated description proposed from a new interview.
    owner: logistics-it@aurorafoods.example
    lastReviewed: 2026-07-31
    provenance:
      - fact: fact-wms-role
""",
    )
    report = validate.validate(repo, zone="staging", today=TODAY)
    assert not [f for f in report.errors if f.code == "ID001"], report.render()
    assert report.ok


def test_missing_governance_metadata_warns_in_staging_but_blocks_promotion(repo):
    _stage(repo, "proposal.yaml", UNGOVERNED_STAGING)
    staging_report = validate.validate(repo, zone="staging", today=TODAY)
    assert staging_report.ok, staging_report.render()
    assert any(f.code == "GOV001" for f in staging_report.warnings)

    result = promote.promote(repo, today=TODAY)
    assert not result.ok
    assert any(f.code == "GOV001" for f in result.report.errors)
    # Nothing moved: the file is still in staging.
    assert (repo / "model" / "staging" / "proposal.yaml").exists()
    assert not (repo / "model" / "approved" / "proposal.yaml").exists()


# ------------------------------------------------------------------------- promotion


def test_promote_moves_clean_staging_into_approved(repo):
    _stage(repo, "proposal.yaml", GOOD_STAGING)
    result = promote.promote(repo, today=TODAY)
    assert result.ok and result.moved
    assert not (repo / "model" / "staging" / "proposal.yaml").exists()
    assert (repo / "model" / "approved" / "proposal.yaml").exists()

    after = validate.validate(repo, zone="approved", today=TODAY)
    assert after.ok, after.render()
    model, _docs, _config = dsl.load(repo, "approved")
    assert "app-service-desk-tool" in model.elements


def test_promote_dry_run_moves_nothing(repo):
    _stage(repo, "proposal.yaml", GOOD_STAGING)
    result = promote.promote(repo, dry_run=True, today=TODAY)
    assert result.ok and not result.moved
    assert (repo / "model" / "staging" / "proposal.yaml").exists()
    assert not (repo / "model" / "approved" / "proposal.yaml").exists()


def test_promote_subset_leaves_other_staging_files(repo):
    _stage(repo, "good.yaml", GOOD_STAGING)
    _stage(repo, "not-ready.yaml", UNGOVERNED_STAGING)
    result = promote.promote(repo, files=[Path("model/staging/good.yaml")], today=TODAY)
    assert result.ok and result.moved, result.report.render()
    assert (repo / "model" / "approved" / "good.yaml").exists()
    assert (repo / "model" / "staging" / "not-ready.yaml").exists()


def test_promote_update_replaces_the_approved_file(repo):
    """Promoting a file whose relative path exists in approved is an update."""
    original = (repo / "model" / "approved" / "application.yaml").read_text(encoding="utf-8")
    updated = original.replace(
        "Customer-facing ordering web application. Holds no stock data of its own.",
        "Customer-facing ordering web application. Publishes prices; holds no stock data.",
    )
    assert updated != original
    _stage(repo, "application.yaml", updated)
    result = promote.promote(repo, today=TODAY)
    assert result.ok and result.moved, result.report.render()
    promoted = (repo / "model" / "approved" / "application.yaml").read_text(encoding="utf-8")
    assert "Publishes prices" in promoted


def test_promotion_is_blocked_when_a_replacement_would_dangle_a_reference(repo):
    """The gate must validate what the *move* produces, not a union of both files.

    Promotion renames staging/x.yaml onto approved/x.yaml, so everything the approved
    file held and the staging file leaves out is deleted. The gate used to merge the two
    files id-by-id, validate that union, pass -- and then the move deleted content the
    gate had just seen, leaving the approved zone with dangling references.
    """
    approved = (repo / "model" / "approved" / "application.yaml").read_text(encoding="utf-8")
    kept, _sep, _dropped = approved.partition("  - id: app-wms")
    assert _sep, "the example's application.yaml should hold more than one component"
    _stage(repo, "application.yaml", kept)

    result = promote.promote(repo, today=TODAY)
    assert not result.ok, "dropping a referenced element must block promotion"
    assert any(f.code == "REF001" for f in result.report.errors), result.report.render()
    assert not result.moved
    # The repository is untouched and still valid.
    assert validate.validate(repo, zone="approved", today=TODAY).ok


def test_a_replacement_that_drops_unreferenced_content_is_reported(repo):
    """A clean gate is not silence: deletions are named before the commit signs them."""
    _stage(
        repo,
        "spare.yaml",
        """\
elements:
  - id: app-spare-tool
    type: ApplicationComponent
    name: Spare Tool
    owner: it-service@aurorafoods.example
    lastReviewed: 2026-07-31
    provenance:
      - fact: fact-manual-order-entry
""",
    )
    promote.promote(repo, today=TODAY)  # app-spare-tool is now approved, referenced by nothing

    _stage(repo, "spare.yaml", "elements: []\n")
    result = promote.promote(repo, dry_run=True, today=TODAY)
    assert result.ok, result.report.render()
    assert result.dropped == ["app-spare-tool"]
    assert "model/approved/spare.yaml" in result.replaced
    rendered = result.render()
    assert "app-spare-tool" in rendered and "removes 1 approved concept" in rendered


def test_the_staging_view_shows_the_post_move_truth(repo):
    """`validate --zone staging` uses the same shadowing, so drafting sees the result."""
    approved = (repo / "model" / "approved" / "application.yaml").read_text(encoding="utf-8")
    kept, _sep, _dropped = approved.partition("  - id: app-wms")
    _stage(repo, "application.yaml", kept)
    report = validate.validate(repo, zone="staging", today=TODAY)
    assert any(f.code == "REF001" for f in report.errors), report.render()


def test_promote_refuses_files_outside_staging(repo):
    with pytest.raises(promote.PromoteError):
        promote.promote(repo, files=[Path("model/approved/application.yaml")], today=TODAY)


def test_promote_with_empty_staging_is_an_error(repo):
    with pytest.raises(promote.PromoteError):
        promote.promote(repo, today=TODAY)


# ------------------------------------------------------------------------------- CLI


def test_cli_promote_happy_path(repo, capsys):
    _stage(repo, "proposal.yaml", GOOD_STAGING)
    assert cli.main(["promote", "--root", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "promoted" in out
    assert not (repo / "model" / "staging" / "proposal.yaml").exists()


def test_cli_promote_blocked_exits_one(repo, capsys):
    _stage(repo, "proposal.yaml", UNGOVERNED_STAGING)
    assert cli.main(["promote", "--root", str(repo)]) == 1
    assert "blocked" in capsys.readouterr().out
