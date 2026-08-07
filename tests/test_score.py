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


def test_the_measured_cases_carry_atomic_statements():
    """Gold must obey the rule the skill it measures states.

    `ea-intake`: a fact is *one atomic statement*. Gold's clinic register carried two
    compound ones, three measured runs split them, and the scorer charged the runs half
    credit for being more correct than gold. Semicolons are the shape that defect took;
    this pins it for the two cases the baseline depends on. `eval/example/` is deliberately
    not covered -- it is a lifecycle fixture, not a measured case.
    """
    for case in (CLINIC, REPO_ROOT / "eval" / "golden" / "contested"):
        register, _documents, _entities = facts.load(case)
        compound = [f.id for f in register.facts.values() if ";" in f.statement]
        assert not compound, f"{case.name}: compound statements in {compound}"


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
    # Everything matched except the one retyped element, which counts half. Expressed
    # against `gold` rather than a literal so a legitimate change to the golden case
    # (the 2026-08-06 capability layer was one) moves the arithmetic, not the intent.
    assert elements.matched == pytest.approx(elements.gold - 0.5), "found, but classified differently"
    assert 0.9 < elements.f1 < 1.0


def test_a_type_change_across_layers_is_not_a_match(candidate):
    """Half credit is for a contested classification, not for a different thing."""
    text = _model_file(candidate).read_text(encoding="utf-8")
    _model_file(candidate).write_text(
        text.replace("    type: ApplicationService", "    type: BusinessService"), encoding="utf-8"
    )
    elements = score.score(candidate, CLINIC).categories["elements"]
    assert elements.partial == 0 and elements.matched == elements.gold - 1


def test_regrouping_gold_facts_covers_the_same_ground(candidate):
    """Coverage survives regrouping; only the statement decides full or half credit.

    This test used to run the other way round -- gold carried two compound statements and
    the candidate split them. Gold was atomized (it was breaking `ea-intake`'s own rule),
    so the surviving property is tested from the merging side: a candidate that writes one
    compound fact where gold has two atomic ones still covers gold's ground, and pays half
    credit per side for saying something different, never a zero.
    """
    text = _register_file(candidate).read_text(encoding="utf-8")
    merged = """  - id: fact-billing-inside-ehr
    statement: Invoices are produced by the billing module inside the EHR; there is no separate billing system.
    provenance:
      - file: facts/sources/interview-clinic-2026-07-01.md
        quote: Invoices are produced by the billing module inside the EHR
      - file: facts/sources/interview-clinic-2026-07-01.md
        quote: we do not run a separate billing system
    entities: [ehr]
"""
    head, _sep, tail = text.partition("  - id: fact-billing-module-in-ehr")
    rest = tail.split("  - id: fact-portal-hosting", 1)[1]
    _register_file(candidate).write_text(
        head + merged + "\n  - id: fact-portal-hosting" + rest, encoding="utf-8"
    )
    # Keep the candidate's own gates green: it must cite the fact it actually wrote.
    # Three places cite the two merged facts since gold gained its capability layer --
    # `app-ehr`, `cap-billing`, and the Realization between them -- and a single missed
    # one is PROV007, which makes the whole score untrustworthy rather than merely lower.
    model = _model_file(candidate).read_text(encoding="utf-8")
    _model_file(candidate).write_text(
        model.replace(
            "      - fact: fact-billing-module-in-ehr\n      - fact: fact-no-separate-billing",
            "      - fact: fact-billing-inside-ehr",
        ).replace(
            "      - fact: fact-billing-module-in-ehr",
            "      - fact: fact-billing-inside-ehr",
        ),
        encoding="utf-8",
    )
    report = score.score(candidate, CLINIC)
    assert report.gates_ok, report.render()
    facts_score = report.categories["facts"]
    assert facts_score.candidate == facts_score.gold - 1, "the merge is what is being scored"
    assert facts_score.gold_credit >= 8.0, "both atomic facts are covered, at half credit each"
    assert facts_score.partial >= 2 and facts_score.f1 < 1.0


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


def test_an_edge_the_candidate_only_implies_is_half_a_match(candidate):
    """The measured 0% case, scored end to end.

    The candidate routes the portal's service to the patient *through a process it
    invented*, exactly as three measured runs did. Gold's direct edge is derivable from
    the candidate's two by DR4, so it is half a match instead of a miss -- and the two
    edges carrying that derivation are half matches too, not inventions.
    """
    text = _model_file(candidate).read_text(encoding="utf-8")
    text = text.replace(
        "relationships:",
        """  - id: proc-booking
    type: BusinessProcess
    name: Booking Flow
    owner: practice-manager@novakclinic.example
    lastReviewed: 2026-07-01
    assumed: true
    rationale: Intermediate behaviour the sources do not name; inserted by the run.

relationships:""",
    ).replace(
        """  - id: rel-portal-serves-patient
    type: Serving
    source: app-booking-portal
    target: actor-patient""",
        """  - id: rel-portal-serves-flow
    type: Serving
    source: app-booking-portal
    target: proc-booking
    provenance:
      - fact: fact-booking-portal-channel

  - id: rel-patient-does-flow
    type: Assignment
    source: actor-patient
    target: proc-booking""",
    )
    _model_file(candidate).write_text(text, encoding="utf-8")
    report = score.score(candidate, CLINIC)
    assert report.gates_ok, report.render()
    relationships = report.categories["relationships"]
    assert relationships.unmatched_gold == (), "nothing was missed, only re-grained"
    assert relationships.partial_gold == (
        "Serving Booking Portal -> Patient (derived DR4 via Booking Flow)",
    )
    # One gold edge was re-grained into two, so: every other gold edge matches fully and
    # that one counts half; on the candidate side the two edges carrying the derivation
    # count half each, which is why the credit lands back on `gold`. Written against
    # `relationships.gold` so a change to the golden case moves the arithmetic, not the
    # claim -- the 2026-08-06 capability layer was exactly such a change.
    assert relationships.gold_credit == pytest.approx(relationships.gold - 0.5)
    assert set(relationships.partial_candidate) == {
        "Serving Booking Portal -> Booking Flow",
        "Assignment Patient -> Booking Flow",
    }
    assert relationships.matched == pytest.approx(relationships.gold)
    assert relationships.recall == pytest.approx((relationships.gold - 0.5) / relationships.gold)
    # The invented element still costs element precision -- derivation forgives the edge,
    # not the elaboration.
    assert report.categories["elements"].precision < 1.0


def test_a_wrong_edge_is_not_forgiven_by_derivation(candidate):
    """Half credit is for a re-grained connection, never for a connection gold denies."""
    text = _model_file(candidate).read_text(encoding="utf-8")
    _model_file(candidate).write_text(
        text.replace(
            """  - id: rel-server-serves-ehr
    type: Serving
    source: node-ehr-server
    target: app-ehr""",
            """  - id: rel-server-serves-portal
    type: Serving
    source: node-ehr-server
    target: app-booking-portal""",
        ),
        encoding="utf-8",
    )
    relationships = score.score(candidate, CLINIC).categories["relationships"]
    assert relationships.unmatched_gold == ("Serving EHR Server -> EHR",)
    assert relationships.partial_gold == ()
    assert relationships.unmatched_candidate == ("Serving EHR Server -> Booking Portal",)


def test_the_structural_relationship_count_is_reported_and_never_gated(candidate):
    report = score.score(candidate, CLINIC)
    assert "rel-structural" in report.diagnostics
    assert "rel-structural" not in report.categories, "diagnostics explain a number, they are not one"
    assert report.min_f1 == 1.0


# -------------------------------------------------------- the score names its own items

# A ratio alone made every investigation of a fallen category a manual diff of two YAML
# trees. Three such investigations produced three different verdicts, and all three cost
# more than the run that produced the number.


def test_a_perfect_score_names_nothing():
    report = score.score(CLINIC, CLINIC)
    for name, category in report.categories.items():
        assert not category.unmatched_gold, name
        assert not category.unmatched_candidate, name
        assert not category.partial_gold, name
    assert "what did not match" not in report.render()


def test_the_score_names_the_element_it_missed_and_the_one_it_got_instead(candidate):
    text = _model_file(candidate).read_text(encoding="utf-8")
    _model_file(candidate).write_text(
        text.replace("name: Booking Portal", "name: Appointment App"), encoding="utf-8"
    )
    report = score.score(candidate, CLINIC)
    elements = report.categories["elements"]
    assert elements.unmatched_gold == ("ApplicationComponent Booking Portal",)
    assert elements.unmatched_candidate == ("ApplicationComponent Appointment App",)
    # And the relationships it dragged down are named by endpoint, not by id.
    relationships = report.categories["relationships"]
    assert "Serving Booking Portal -> Patient" in relationships.unmatched_gold
    assert "Serving Appointment App -> Patient" in relationships.unmatched_candidate
    assert "Appointment App" in report.render()


def test_a_half_credit_names_both_sides_of_the_disagreement(candidate):
    text = _model_file(candidate).read_text(encoding="utf-8")
    _model_file(candidate).write_text(
        text.replace("    type: ApplicationService", "    type: ApplicationInterface"), encoding="utf-8"
    )
    elements = score.score(candidate, CLINIC).categories["elements"]
    assert elements.partial_gold == ("ApplicationService Scheduling Interface",)
    assert elements.partial_candidate == ("ApplicationInterface Scheduling Interface",)
    assert not elements.unmatched_gold, "it was found, only classified differently"


def test_the_missing_fact_is_named_in_the_json(candidate):
    text = _register_file(candidate).read_text(encoding="utf-8")
    head, _sep, _tail = text.partition("  - id: fact-backup-untested")
    _register_file(candidate).write_text(head, encoding="utf-8")
    payload = score.score(candidate, CLINIC).as_dict()["categories"]["facts"]
    assert payload["unmatchedGold"] == ["fact-backup-untested"]
    assert payload["unmatchedCandidate"] == []


def test_the_terminal_listing_is_capped_but_the_json_is_not(candidate):
    """Twenty invented elements must not push the gate verdict off the screen."""
    extra = "".join(
        f"""
  - id: app-invented-{index}
    type: ApplicationComponent
    name: Invented System {index}
    owner: practice-manager@novakclinic.example
    lastReviewed: 2026-07-01
    assumed: true
    rationale: Deliberately invented for the render-cap test.
"""
        for index in range(20)
    )
    text = _model_file(candidate).read_text(encoding="utf-8")
    head, sep, tail = text.partition("relationships:")
    _model_file(candidate).write_text(head + extra + "\n" + sep + tail, encoding="utf-8")
    report = score.score(candidate, CLINIC)
    assert len(report.categories["elements"].unmatched_candidate) == 20
    assert "(+12 more)" in report.render()
    assert len(report.as_dict()["categories"]["elements"]["unmatchedCandidate"]) == 20


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
