"""The governance contract harness, checked against hand-written answers.

`eval/harness/contracts.py` needs an API key, so the default gate cannot run it -- but the
part that decides pass or fail is deterministic, and an unsatisfiable contract would look
exactly like a bad skill forever. So each contract gets a **reference answer** written here
by hand: a record a careful architect would file. Every check must pass on it, and must fail
on the specific mutation it exists to catch.

This is the same discipline as the golden set: prove the instrument moves in the right
direction before trusting what it says about the thing being measured.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / "eval" / "harness"


@pytest.fixture(scope="module")
def contracts():
    """Load the harness module without the SDK installed: only its checks are used."""
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    spec = importlib.util.spec_from_file_location("ea_contracts", HARNESS / "contracts.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ea_contracts"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def repository(tmp_path) -> Path:
    root = tmp_path / "example"
    shutil.copytree(REPO_ROOT / "eval" / "example", root)
    return root


def write(root: Path, relative: str, data: dict) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def failures(results) -> list[str]:
    return [item.name for item in results if not item.passed]


# ------------------------------------------------------------------- reference answers

DECISION = {
    "id": "decision-wms-stays-on-premise",
    "title": "The warehouse management system stays on-premise through 2027",
    "status": "accepted",
    "date": "2026-08-06",
    "context": "The cloud move has no approved budget and peak season starts in October.",
    "decision": "The WMS remains on-premise until the 2028 planning round revisits it.",
    "rationale": "A migration during peak season risks dispatch; no budget exists to do it earlier.",
    "consequences": "The on-premise hosting waiver must be renewed; the 2028 plateau keeps the move.",
    "options": [
        {
            "option": "Stay on-premise (chosen)",
            "pros": "No peak-season risk, no unfunded work.",
            "cons": "Hosting standard stays waived for another year.",
        },
        {
            "option": "Phased lift-and-shift in Q1",
            "pros": "Ends the waiver sooner.",
            "cons": "Unfunded, and Q1 overlaps the finance freeze.",
        },
        {
            "option": "Replace the WMS with a SaaS product",
            "pros": "Removes the hosting question entirely.",
            "cons": "A programme, not a migration; nobody has assessed it.",
        },
    ],
    "relatedElements": ["app-wms"],
}

DISPENSATION = {
    "id": "disp-erp-database-version",
    "title": "The ERP database may stay below PostgreSQL 16 until the freeze lifts",
    "waives": {"standard": "std-postgresql-16"},
    "appliesTo": ["node-erp-app-server", "sysswt-postgresql"],
    "rationale": "The upgrade window is blocked until the finance year-end freeze lifts.",
    "grantedBy": "architecture-board@aurorafoods.example",
    "granted": "2026-08-06",
    "expires": "2027-03-31",
    "status": "open",
}

SUPERSEDING = {
    "id": "decision-portal-event-channel",
    "title": "The portal gets an event-based stock channel alongside the order API",
    "status": "accepted",
    "date": "2026-08-06",
    "context": "A single synchronous API made the portal unavailable whenever the ERP was down.",
    "decision": "Stock levels reach the portal over an event channel; orders still use the API.",
    "rationale": "Removing the outage class matters more than the single-contract simplicity.",
    "consequences": "Two contracts to govern; the portal degrades instead of failing.",
    "options": [
        {"option": "Event channel (chosen)", "pros": "Portal survives an ERP outage.", "cons": "Two contracts."},
        {"option": "Keep the single API", "pros": "One contract.", "cons": "The outage class stays."},
    ],
    "relatedElements": ["app-erp-core", "app-order-portal", "service-order-api"],
}


def supersede(root: Path) -> None:
    """The three moves `ea-adr` prescribes, all of them."""
    write(root, "governance-log/decisions/decision-portal-event-channel.yaml", SUPERSEDING)
    old = root / "governance-log" / "decisions" / "decision-order-api-single-integration.yaml"
    data = yaml.safe_load(old.read_text(encoding="utf-8"))
    data["status"] = "superseded"
    data["supersededBy"] = SUPERSEDING["id"]
    data.pop("relatedElements", None)
    old.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


# ----------------------------------------------------------- the contracts are satisfiable


def test_the_reference_decision_holds_every_check(contracts, repository):
    write(repository, "governance-log/decisions/decision-wms-stays-on-premise.yaml", DECISION)
    assert failures(contracts.decision_checks(repository)) == []


def test_the_reference_dispensation_holds_every_check(contracts, repository):
    write(repository, "governance-log/dispensations/disp-erp-database-version.yaml", DISPENSATION)
    assert failures(contracts.dispensation_checks(repository)) == []


def test_the_reference_supersession_holds_every_check(contracts, repository):
    supersede(repository)
    assert failures(contracts.supersede_checks(repository)) == []


def test_the_reference_records_pass_the_real_governance_gate(contracts, repository):
    from easkills import govern

    write(repository, "governance-log/decisions/decision-wms-stays-on-premise.yaml", DECISION)
    write(repository, "governance-log/dispensations/disp-erp-database-version.yaml", DISPENSATION)
    report = govern.validate_governance(repository, today=contracts.TODAY)
    assert report.ok, report.render()


# --------------------------------------------------- and they catch what they exist for


def test_a_decision_bound_to_nothing_fails(contracts, repository):
    write(
        repository,
        "governance-log/decisions/decision-wms-stays-on-premise.yaml",
        {**DECISION, "relatedElements": []},
    )
    assert "bound to real model elements" in failures(contracts.decision_checks(repository))


def test_a_decision_that_praises_only_the_winner_fails(contracts, repository):
    write(
        repository,
        "governance-log/decisions/decision-wms-stays-on-premise.yaml",
        {**DECISION, "options": [{"option": "Stay on-premise", "pros": "Cheap."}]},
    )
    assert "the rejected options are recorded with pros and cons" in failures(
        contracts.decision_checks(repository)
    )


def test_a_blanket_waiver_fails(contracts, repository):
    every_element = sorted(contracts.model_ids(repository))
    write(
        repository,
        "governance-log/dispensations/disp-erp-database-version.yaml",
        {**DISPENSATION, "appliesTo": every_element, "expires": "2031-01-01"},
    )
    broken = failures(contracts.dispensation_checks(repository))
    assert "scoped to real elements, not to everything" in broken
    assert "the window is bounded and defensible" in broken


def test_a_waiver_against_an_invented_standard_fails(contracts, repository):
    write(
        repository,
        "governance-log/dispensations/disp-erp-database-version.yaml",
        {**DISPENSATION, "waives": {"standard": "std-invented"}},
    )
    assert "waives a standard that exists" in failures(contracts.dispensation_checks(repository))


def test_a_supersession_that_leaves_the_elements_behind_fails(contracts, repository):
    """The whole reason the paragraph in `ea-adr` exists: `CORR001`."""
    supersede(repository)
    old = repository / "governance-log" / "decisions" / "decision-order-api-single-integration.yaml"
    data = yaml.safe_load(old.read_text(encoding="utf-8"))
    data["relatedElements"] = ["app-order-portal"]
    old.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    broken = failures(contracts.supersede_checks(repository))
    assert "the superseded record governs nothing" in broken
    assert "no CORR001 correspondence violation" in broken


def test_a_supersession_without_a_pointer_fails(contracts, repository):
    supersede(repository)
    old = repository / "governance-log" / "decisions" / "decision-order-api-single-integration.yaml"
    data = yaml.safe_load(old.read_text(encoding="utf-8"))
    data.pop("supersededBy")
    old.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    assert "supersededBy points at the successor" in failures(contracts.supersede_checks(repository))


def test_rewriting_the_old_record_instead_of_amending_it_fails(contracts, repository):
    """"Status transitions are records, not edits" -- deleting history is the failure."""
    supersede(repository)
    (repository / "governance-log" / "decisions" / "decision-order-api-single-integration.yaml").unlink()
    assert "the old record still exists" in failures(contracts.supersede_checks(repository))


# ------------------------------------------------------------------- the harness itself


def test_every_contract_names_skills_that_exist(contracts):
    for contract in contracts.CONTRACTS:
        for name in contract.skills:
            assert (REPO_ROOT / "skills" / name / "SKILL.md").is_file(), name


def test_the_coverage_page_classifies_every_skill_exactly_once(contracts):
    """`docs/SKILL-COVERAGE.md` is the honest answer to "what measures which skill".

    Every skill gets a row, and the rows for the measured ones must agree with the
    harnesses' own declarations -- a coverage claim that drifts from the code is worse than
    no claim, because it reads as coverage that exists.
    """
    page = (REPO_ROOT / "docs" / "SKILL-COVERAGE.md").read_text(encoding="utf-8")
    table = page.split("## Every skill, and what would catch a defect in it", 1)[1].split("##", 1)[0]
    rows = {
        line.split("|")[1].strip().strip("`"): line.split("|")[2].strip()
        for line in table.splitlines()
        if line.startswith("| `")
    }
    skills = {path.name for path in (REPO_ROOT / "skills").iterdir() if path.is_dir()}
    assert set(rows) == skills, f"missing {sorted(skills - set(rows))}, extra {sorted(set(rows) - skills)}"

    contract_skills = {name for contract in contracts.CONTRACTS for name in contract.skills}
    for name in sorted(contract_skills):
        assert "contract" in rows[name], f"{name} is contract-checked but the page says {rows[name]!r}"

    import ast

    tree = ast.parse((HARNESS / "run.py").read_text(encoding="utf-8"))
    measured = next(
        ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "MEASURED_SKILLS"
    )
    for phase, names in measured.items():
        expected = "contract" if phase == "apparatus" else "scored"
        for name in names:
            assert expected in rows[name], f"{name} ({phase}) is listed as {rows[name]!r}"


def test_the_contract_harness_is_offline_except_for_the_model(contracts):
    """Same quarantine as the scoring harness: it may call the API, the core may not."""
    source = (HARNESS / "contracts.py").read_text(encoding="utf-8")
    assert "import anthropic" not in source, "the SDK is reached through common.client()"
    assert "TODAY = date(" in source, "a contract judged against the wall clock is not a contract"
