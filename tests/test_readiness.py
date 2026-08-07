"""Per-layer readiness: every RDY checkpoint fires, and none of them fires on correct
modelling.

The second half is the load-bearing one. A readiness report is advisory, so its only
real failure mode is noise: a checkpoint that flags idiomatic ArchiMate teaches people to
ignore the report, and an ignored report is worse than no report because it looks like
coverage. Writing RDY008 produced exactly that against the worked example on the first
run -- `PostgreSQL 16`, composed into the server that serves the ERP -- and the tests
below pin the containment rule that fixed it.
"""

from __future__ import annotations

import json

import pytest

from easkills import cli, readiness


@pytest.fixture(scope="module")
def example_report(example_root):
    return readiness.analyse(example_root)


@pytest.fixture(scope="module")
def broken_report(broken_root):
    return readiness.analyse(broken_root)


@pytest.fixture(scope="module")
def broken_staging_report(broken_root):
    return readiness.analyse(broken_root, zone="staging")


def _layer(report, name):
    return next(layer for layer in report.layers if layer.layer == name)


# --------------------------------------------------------------------------- positive


def test_the_worked_example_has_no_open_checkpoint(example_report):
    assert not example_report.warnings, "\n".join(f.render() for f in example_report.warnings)


def test_every_checked_layer_of_the_example_is_populated(example_report):
    """The example is the "complete enough to gate on" case; an empty layer here would
    make the zero-findings claim a statement about a layer nobody modelled."""
    for layer in example_report.layers:
        assert not layer.empty, f"{layer.layer} is empty in the worked example"


def test_a_part_contributes_through_its_whole(example_root):
    """The false positive that shaped RDY006/007/008.

    `PostgreSQL 16` serves nothing and realizes nothing -- it is *composed into* the ERP
    application server, and the server is what serves the ERP. That is correct, idiomatic
    ArchiMate, and the first version of this checklist called it unfinished technology.
    """
    report = readiness.analyse(example_root)
    flagged = {f.concept for f in report.findings if f.code == "RDY008"}
    assert "sysswt-postgresql" not in flagged
    # And the rule is not simply disabled: the graph helper is what exempts it.
    from easkills import dsl

    model, _documents, _config = dsl.load(example_root, "approved")
    graph = readiness._graph(model)
    assert not graph.served.get("sysswt-postgresql")
    assert not graph.realizes.get("sysswt-postgresql")
    assert graph.contributes("sysswt-postgresql"), "through node-erp-app-server"


def test_nothing_here_is_ever_an_error(example_report, broken_report):
    """An unfinished layer is not a wrong model. If this ever needs changing, the
    argument has to be made in RULES.md first -- a checklist that blocks commits for
    incompleteness gets switched off, and then measures nothing."""
    for report in (example_report, broken_report):
        assert report.ok
        assert all(f.severity != "error" for f in report.findings)


def test_an_empty_layer_is_shown_and_not_flagged(broken_report):
    """Same rule that keeps PLAT005 silent with no plateaus: a repository that has not
    started a layer is not breaking it. The report says `empty` so the shape is visible
    without inventing a finding for it."""
    strategy = _layer(broken_report, "Strategy")
    assert strategy.empty and strategy.findings == []


def test_the_report_is_byte_stable(example_root):
    first = readiness.analyse(example_root)
    second = readiness.analyse(example_root)
    assert first.render() == second.render()
    assert first.as_dict() == second.as_dict()


# --------------------------------------------------------------------------- negative

# RDY001/RDY002 need a Capability and RDY010 needs the Strategy layer to be *empty*, so
# the fixture's proposed capability layer lives in staging and the two sides are read in
# different zones. That split also exercises --zone (D8).
EXPECTED_APPROVED_CODES = ["RDY003", "RDY004", "RDY005", "RDY006", "RDY007", "RDY008", "RDY009", "RDY010"]
EXPECTED_STAGING_CODES = ["RDY001", "RDY002"]


@pytest.mark.parametrize("code", EXPECTED_APPROVED_CODES)
def test_approved_zone_checkpoint_fires(broken_report, code):
    matches = [f for f in broken_report.findings if f.code == code]
    assert matches, f"{code} did not fire on the negative fixture"


@pytest.mark.parametrize("code", EXPECTED_STAGING_CODES)
def test_staging_zone_checkpoint_fires(broken_staging_report, code):
    matches = [f for f in broken_staging_report.findings if f.code == code]
    assert matches, f"{code} did not fire on the negative fixture in staging"


def test_every_documented_rdy_code_has_a_case(broken_report, broken_staging_report):
    """The CONTRIBUTING triple, checked rather than trusted: a rule with no provoking
    fixture is decoration, and this is the assertion that says so for the whole family."""
    fired = {f.code for f in broken_report.findings} | {f.code for f in broken_staging_report.findings}
    expected = {f"RDY{n:03d}" for n in range(1, 11)}
    assert expected <= fired, f"no fixture case for {sorted(expected - fired)}"


def test_a_recorded_weakness_is_not_an_open_checkpoint(broken_staging_report):
    """RDY001's whole distinction: unsupported *and unexamined*.

    `ea-capability-map` teaches recording a known weakness as a property rather than as a
    missing element. A checklist that flagged the recorded weakness anyway would punish
    following the skill -- the same defect gold's missing capability layer had.
    """
    flagged = {f.concept for f in broken_staging_report.findings if f.code == "RDY001"}
    assert "cap-unsupported-unexamined" in flagged
    assert "cap-weakness-recorded" not in flagged


def test_capabilities_unanchored_by_a_reference_are_info_not_warning(broken_staging_report):
    """RDY002 is the same observation `align` reports as information.

    Making it a warning would mean `readiness --strict` failing for a business that does
    something its industry blueprint has never heard of -- exactly the failure mode 7.1
    designed the unanchored list *against*. One observation, one severity, whichever
    report it appears in.
    """
    findings = [f for f in broken_staging_report.findings if f.code == "RDY002"]
    assert findings and all(f.severity == "info" for f in findings)


def test_rdy002_is_silent_when_no_reference_pack_exists(tmp_path):
    """No reference model, no question -- not "every capability is unanchored"."""
    approved = tmp_path / "model" / "approved"
    approved.mkdir(parents=True)
    (approved / "strategy.yaml").write_text(
        "elements:\n  - id: cap-x\n    type: Capability\n    name: A Capability\n"
        "    owner: ea@example.test\n    lastReviewed: 2026-08-01\n"
        "    assumed: true\n    rationale: A fixture element, not evidence.\n",
        encoding="utf-8",
        newline="\n",
    )
    report = readiness.analyse(tmp_path)
    assert readiness._reference_nodes(tmp_path) is None
    assert not [f for f in report.findings if f.code == "RDY002"]
    assert [f.code for f in report.findings] == ["RDY001"], "the unsupported capability still counts"


def test_rdy010_names_the_facts_that_prove_the_gap(broken_report):
    """The 0.11.0 scorer lesson: a count without names is a hand-diff waiting to happen.

    RDY010 is the one checkpoint whose evidence is outside the model, so the facts that
    carry the topic are named in the message -- otherwise the reader has to grep the
    register to find out what was gathered and never modelled.
    """
    finding = next(f for f in broken_report.findings if f.code == "RDY010")
    assert "Strategy" in finding.message
    assert "fact-unknown-entity" in finding.message
    assert finding.file.endswith("broken.yaml")


def test_rdy010_ignores_topics_that_are_not_layers(broken_root):
    """`topics:` is a free tag by schema. `risk` and `integration` are real topics in the
    golden set, and guessing a layer for them would invent findings out of vocabulary."""
    assert "risk" not in readiness.TOPIC_LAYERS
    assert "integration" not in readiness.TOPIC_LAYERS
    report = readiness.analyse(broken_root)
    layers = {f.message.split(" layer")[0].rsplit(" ", 1)[-1] for f in report.findings if f.code == "RDY010"}
    assert layers <= set(readiness.LAYERS)


def test_findings_are_attributed_to_their_layer(broken_report):
    """The report is read layer by layer, so a finding filed under the wrong one is
    invisible to the person reviewing that layer."""
    assert {f.code for f in _layer(broken_report, "Application").findings} <= {"RDY005", "RDY006", "RDY007"}
    assert {f.code for f in _layer(broken_report, "Technology").findings} == {"RDY008"}
    assert {f.code for f in _layer(broken_report, "Motivation").findings} == {"RDY009"}


def test_gold_is_deliberately_not_readiness_complete(repo_root):
    """Recorded as a decision so nobody "fixes" it later.

    `clinic`'s applications carry no `lifecycle` or `timeDisposition` because the
    interview says nothing about either. Adding them to satisfy this report would be
    editing gold against a tool's output -- the move `eval/golden/README.md` forbids. The
    capability layer *was* added, and that is the difference: it was argued from a
    sentence in a skill, not from a finding.
    """
    clinic = repo_root / "eval" / "golden" / "clinic"
    report = readiness.analyse(clinic)
    assert {f.code for f in report.warnings} == {"RDY005"}
    assert not _layer(report, "Strategy").empty, "the 2026-08-06 capability layer"
    assert _layer(report, "Strategy").findings == [], "each capability has a realizer"


# ------------------------------------------------------------------------------- CLII


def test_cli_readiness_is_advisory_by_default(broken_root, capsys):
    assert cli.main(["readiness", "--root", str(broken_root)]) == 0
    out = capsys.readouterr().out
    assert "RDY004" in out
    assert "empty -- nothing modelled here yet" in out


def test_cli_readiness_strict_gates(example_root, broken_root, capsys):
    assert cli.main(["readiness", "--root", str(example_root), "--strict"]) == 0
    assert cli.main(["readiness", "--root", str(broken_root), "--strict"]) == 1
    capsys.readouterr()


def test_cli_readiness_reads_the_zone_it_is_asked_for(broken_root, capsys):
    assert cli.main(["readiness", "--root", str(broken_root), "--zone", "staging"]) == 0
    assert "RDY001" in capsys.readouterr().out


def test_cli_readiness_writes_json(example_root, tmp_path, capsys):
    out = tmp_path / "readiness.json"
    assert cli.main(["readiness", "--root", str(example_root), "--json", str(out)]) == 0
    capsys.readouterr()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["summary"]["errors"] == 0
    assert [layer["layer"] for layer in payload["layers"]] == list(readiness.LAYERS)


def test_an_empty_repository_has_no_open_checkpoints(tmp_path):
    report = readiness.analyse(tmp_path)
    assert not report.warnings
    assert all(layer.empty for layer in report.layers)


def test_an_unknown_zone_is_refused(example_root):
    with pytest.raises(ValueError):
        readiness.analyse(example_root, zone="wishful")
