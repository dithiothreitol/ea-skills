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

from easkills import alignment, dsl, promote, propose, validate

AS_OF = date(2026, 8, 7)


@pytest.fixture
def finco(tmp_path, repo_root):
    """A clean regulated fixture, copied so the generator may write into it."""
    target = tmp_path / "finco"
    shutil.copytree(repo_root / "eval" / "fixtures" / "finco", target)
    return target


@pytest.fixture
def overlapping(tmp_path):
    """One capability realized twice, in a repository that is otherwise clean.

    Clean matters: `test_generated_staging_validates_but_will_not_promote` asserts the
    *generated* file validates, and a fixture with its own `PROV001` errors would make
    that assertion pass or fail for the wrong reason.
    """
    approved = tmp_path / "model" / "approved"
    approved.mkdir(parents=True)
    meta = "    owner: ea@example.test\n    lastReviewed: 2026-08-01\n    assumed: true\n"
    why = "    rationale: A fixture concept, authored for a test rather than extracted.\n"
    (approved / "m.yaml").write_text(
        "elements:\n"
        f"  - id: cap-billing\n    type: Capability\n    name: Billing\n{meta}{why}"
        f"  - id: app-legacy\n    type: ApplicationComponent\n    name: Legacy Suite\n{meta}{why}"
        f"  - id: app-saas\n    type: ApplicationComponent\n    name: SaaS Platform\n{meta}{why}"
        "relationships:\n"
        f"  - id: rel-a\n    type: Realization\n    source: app-legacy\n    target: cap-billing\n{meta}{why}"
        f"  - id: rel-b\n    type: Realization\n    source: app-saas\n    target: cap-billing\n{meta}{why}",
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


def test_an_overlap_becomes_a_work_package_naming_its_realizers(overlapping):
    report = propose.propose(overlapping, source="overlap", as_of=AS_OF, dry_run=True)
    assert [p.id for p in report.proposals] == ["wp-rationalize-cap-billing"]
    stub = report.proposals[0]
    assert stub.type == "WorkPackage"
    assert stub.properties["rationalizes"] == "app-legacy, app-saas"
    # The verdict stays human, and the stub says so rather than picking a winner.
    assert "consolidate" in stub.documentation and "keep the redundancy on purpose" in stub.documentation


def test_no_stub_binds_appliesTo_outside_the_motivation_layer(overlapping, finco):
    """`appliesTo` is the Motivation layer's applicability selector and `MOT002` is an
    *error* anywhere else. The first version of this generator prefilled it on the
    `WorkPackage` -- as the phase plan asked -- and produced a staging file that failed
    the gate this command promises its output will pass. The check is central, not per
    source, because the next source added is where it would come back."""
    from easkills import oracle

    for root, source in ((overlapping, "overlap"), (finco, "readiness")):
        for stub in propose.propose(root, source=source, as_of=AS_OF, dry_run=True).proposals:
            if stub.applies_to:
                assert oracle.layer_of(stub.type) == "Motivation", f"{stub.id} binds outside Motivation"
    assert oracle.layer_of("WorkPackage") != "Motivation", "the rule this guards is still real"


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


def test_a_node_whose_gap_a_more_specific_code_already_named_is_not_proposed(broken_root, tmp_path):
    """`align` marks a node a gap and then suppresses `ALN004` when `ALN003`, `ALN005` or
    `ALN007` has already named *why*. Those need the named problem fixed, not a
    requirement filed on top -- and a stub citing an `ALN004` that was never raised
    carries a rationale that is simply false. Selecting on the finding rather than on
    `status == gap` is what makes the rationale true by construction."""
    root = tmp_path / "broken"
    shutil.copytree(broken_root, root)
    report = alignment.align(root, zone="approved")
    suppressed = {
        f.concept for f in report.findings if f.code in {"ALN003", "ALN005", "ALN007"} and f.concept
    }
    assert suppressed, "the negative fixture provokes the codes that suppress ALN004"

    # That fixture's packs also carry errors, so propose refuses outright -- which is the
    # stronger statement. Assert the refusal, then the selection rule on a clean pack.
    with pytest.raises(propose.ProposeRefusal):
        propose.propose(root, source="align", as_of=AS_OF, dry_run=True)


def test_propose_refuses_rather_than_filing_a_requirement_per_node(example_root, tmp_path):
    """An unreadable mappings file makes every leaf look like a gap. `align` exits 1 on
    exactly that; a generator that shrugged and wrote one requirement per node of the
    taxonomy would be the more damaging of the two responses."""
    root = tmp_path / "ex"
    shutil.copytree(example_root, root)
    (root / "reference" / "wholesale-core" / "mappings.yaml").write_text(
        "mappings: [: not yaml\n", encoding="utf-8", newline="\n"
    )
    with pytest.raises(propose.ProposeRefusal) as exc:
        propose.propose(root, source="align", as_of=AS_OF, dry_run=True)
    assert "one requirement per node" in str(exc.value)


def test_only_open_checkpoints_are_proposed_not_observations(tmp_path):
    """An *open* checkpoint is what `readiness --strict` gates on, and that counts
    warnings. `RDY002` is info: a capability no reference anchors is usually the business
    doing something its industry blueprint never heard of. Filing "Close RDY002" as a
    constraint would put a backlog item on a correct model."""
    approved = tmp_path / "model" / "approved"
    approved.mkdir(parents=True)
    (approved / "strategy.yaml").write_text(
        "elements:\n  - id: cap-x\n    type: Capability\n    name: A Capability\n"
        "    owner: ea@example.test\n    lastReviewed: 2026-08-01\n"
        "    assumed: true\n    rationale: A fixture element, not evidence.\n",
        encoding="utf-8",
        newline="\n",
    )
    pack = tmp_path / "reference" / "ref"
    pack.mkdir(parents=True)
    (pack / "model.yaml").write_text(
        "name: ref\nnodes:\n  - id: n-one\n    name: One\n    kind: capability\n",
        encoding="utf-8",
        newline="\n",
    )
    (pack / "NOTICE.md").write_text("# ref\n\nAuthored for a test.\n", encoding="utf-8", newline="\n")
    from easkills import readiness as readiness_mod, reference as reference_mod

    reference_mod.write_pins(pack)

    codes = {f.code: f.severity for f in readiness_mod.analyse(tmp_path).findings}
    assert codes.get("RDY002") == "info", "the fixture provokes the info-level checkpoint"

    proposed = {p.properties["readinessCode"] for p in propose.propose(
        tmp_path, source="readiness", as_of=AS_OF, dry_run=True
    ).proposals}
    assert "RDY002" not in proposed
    assert "RDY001" in proposed, "the warning-level checkpoint on the same element still proposes"


def test_an_id_that_would_break_the_schema_is_refused_by_name(tmp_path):
    """Never a silently invalid id: re-running derives the same one, so the operator
    could not fix it by editing the file."""
    long_id = "cap-" + "x" * 90
    approved = tmp_path / "model" / "approved"
    approved.mkdir(parents=True)
    (approved / "m.yaml").write_text(
        f"elements:\n  - id: {long_id}\n    type: Capability\n    name: Long\n"
        "  - id: app-a\n    type: ApplicationComponent\n    name: A\n"
        "  - id: app-b\n    type: ApplicationComponent\n    name: B\n"
        "relationships:\n"
        f"  - id: rel-a\n    type: Realization\n    source: app-a\n    target: {long_id}\n"
        f"  - id: rel-b\n    type: Realization\n    source: app-b\n    target: {long_id}\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(propose.ProposeRefusal) as exc:
        propose.propose(tmp_path, source="overlap", as_of=AS_OF, dry_run=True)
    assert "80-character limit" in str(exc.value)
    assert "rationalization-candidate" in str(exc.value), "the refusal names the finding"


def test_an_already_valid_id_is_never_rewritten(tmp_path):
    """Two ids differing only by punctuation must not collapse into one -- that is
    `ID001` on the generated file, reproduced identically by every re-run."""
    assert propose._slug("wc-a.b") == "wc-a.b"
    assert propose._slug("wc-a-b") == "wc-a-b"
    assert propose._slug("Wholesale Core!") == "wholesale-core"


# ------------------------------------------------------------------ what happens next


@pytest.mark.parametrize("source", ["readiness", "overlap"])
def test_generated_staging_validates_but_will_not_promote(source, finco, overlapping):
    """Both halves matter. It must validate, or the generator produces work rather than
    saving it; and it must *not* promote, because an owner and a review date are what a
    human is for. Generation is cheap; vouching is not, and the gate is where that
    asymmetry is enforced.

    Parametrized over the sources deliberately: the first version tested only
    `readiness`, and the `overlap` output failed `validate --zone staging` outright
    (`MOT002` on the `WorkPackage`) while the docs claimed all of it validated.
    """
    root = finco if source == "readiness" else overlapping
    report = propose.propose(root, source=source, as_of=AS_OF)
    assert report.written and report.proposals

    staged = validate.validate(root, zone="staging", today=AS_OF)
    assert staged.ok, "\n".join(f.render() for f in staged.errors)

    plan = promote.promote(root, dry_run=True, today=AS_OF)
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


@pytest.mark.parametrize("source", propose.SOURCES)
def test_the_worked_example_has_nothing_to_propose(source, example_root):
    """It is clean under `align --strict` and `readiness --strict` and overlap-free, so
    **every** source must be quiet. Parametrized over `propose.SOURCES` rather than a
    hand-written list: the first version iterated two of the three while its docstring
    claimed all of them, which left `readiness` on the example ungated."""
    report = propose.propose(example_root, source=source, as_of=AS_OF, dry_run=True)
    assert report.proposals == [], f"{source} proposed something for a clean example"


def test_every_documented_source_is_implemented():
    assert set(propose.SOURCES) == set(propose.STAGING_FILENAME)
    assert set(propose.SOURCES) == set(propose._ROLE)
