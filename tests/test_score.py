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


# -------------------------------------------------------------- what the score forgives

# These four are the answer to the 2026-08-05 end-to-end run, where a candidate that
# recalled 100% of gold's elements and relationships scored 15% and 0% -- entirely on
# vocabulary. Disagreeing about a label is not the same as missing the thing.


def test_an_element_named_by_its_alias_still_matches(candidate):
    """`facts/entities.yaml` says EHR *is* the electronic health record system."""
    text = _model_file(candidate).read_text(encoding="utf-8")
    _model_file(candidate).write_text(
        text.replace("name: EHR\n", "name: Electronic Health Record System\n"), encoding="utf-8"
    )
    report = score.score(candidate, CLINIC)
    assert report.categories["elements"].f1 == 1.0, "the alias table already knew these are one thing"
    assert report.categories["relationships"].f1 == 1.0, "so the endpoints resolve too"


def test_a_type_disagreement_inside_one_layer_is_half_a_match(candidate):
    """ApplicationService vs ApplicationInterface for one interview sentence."""
    text = _model_file(candidate).read_text(encoding="utf-8")
    _model_file(candidate).write_text(
        text.replace("    type: ApplicationService", "    type: ApplicationInterface"), encoding="utf-8"
    )
    elements = score.score(candidate, CLINIC).categories["elements"]
    assert elements.partial == 1
    assert elements.matched == pytest.approx(5.5), "found, but classified differently"
    assert 0.9 < elements.f1 < 1.0


def test_a_type_change_across_layers_is_not_a_match(candidate):
    """Half credit is for a contested classification, not for a different thing."""
    text = _model_file(candidate).read_text(encoding="utf-8")
    _model_file(candidate).write_text(
        text.replace("    type: ApplicationService", "    type: BusinessService"), encoding="utf-8"
    )
    elements = score.score(candidate, CLINIC).categories["elements"]
    assert elements.partial == 0 and elements.matched == 5


def test_splitting_one_gold_fact_into_two_is_not_a_miss(candidate):
    """The register's own discipline pushes towards atomic facts; gold combined them."""
    text = _register_file(candidate).read_text(encoding="utf-8")
    split = """  - id: fact-billing-module
    statement: Invoices are produced by the billing module inside the EHR.
    provenance:
      - file: facts/sources/interview-clinic-2026-07-01.md
        quote: Invoices are produced by the billing module inside the EHR
    entities: [ehr]

  - id: fact-no-separate-billing
    statement: The clinic runs no separate billing system.
    provenance:
      - file: facts/sources/interview-clinic-2026-07-01.md
        quote: we do not run a separate billing system
    entities: [ehr]
"""
    head, sep, tail = text.partition("  - id: fact-billing-inside-ehr")
    combined = tail.split("\n\n", 1)[1]
    _register_file(candidate).write_text(head + split + "\n" + combined, encoding="utf-8")
    report = score.score(candidate, CLINIC)
    facts_score = report.categories["facts"]
    assert facts_score.recall > 0.9, "gold's ground is still covered, by two facts instead of one"
    assert facts_score.gold_credit >= 6.5


def test_matching_evidence_under_a_wrong_statement_is_only_half(candidate):
    """Spans answer 'was this covered?'; the statement still has to say so."""
    text = _register_file(candidate).read_text(encoding="utf-8")
    _register_file(candidate).write_text(
        text.replace(
            "statement: Nobody has tested the backup restore of the EHR server.",
            "statement: The practice is generally satisfied with its infrastructure setup.",
        ),
        encoding="utf-8",
    )
    facts_score = score.score(candidate, CLINIC).categories["facts"]
    assert facts_score.partial >= 1 and facts_score.f1 < 1.0


def test_the_structural_relationship_count_is_reported_and_never_gated(candidate):
    report = score.score(candidate, CLINIC)
    assert "rel-structural" in report.diagnostics
    assert "rel-structural" not in report.categories, "diagnostics explain a number, they are not one"
    assert report.min_f1 == 1.0


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


# ------------------------------------------------------------------ the contested case

CONTESTED = REPO_ROOT / "eval" / "golden" / "contested"


def test_contested_case_is_gold():
    """Two sources that disagree, and a register that keeps both sides."""
    model_report = validate.validate(CONTESTED, zone="approved")
    facts_report = facts.validate_facts(CONTESTED)
    assert model_report.ok and not model_report.warnings, model_report.render()
    assert facts_report.ok and not facts_report.warnings, facts_report.render()
    assert score.score(CONTESTED, CONTESTED).min_f1 == 1.0


def test_the_contradiction_is_recorded_on_both_sides():
    register, _documents, _entities = facts.load(CONTESTED)
    inventory = register.facts["fact-schedpro-decommissioned"]
    interview = register.facts["fact-schedpro-still-used"]
    assert inventory.confidence == interview.confidence == "contested"
    assert interview.id in inventory.contests and inventory.id in interview.contests
    assert {p.file for p in inventory.provenance} != {p.file for p in interview.provenance}, (
        "the two sides must come from different sources, or it is not a contradiction"
    )


def test_following_one_side_is_reported_as_an_open_question():
    """PROV009 is info, not an error: choosing is allowed, choosing silently is not."""
    report = validate.validate(CONTESTED, zone="approved")
    contested = [f for f in report.findings if f.code == "PROV009"]
    assert contested and all(f.severity == "info" for f in contested)
    assert any(f.concept == "app-schedpro" for f in contested)


def test_the_architecture_description_says_the_sources_disagree(tmp_path):
    from easkills import docgen

    target = tmp_path / "contested"
    shutil.copytree(CONTESTED, target)
    docgen.generate(target)
    text = (target / "docs" / "architecture-description.md").read_text(encoding="utf-8")
    section = text.split("## 6. Assumptions and open questions", 1)[1]
    assert "disagree" in section
    assert "decommissioned in March 2026" in section, "the losing side must be quoted too"
