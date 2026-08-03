"""The golden-set harness: gold must be clean, self-scoring must be perfect, and
degradations must show up in exactly the category that was degraded."""

import shutil
from pathlib import Path

import pytest

from easkills import cli, facts, score, validate

REPO_ROOT = Path(__file__).resolve().parents[1]
CLINIC = REPO_ROOT / "eval" / "golden" / "clinic"


@pytest.fixture()
def candidate(tmp_path) -> Path:
    target = tmp_path / "candidate"
    shutil.copytree(CLINIC, target)
    return target


# ----------------------------------------------------------------- gold is actually gold


def test_golden_clinic_model_is_clean():
    report = validate.validate(CLINIC, zone="approved")
    assert report.ok and not report.warnings, report.render()


def test_golden_clinic_facts_are_clean():
    report = facts.validate_facts(CLINIC)
    assert report.ok and not report.warnings, report.render()


def test_self_score_is_perfect():
    report = score.score(CLINIC, CLINIC)
    assert report.min_f1 == 1.0
    assert report.gates_ok


def test_example_self_score_is_perfect(example_root):
    report = score.score(example_root, example_root)
    assert report.min_f1 == 1.0


# ------------------------------------------------------------------------ degradations


def _model_file(root: Path) -> Path:
    return root / "model" / "approved" / "clinic.yaml"


def _register_file(root: Path) -> Path:
    return root / "facts" / "register" / "interview-clinic.yaml"


def test_missing_fact_lowers_fact_recall_only(candidate):
    text = _register_file(candidate).read_text(encoding="utf-8")
    head, _sep, _tail = text.partition("  - id: fact-backup-untested")
    _register_file(candidate).write_text(head, encoding="utf-8")
    report = score.score(candidate, CLINIC)
    assert report.categories["facts"].recall < 1.0
    assert report.categories["facts"].precision == 1.0
    assert report.categories["elements"].f1 == 1.0


def test_renamed_element_lowers_element_score_and_its_relationships(candidate):
    text = _model_file(candidate).read_text(encoding="utf-8")
    _model_file(candidate).write_text(text.replace("name: Booking Portal", "name: Appointment App"), encoding="utf-8")
    report = score.score(candidate, CLINIC)
    elements = report.categories["elements"]
    assert elements.matched == elements.gold - 1
    # Relationships touching the renamed element can no longer be matched.
    assert report.categories["relationships"].recall < 1.0
    assert report.categories["facts"].f1 == 1.0


def test_swapped_relationship_type_lowers_relationship_score(candidate):
    text = _model_file(candidate).read_text(encoding="utf-8")
    _model_file(candidate).write_text(
        text.replace(
            "  - id: rel-server-serves-ehr\n    type: Serving",
            "  - id: rel-server-serves-ehr\n    type: Association",
        ),
        encoding="utf-8",
    )
    report = score.score(candidate, CLINIC)
    relationships = report.categories["relationships"]
    assert relationships.matched == relationships.gold - 1
    assert report.categories["elements"].f1 == 1.0


def test_hallucinated_element_lowers_precision_not_recall(candidate):
    extra = """
  - id: app-invented
    type: ApplicationComponent
    name: Invented System
    owner: practice-manager@novakclinic.example
    lastReviewed: 2026-07-01
    assumed: true
    rationale: Deliberately invented for the degradation test.
"""
    text = _model_file(candidate).read_text(encoding="utf-8")
    head, sep, tail = text.partition("relationships:")
    _model_file(candidate).write_text(head + extra + "\n" + sep + tail, encoding="utf-8")
    report = score.score(candidate, CLINIC)
    elements = report.categories["elements"]
    assert elements.recall == 1.0
    assert elements.precision < 1.0


def test_failing_gates_are_reported(candidate):
    text = _model_file(candidate).read_text(encoding="utf-8")
    _model_file(candidate).write_text(
        text.replace("      - fact: fact-ehr-server", "      - fact: no-such-fact"), encoding="utf-8"
    )
    report = score.score(candidate, CLINIC)
    assert not report.gates_ok
    assert report.gates["model"]["errors"] >= 1


# ------------------------------------------------------------------------------- CLI


def test_cli_score_gate_passes_on_self(capsys):
    assert cli.main(["score", "--root", str(CLINIC), "--gold", str(CLINIC), "--min-f1", "100"]) == 0
    assert "100.00%" in capsys.readouterr().out


def test_cli_score_gate_fails_below_threshold(candidate, capsys):
    """A distorted statement (gates still green) drops fact F1 below the bar."""
    text = _register_file(candidate).read_text(encoding="utf-8")
    _register_file(candidate).write_text(
        text.replace(
            "statement: Nobody has tested the backup restore of the EHR server.",
            "statement: The practice is generally satisfied with its infrastructure setup.",
        ),
        encoding="utf-8",
    )
    assert cli.main(["score", "--root", str(candidate), "--gold", str(CLINIC), "--min-f1", "100"]) == 1
    assert "below the required" in capsys.readouterr().out


def test_cli_score_gate_fails_on_gate_failure(candidate, capsys):
    text = _model_file(candidate).read_text(encoding="utf-8")
    _model_file(candidate).write_text(
        text.replace("      - fact: fact-ehr-server", "      - fact: no-such-fact"), encoding="utf-8"
    )
    assert cli.main(["score", "--root", str(candidate), "--gold", str(CLINIC), "--min-f1", "50"]) == 1
    assert "fails its own validation gates" in capsys.readouterr().out
