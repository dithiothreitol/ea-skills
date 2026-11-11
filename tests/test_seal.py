"""The approval seal (D4): approved content changed outside `promote` fails the model gate.

Each test is one way approved content can change -- edited, added, deleted, promoted --
and what the gate must say about it, plus the ramp that keeps an unsealed repository from
failing for not having adopted yet, and the refusals that keep the seal from being
laundered.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from easkills import cli, promote, seal, validate
from easkills.validate import SEVERITY_ERROR, SEVERITY_INFO

SIGNED = {"approved_by": "board@example.test", "as_of": "2026-08-01"}


@pytest.fixture()
def unsealed(tmp_path, example_root) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(example_root, root, ignore=shutil.ignore_patterns("docs", "build", "approvals"))
    return root


@pytest.fixture()
def sealed(unsealed) -> Path:
    result = promote.seal_existing(unsealed, **SIGNED)
    assert result.ok and result.record is not None
    return unsealed


def _apr(root: Path) -> list:
    return [f for f in validate.validate(root).findings if f.code.startswith("APR")]


def test_an_unsealed_zone_is_told_once_and_never_fails(unsealed):
    findings = _apr(unsealed)
    assert [(f.code, f.severity) for f in findings] == [("APR001", SEVERITY_INFO)]
    assert "--seal-existing" in findings[0].message
    assert validate.validate(unsealed).ok


def test_the_worked_example_is_sealed_and_clean(example_root):
    assert seal.record_files(example_root), "the worked example demonstrates the seal"
    assert _apr(example_root) == []


def test_sealing_vouches_for_every_approved_file(sealed):
    records, problems = seal.load_records(sealed)
    assert problems == [] and len(records) == 1 and records[0].kind == "seal"
    assert set(records[0].files) == {seal.relative(sealed, f) for f in seal.approved_files(sealed)}
    assert _apr(sealed) == []


def test_an_edit_outside_promote_fails_the_gate(sealed):
    target = sealed / "model" / "approved" / "application.yaml"
    target.write_text(target.read_text(encoding="utf-8") + "# edited by hand\n", encoding="utf-8")
    findings = _apr(sealed)
    assert [(f.code, f.severity, f.file) for f in findings] == [
        ("APR001", SEVERITY_ERROR, "model/approved/application.yaml")
    ]
    assert "changed since it was approved" in findings[0].message
    assert not validate.validate(sealed).ok


def test_a_file_added_outside_promote_fails_the_gate(sealed):
    (sealed / "model" / "approved" / "smuggled.yaml").write_text("elements: []\n", encoding="utf-8")
    assert [(f.code, f.file) for f in _apr(sealed)] == [("APR001", "model/approved/smuggled.yaml")]


def test_a_file_deleted_outside_promote_fails_the_gate(sealed):
    (sealed / "model" / "approved" / "views.yaml").unlink()
    findings = _apr(sealed)
    assert ("APR003", "model/approved/views.yaml") in [(f.code, f.file) for f in findings]


def test_a_promotion_writes_the_record_that_vouches_for_it(sealed):
    staging = sealed / "model" / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    shutil.copy(sealed / "model" / "approved" / "technology.yaml", staging / "technology.yaml")
    text = (staging / "technology.yaml").read_text(encoding="utf-8")
    (staging / "technology.yaml").write_text(text.replace("lastReviewed: 2026-06-30", "lastReviewed: 2026-07-31", 1), encoding="utf-8")
    result = promote.promote(sealed, today=None, **SIGNED)
    assert result.ok and result.record is not None
    assert result.record.name == "approval-2026-08-01-02.yaml", "the seal of the same day is -01"
    record = seal.load_records(sealed)[0][-1]
    assert record.kind == "promotion" and record.approved_by == "board@example.test"
    assert list(record.files) == ["model/approved/technology.yaml"]
    text = result.record.read_text(encoding="utf-8")
    assert "changed:" in text and "added:" not in text
    assert _apr(sealed) == [], "the promoted file is vouched for by the new record"


def test_record_ids_run_in_order_within_a_day(sealed):
    assert seal.next_record_id(sealed, "2026-08-01") == "approval-2026-08-01-02", "the seal took -01"
    assert seal.next_record_id(sealed, "2026-08-02") == "approval-2026-08-02-01"


def test_a_real_promotion_must_say_who_signed_and_when(sealed):
    (sealed / "model" / "staging").mkdir(exist_ok=True)
    with pytest.raises(promote.PromoteError, match="--approved-by"):
        promote.promote(sealed)
    with pytest.raises(promote.PromoteError, match="real date"):
        promote.promote(sealed, approved_by="x", as_of="2026-02-30")
    # The dry run moves nothing and signs nothing, so it needs neither.
    shutil.copy(sealed / "model" / "approved" / "technology.yaml", sealed / "model" / "staging" / "technology.yaml")
    assert promote.promote(sealed, dry_run=True).record is None


def test_sealing_twice_is_refused(sealed):
    with pytest.raises(promote.PromoteError, match="already sealed"):
        promote.seal_existing(sealed, **SIGNED)


def test_an_invalid_approved_zone_is_not_sealed(unsealed):
    target = unsealed / "model" / "approved" / "relations.yaml"
    target.write_text(target.read_text(encoding="utf-8").replace("source: app-order-portal", "source: app-ghost", 1), encoding="utf-8")
    result = promote.seal_existing(unsealed, **SIGNED)
    assert not result.ok and result.record is None
    assert not seal.record_files(unsealed)


def test_the_record_is_byte_stable(tmp_path, example_root):
    bodies = []
    for name in ("a", "b"):
        root = tmp_path / name
        shutil.copytree(example_root, root, ignore=shutil.ignore_patterns("docs", "build", "approvals"))
        bodies.append(promote.seal_existing(root, **SIGNED).record.read_bytes())
    assert bodies[0] == bodies[1]


def test_the_cli_seals_and_refuses_a_file_selection(unsealed):
    base = ["promote", "--root", str(unsealed), "--seal-existing"]
    assert cli.main([*base, "--file", "model/staging/x.yaml", "--approved-by", "x", "--as-of", "2026-08-01"]) == 1
    assert cli.main([*base, "--approved-by", "x", "--as-of", "2026-08-01"]) == 0
    assert cli.main([*base, "--approved-by", "x", "--as-of", "2026-08-02"]) == 1, "already sealed"


@pytest.mark.parametrize("code", ["APR001", "APR002", "APR003"])
def test_every_seal_rule_fires_on_the_negative_fixture(broken_root, code):
    findings = [f for f in validate.validate(broken_root).findings if f.code == code]
    assert findings and all(f.severity == SEVERITY_ERROR for f in findings)


def test_the_promotion_gate_does_not_judge_the_seal(sealed):
    """The promotion gate judges a merge that is not on disk yet; the staged file is
    unsealed by definition, and the record that seals it is what the promotion writes."""
    (sealed / "model" / "staging").mkdir(exist_ok=True)
    shutil.copy(sealed / "model" / "approved" / "technology.yaml", sealed / "model" / "staging" / "technology.yaml")
    report = validate.validate_promotion(sealed)
    assert not [f for f in report.findings if f.code.startswith("APR")]


# ------------------------------------------------- found by the session review (0.22.0)


def test_restoring_an_earlier_signed_version_by_hand_fails_the_gate(sealed):
    """Only the latest record naming a file counts: v1 was signed, then v2 was signed over
    it, and restoring v1 by hand undoes the second signature without anybody signing."""
    original = (sealed / "model" / "approved" / "technology.yaml").read_text(encoding="utf-8")
    staging = sealed / "model" / "staging"
    staging.mkdir(exist_ok=True)
    (staging / "technology.yaml").write_text(original.replace("lastReviewed: 2026-06-30", "lastReviewed: 2026-07-31", 1), encoding="utf-8")
    assert promote.promote(sealed, **SIGNED).ok
    (sealed / "model" / "approved" / "technology.yaml").write_text(original, encoding="utf-8")
    assert [(f.code, f.file) for f in _apr(sealed)] == [("APR001", "model/approved/technology.yaml")]


def test_a_line_ending_is_not_a_change(sealed):
    """git stores LF (`text=auto eol=lf`); a Windows editor writes CRLF. The digest is of the
    content, so the same content reads the same on every clone."""
    target = sealed / "model" / "approved" / "views.yaml"
    target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
    assert _apr(sealed) == []


def test_a_first_promotion_into_an_unsealed_zone_with_content_is_refused(unsealed):
    """Otherwise its record would vouch for the moved files only, every other approved file
    would fail APR001 at once, and --seal-existing would refuse because a record exists."""
    staging = unsealed / "model" / "staging"
    staging.mkdir(exist_ok=True)
    shutil.copy(unsealed / "model" / "approved" / "technology.yaml", staging / "technology.yaml")
    with pytest.raises(promote.PromoteError, match="--seal-existing"):
        promote.promote(unsealed, **SIGNED)
    assert not seal.record_files(unsealed) and (staging / "technology.yaml").is_file()
    assert promote.promote(unsealed, dry_run=True).ok, "the dry run still shows the plan"


def test_a_promotion_that_cannot_move_its_files_leaves_nothing_behind(sealed, monkeypatch):
    staging = sealed / "model" / "staging"
    staging.mkdir(exist_ok=True)
    shutil.copy(sealed / "model" / "approved" / "technology.yaml", staging / "technology.yaml")
    shutil.copy(sealed / "model" / "approved" / "views.yaml", staging / "views.yaml")
    real = promote.os.replace
    calls = {"n": 0}

    def flaky(source, target):
        calls["n"] += 1
        if calls["n"] == 3:  # the second staged file's move
            raise OSError("disk full")
        return real(source, target)

    monkeypatch.setattr(promote.os, "replace", flaky)
    with pytest.raises(promote.PromoteError, match="nothing was moved"):
        promote.promote(sealed, **SIGNED)
    monkeypatch.setattr(promote.os, "replace", real)
    assert sorted(p.name for p in staging.iterdir()) == ["technology.yaml", "views.yaml"]
    assert len(seal.record_files(sealed)) == 1, "the record of the failed promotion is removed"
    assert _apr(sealed) == []
