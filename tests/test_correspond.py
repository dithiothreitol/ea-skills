"""ISO 42010 §6.9: correspondences are derived from the records that already declare
them, held to stated rules, and the two rules nothing else checked must actually fire.

The point of these tests is the failure direction. A correspondence table that only ever
agrees with itself would be the decorative conformance this repository refuses, so every
kind is exercised with a repository where the relation has gone wrong.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from easkills import cli, correspond, docgen, dsl, govern, reports

TODAY = date(2026, 7, 30)


def _derive(root: Path, today: date = TODAY) -> list[correspond.Correspondence]:
    model, _documents, _config = dsl.load(root, "approved")
    return correspond.derive(model, govern.load(root), today)


@pytest.fixture()
def repo(tmp_path, example_root) -> Path:
    target = tmp_path / "repo"
    shutil.copytree(example_root, target)
    return target


# ------------------------------------------------------------------ the clean example


def test_the_example_records_every_kind_of_correspondence(example_root):
    """One AD, five rules -- and each rule has something to hold together."""
    kinds = {c.kind for c in _derive(example_root)}
    assert kinds == {rule.kind for rule in correspond.RULES}


def test_the_example_violates_none(example_root):
    assert [c for c in _derive(example_root) if not c.satisfied] == []


def test_derivation_is_stable(example_root):
    assert _derive(example_root) == _derive(example_root)


def test_every_rule_names_a_code_the_catalogue_actually_has(repo_root):
    """`enforcedBy` is the honest column: a rule pointing at a code that does not exist
    would be a promise of enforcement, which is worse than admitting there is none."""
    catalogue = (repo_root / "docs" / "RULES.md").read_text(encoding="utf-8")
    for rule in correspond.RULES:
        assert rule.enforced_by, f"{rule.kind} claims no enforcement"
        for code in rule.enforced_by:
            assert f"`{code}`" in catalogue, f"{rule.kind} cites {code}, which is not in docs/RULES.md"


# ------------------------------------------------------------ CORR001: decision drift


def _supersede_the_example_decision(repo: Path) -> None:
    path = repo / "governance-log" / "decisions" / "decision-order-api-single-integration.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("status: accepted", "status: superseded"),
        encoding="utf-8",
        newline="\n",
    )


def test_an_element_realising_a_superseded_decision_is_a_violation(repo):
    _supersede_the_example_decision(repo)
    violated = [c for c in _derive(repo) if not c.satisfied]
    assert {c.target for c in violated} == {"app-erp-core", "app-order-portal", "service-order-api"}
    assert all(c.code == "CORR001" and c.kind == "realizes" for c in violated)
    assert "superseded" in violated[0].detail


def test_decision_drift_reaches_the_governance_gate(repo):
    """A finding, not just a table entry -- otherwise nobody runs into it."""
    _supersede_the_example_decision(repo)
    report = govern.validate_governance(repo, today=TODAY)
    assert "CORR001" in {f.code for f in report.warnings}
    assert report.ok, "drift between the log and the model is a warning: the model is not malformed"


def test_a_proposed_decision_is_still_standing(repo):
    """Elements realising a proposal are ahead of the log, which is a legitimate state."""
    path = repo / "governance-log" / "decisions" / "decision-order-api-single-integration.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("status: accepted", "status: proposed"),
        encoding="utf-8",
        newline="\n",
    )
    assert [c for c in _derive(repo) if not c.satisfied] == []


# --------------------------------------------------- CORR002: obligation without bearer


def _eliminate(repo: Path, *element_ids: str) -> None:
    """Mark elements TIME 'Eliminate' by appending the property to each."""
    path = repo / "model" / "approved" / "application.yaml"
    text = path.read_text(encoding="utf-8")
    for element_id in element_ids:
        head, sep, tail = text.partition(f"  - id: {element_id}\n")
        assert sep, element_id
        line_end = tail.index("\n    provenance:")
        text = head + sep + tail[:line_end] + "\n    properties:\n      timeDisposition: Eliminate" + tail[line_end:]
    path.write_text(text, encoding="utf-8", newline="\n")


def test_one_eliminated_bearer_among_several_is_a_plan_not_a_gap(repo):
    """`req-po-retention` binds the ERP core and the order record; retiring one of them
    is a migration, and reporting it would train people to ignore the rule."""
    _eliminate(repo, "app-erp-core")
    assert [c for c in _derive(repo) if not c.satisfied] == []


def test_an_obligation_whose_every_bearer_goes_is_a_violation(repo):
    """The audit trap: the seven-year retention requirement, and nothing left to hold
    the records in."""
    _eliminate(repo, "app-erp-core")
    data = repo / "model" / "approved" / "application.yaml"
    # data-order-record lives in the same file's data section; eliminate it too.
    text = data.read_text(encoding="utf-8")
    head, sep, tail = text.partition("  - id: data-order-record\n")
    assert sep
    line_end = tail.index("\n    provenance:")
    data.write_text(
        head + sep + tail[:line_end] + "\n    properties:\n      timeDisposition: Eliminate" + tail[line_end:],
        encoding="utf-8",
        newline="\n",
    )
    violated = [c for c in _derive(repo) if not c.satisfied]
    assert {c.source for c in violated} == {"req-po-retention"}
    assert {c.target for c in violated} == {"app-erp-core", "data-order-record"}
    assert all(c.code == "CORR002" for c in violated)


# ------------------------------------------------- kinds enforced by rules that exist


def test_a_retired_standard_breaks_its_correspondence_and_cites_the_rule_that_reports_it(repo):
    """No second finding: STD002 already says it. The table records the state and names
    the code, which is what §6.9 asks for and all it asks for."""
    path = repo / "standards" / "std-postgresql-16.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("lifecycle: active", "lifecycle: retired"),
        encoding="utf-8",
        newline="\n",
    )
    violated = [c for c in _derive(repo) if not c.satisfied]
    assert [(c.source, c.target, c.code) for c in violated] == [
        ("sysswt-postgresql", "std-postgresql-16", "STD002")
    ]
    codes = {f.code for f in govern.validate_governance(repo, today=TODAY).findings}
    assert "CORR" not in "".join(codes), "correspondences must not double-report someone else's finding"


def test_a_dangling_reference_is_left_to_the_rule_that_owns_it(broken_root):
    """DEC005/MOT001/COMP005 report the missing far end; the correspondence simply is
    not derived, because there is no second AD element for it to relate to."""
    targets = {c.target for c in _derive(broken_root)}
    assert "no-such-element" not in targets
    assert "no-such-fact" in targets, "a fact reference resolves in the register, not the model"


# --------------------------------------------------------------- the conformance clause


def test_clause_6_9_passes_on_the_example(example_root):
    data = reports.conformance(example_root, today=TODAY)
    item = next(i for i in data["items"] if i["clause"] == "6.9")
    assert item["status"] == "pass"
    assert "20 correspondence(s)" in item["detail"]


def test_clause_6_9_fails_when_a_correspondence_is_violated(repo):
    _supersede_the_example_decision(repo)
    item = next(i for i in reports.conformance(repo, today=TODAY)["items"] if i["clause"] == "6.9")
    assert item["status"] == "fail"
    assert "CORR001" in item["detail"]


def test_clause_6_9_is_a_gap_when_nothing_corresponds(tmp_path):
    """An empty AD does not pass §6.9 by having nothing to be wrong about."""
    item = next(i for i in reports.conformance(tmp_path, today=TODAY)["items"] if i["clause"] == "6.9")
    assert item["status"] == "gap"


def test_clause_6_10_needs_the_decision_in_the_description_not_just_the_log(repo):
    """Same correction §6.8 got: the clause is about the architecture *description*."""
    (repo / "docs" / "architecture-description.md").unlink()
    item = next(i for i in reports.conformance(repo, today=TODAY)["items"] if i["clause"] == "6.10")
    assert item["status"] == "fail"
    assert "architecture-description.md does not exist" in item["detail"]


# ------------------------------------------------------- the description records them


def test_the_description_records_the_rules_and_the_decisions(example_root):
    markdown = docgen.build_markdown(dsl.load(example_root, "approved")[0])
    assert "## 7. Decisions" in markdown and "## 8. Correspondences" in markdown
    for rule in correspond.RULES:
        assert f"`{rule.kind}`" in markdown, f"{rule.kind} is not recorded in the description"
    assert "The order API stays the only integration" in markdown


def test_the_description_records_violations_as_known_inconsistencies(repo):
    _supersede_the_example_decision(repo)
    markdown = docgen.build_markdown(dsl.load(repo, "approved")[0])
    assert "violated" in markdown.lower()
    assert "CORR001" in markdown


def test_the_description_does_not_move_with_the_wall_clock(repo):
    """Correspondence verdicts are evaluated as of the model's own date, so the
    freshness gate cannot fail on a day nobody touched the repository."""
    first = docgen.build_markdown(dsl.load(repo, "approved")[0])
    assert first == docgen.build_markdown(dsl.load(repo, "approved")[0])
    section = first.split("## 8. Correspondences", 1)[1].split("## 9.", 1)[0]
    assert "2027-06-30" not in section, (
        "the on-premise waiver expires in 2027; the table must not depend on whether it has"
    )


# ------------------------------------------------------------------------------- CLI


def test_cli_correspondences_report(example_root, capsys):
    assert cli.main(["correspondences", "--root", str(example_root), "--as-of", "2026-07-30"]) == 0
    out = capsys.readouterr().out
    assert "20 relation(s), 0 violated" in out
    assert "decision-order-api-single-integration -> app-erp-core" in out


def test_cli_correspondences_json(example_root, tmp_path, capsys):
    target = tmp_path / "corr.json"
    assert cli.main(["correspondences", "--root", str(example_root), "--json", str(target)]) == 0
    capsys.readouterr()
    import json

    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["total"] == 20 and data["violated"] == 0
    assert {k["kind"] for k in data["kinds"]} == {rule.kind for rule in correspond.RULES}
