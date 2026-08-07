"""`propose`: findings become staged skeletons, and never anything more than skeletons.

The generator's value is entirely in what it refuses to do. It writes ids, types and
bindings -- the mechanical part -- and leaves every word of prose to a human behind a
loud placeholder. Most of this module tests the refusals: never overwrite, never invent
prose, never let a stub reach `approved` without an owner, never renumber on a re-run.
"""

import shutil
from datetime import date

import pytest
import yaml

from easkills import dsl, promote, propose, validate

AS_OF = date(2026, 8, 7)


@pytest.fixture
def finco(tmp_path, repo_root):
    """A clean regulated fixture, copied so the generator may write into it."""
    target = tmp_path / "finco"
    shutil.copytree(repo_root / "eval" / "fixtures" / "finco", target)
    return target


@pytest.fixture
def overlapping(tmp_path):
    approved = tmp_path / "model" / "approved"
    approved.mkdir(parents=True)
    (approved / "m.yaml").write_text(
        "elements:\n"
        "  - id: cap-billing\n    type: Capability\n    name: Billing\n"
        "  - id: app-legacy\n    type: ApplicationComponent\n    name: Legacy Suite\n"
        "  - id: app-saas\n    type: ApplicationComponent\n    name: SaaS Platform\n"
        "relationships:\n"
        "  - id: rel-a\n    type: Realization\n    source: app-legacy\n    target: cap-billing\n"
        "  - id: rel-b\n    type: Realization\n    source: app-saas\n    target: cap-billing\n",
        encoding="utf-8",
        newline="\n",
    )
    return tmp_path


def _elements(path):
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {})["elements"]


# ------------------------------------------------------------------- what it produces


def test_a_reference_gap_becomes_a_requirement_bound_to_nothing(example_root, tmp_path):
    """A gap is a node nobody answered and nobody excluded. What will satisfy it is
    exactly the decision that has not been made, so the stub binds to nothing -- filling
    `appliesTo` with a guess would be the generator making that decision quietly."""
    root = tmp_path / "ex"
    shutil.copytree(example_root, root)
    mappings = root / "reference" / "wholesale-core" / "mappings.yaml"
    mappings.write_text("mappings: []\n", encoding="utf-8", newline="\n")

    report = propose.propose(root, source="align", as_of=AS_OF, dry_run=True)
    assert report.proposals, "every node is a gap once the mappings are gone"
    first = report.proposals[0]
    assert first.id.startswith("req-wholesale-core-")
    assert first.applies_to == []
    assert first.properties["referencePack"] == "wholesale-core"
    assert "ALN004" in first.rationale


def test_a_control_node_becomes_a_constraint_not_a_requirement(tmp_path, repo_root):
    """A control restricts how the architecture may be built, which is what `Constraint`
    means in ArchiMate. Emitting `Requirement` for everything would be one type doing two
    jobs, and the motivation layer would stop distinguishing intent from restriction."""
    root = tmp_path / "ctrl"
    (root / "model" / "approved").mkdir(parents=True)
    (root / "model" / "approved" / "m.yaml").write_text(
        "elements:\n  - id: app-x\n    type: ApplicationComponent\n    name: X\n",
        encoding="utf-8",
        newline="\n",
    )
    pack = root / "reference" / "controls"
    pack.mkdir(parents=True)
    (pack / "model.yaml").write_text(
        "name: controls\nnodes:\n"
        "  - id: ctl-access\n    name: Access Control\n    kind: control\n"
        "  - id: cap-thing\n    name: A Capability\n    kind: capability\n",
        encoding="utf-8",
        newline="\n",
    )
    (pack / "NOTICE.md").write_text("# controls\n\nAuthored for a test.\n", encoding="utf-8", newline="\n")
    from easkills import reference as reference_mod

    reference_mod.write_pins(pack)

    by_id = {p.id: p for p in propose.propose(root, source="align", as_of=AS_OF, dry_run=True).proposals}
    assert by_id["req-controls-ctl-access"].type == "Constraint"
    assert by_id["req-controls-cap-thing"].type == "Requirement"


def test_a_readiness_checkpoint_becomes_a_constraint_bound_to_its_element(finco):
    report = propose.propose(finco, source="readiness", as_of=AS_OF, dry_run=True)
    by_id = {p.id: p for p in report.proposals}
    stub = by_id["con-app-crm-rdy005"]
    assert stub.type == "Constraint"
    assert stub.applies_to == ["app-crm"], "the checkpoint is about that element, so the stub binds to it"
    assert stub.properties["readinessCode"] == "RDY005"


def test_a_checkpoint_that_names_no_element_produces_nothing(broken_root, tmp_path):
    """`RDY010` names a *layer* the fact register covers and the model does not. A
    constraint bound to nothing is exactly what `MOT001` exists to stop, so the one
    checkpoint with no element is the one that generates no stub."""
    root = tmp_path / "broken"
    shutil.copytree(broken_root, root)
    origins = {p.origin for p in propose.propose(root, source="readiness", as_of=AS_OF, dry_run=True).proposals}
    assert origins, "the broken fixture has checkpoints"
    assert not [o for o in origins if o.startswith("RDY010")]


def test_an_overlap_becomes_a_work_package_bound_to_its_realizers(overlapping):
    """The one case where `appliesTo` can be prefilled honestly: the elements a
    rationalization touches *are* the realizers the query already named."""
    report = propose.propose(overlapping, source="overlap", as_of=AS_OF, dry_run=True)
    assert [p.id for p in report.proposals] == ["wp-rationalize-cap-billing"]
    stub = report.proposals[0]
    assert stub.type == "WorkPackage"
    assert stub.applies_to == ["app-legacy", "app-saas"]
    # The verdict stays human, and the stub says so rather than picking a winner.
    assert "consolidate" in stub.documentation and "keep the redundancy on purpose" in stub.documentation


# --------------------------------------------------------------------- what it refuses


def test_every_stub_is_assumed_with_a_rationale_naming_its_finding(finco):
    propose.propose(finco, source="readiness", as_of=AS_OF)
    for element in _elements(finco / "model" / "staging" / "proposed-constraints.yaml"):
        assert element["assumed"] is True
        assert element["rationale"].startswith("Derived from RDY")
        assert "Complete or delete before promotion" in element["rationale"]


def test_every_documentation_field_is_a_loud_placeholder(finco, overlapping):
    """A half-finished stub must not read as something an architect wrote. `PROPOSED --`
    is greppable, and it is at the *start* of the field so it survives truncation in any
    table that shows the first line."""
    propose.propose(finco, source="readiness", as_of=AS_OF)
    propose.propose(overlapping, source="overlap", as_of=AS_OF)
    for path in (
        finco / "model" / "staging" / "proposed-constraints.yaml",
        overlapping / "model" / "staging" / "proposed-work-packages.yaml",
    ):
        for element in _elements(path):
            assert element["documentation"].startswith(propose.PLACEHOLDER)


def test_the_generator_writes_no_prose_a_human_could_mistake_for_authored(overlapping):
    """The generator makes skeletons; the skill teaches what a good one says. If this
    ever fails because a template grew a plausible business outcome, the fix is to move
    the words into skill prose, not to relax the test."""
    report = propose.propose(overlapping, source="overlap", as_of=AS_OF, dry_run=True)
    stub = report.proposals[0]
    assert propose.PLACEHOLDER in stub.documentation
    assert "ea-change-triage" in stub.documentation, "the stub points at where the words come from"


def test_an_existing_target_file_is_a_refusal_not_a_merge(overlapping):
    target = overlapping / "model" / "staging" / "proposed-work-packages.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("elements: []\n", encoding="utf-8", newline="\n")
    with pytest.raises(propose.ProposeRefusal) as exc:
        propose.propose(overlapping, source="overlap", as_of=AS_OF)
    assert "never overwrites" in str(exc.value)
    assert target.read_text(encoding="utf-8") == "elements: []\n", "the existing file is untouched"


def test_an_id_already_in_the_model_is_skipped_by_name(overlapping):
    """Somebody already acted on this finding. Skipping silently would hide that; failing
    the whole run over it would make the command unusable in a repository that has done
    some of the work. Naming it is the third option and the right one."""
    approved = overlapping / "model" / "approved" / "existing.yaml"
    approved.write_text(
        "elements:\n  - id: wp-rationalize-cap-billing\n    type: WorkPackage\n    name: Already Planned\n",
        encoding="utf-8",
        newline="\n",
    )
    report = propose.propose(overlapping, source="overlap", as_of=AS_OF, dry_run=True)
    assert report.proposals == []
    assert [s["id"] for s in report.skipped] == ["wp-rationalize-cap-billing"]
    assert "model/approved/" in report.skipped[0]["reason"]


def test_rerunning_after_writing_proposes_nothing_new(finco):
    """The derived ids are what make a re-run safe: the second pass finds every id
    already in staging and writes nothing, rather than renumbering or duplicating."""
    first = propose.propose(finco, source="readiness", as_of=AS_OF)
    assert first.written and first.proposals
    second = propose.propose(finco, source="readiness", as_of=AS_OF)
    assert second.proposals == [] and not second.written
    assert len(second.skipped) == len(first.proposals)


def test_dry_run_writes_nothing(overlapping):
    report = propose.propose(overlapping, source="overlap", as_of=AS_OF, dry_run=True)
    assert report.proposals and not report.written
    assert not (overlapping / "model" / "staging" / "proposed-work-packages.yaml").exists()


def test_an_unknown_source_is_refused_before_anything_is_read(tmp_path):
    with pytest.raises(propose.ProposeRefusal):
        propose.propose(tmp_path, source="vibes", as_of=AS_OF)


# ------------------------------------------------------------------ what happens next


def test_generated_staging_validates_but_will_not_promote(finco):
    """Both halves matter. It must validate, or the generator produces work rather than
    saving it; and it must *not* promote, because an owner and a review date are what a
    human is for. Generation is cheap; vouching is not, and the gate is where that
    asymmetry is enforced."""
    propose.propose(finco, source="readiness", as_of=AS_OF)
    staged = validate.validate(finco, zone="staging", today=AS_OF)
    assert staged.ok, "\n".join(f.render() for f in staged.errors)

    plan = promote.promote(finco, dry_run=True, today=AS_OF)
    assert not plan.ok, "a stub with no owner must not be promotable"
    assert not plan.moved
    blocking = {f.code for f in plan.report.errors}
    assert blocking & {"GOV001", "GOV002"}, f"expected an ownership block, got {blocking}"


def test_output_is_byte_stable_for_identical_inputs(finco, tmp_path, repo_root):
    """Re-run-and-diff is only a safe habit if an unchanged repository produces an
    unchanged file. This is also why `--as-of` is required rather than defaulting to
    today: a wall-clock stamp would make the same repository differ tomorrow."""
    other = tmp_path / "finco-again"
    shutil.copytree(repo_root / "eval" / "fixtures" / "finco", other)
    propose.propose(finco, source="readiness", as_of=AS_OF)
    propose.propose(other, source="readiness", as_of=AS_OF)
    assert (finco / "model" / "staging" / "proposed-constraints.yaml").read_bytes() == (
        other / "model" / "staging" / "proposed-constraints.yaml"
    ).read_bytes()


def test_the_date_in_the_output_is_the_one_that_was_asked_for(overlapping):
    """No wall clock in a generated artifact -- the standing rule, and the reason the CLI
    makes `--as-of` required for this command alone."""
    propose.propose(overlapping, source="overlap", as_of=date(2027, 1, 15))
    text = (overlapping / "model" / "staging" / "proposed-work-packages.yaml").read_text(encoding="utf-8")
    assert "2027-01-15" in text
    assert date.today().isoformat() not in text or date.today() == date(2027, 1, 15)


def test_generated_files_use_unix_newlines(overlapping):
    propose.propose(overlapping, source="overlap", as_of=AS_OF)
    assert b"\r" not in (overlapping / "model" / "staging" / "proposed-work-packages.yaml").read_bytes()


def test_ids_are_derived_from_the_finding_never_counted(overlapping):
    """A counter would renumber everything the first time one finding is fixed, and the
    diff of the second run would be noise instead of news."""
    report = propose.propose(overlapping, source="overlap", as_of=AS_OF, dry_run=True)
    assert report.proposals[0].id == "wp-rationalize-cap-billing"
    assert not any(char.isdigit() for char in report.proposals[0].id.rsplit("-", 1)[-1])


def test_the_worked_example_has_nothing_to_propose(example_root):
    """It is clean under `align --strict` and overlap-free, so all three sources should
    be quiet. A generator that produced stubs for a finished repository would be teaching
    people to delete its output by reflex."""
    for source in ("align", "overlap"):
        report = propose.propose(example_root, source=source, as_of=AS_OF, dry_run=True)
        assert report.proposals == [], f"{source} proposed something for a clean example"


def test_every_documented_source_is_implemented():
    assert set(propose.SOURCES) == set(propose.STAGING_FILENAME)
    assert set(propose.SOURCES) == set(propose._ROLE)
