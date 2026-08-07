"""Maintenance reports and agent context packs must be deterministic, honest about
gaps, and scoped to the approved zone only."""

import os
from datetime import date

from easkills import cli, contextpack, reports

TODAY = date(2026, 8, 3)


# ------------------------------------------------------------------------- staleness


def test_staleness_counts_and_ages(example_root):
    data = reports.staleness(example_root, today=TODAY)
    assert data["elements"] == 20
    assert data["stale"] == 0 and data["unreviewed"] == 0
    oldest = max(r["age"] for r in data["rows"])
    assert oldest == (TODAY - date(2026, 6, 30)).days


def test_staleness_flags_old_content(example_root):
    data = reports.staleness(example_root, today=date(2028, 1, 1))
    assert data["stale"] == data["elements"]


# ------------------------------------------------------------------------------- KPI


def test_kpi_metrics(example_root):
    data = reports.kpi(example_root, today=TODAY)
    assert data["size"]["elements"] == 20
    assert data["evidence"]["assumed"] == 2
    assert data["governance"]["ownedShare"] == 1.0
    assert data["governance"]["openDispensations"] == 1
    assert data["portfolio"]["obsolescenceExposure"] == ["app-erp-core", "app-wms"]
    assert data["capabilities"]["unsupported"] == []
    assert data["documentation"]["unframedConcerns"] == []


def test_kpi_of_an_empty_repository_is_not_self_contradictory(tmp_path):
    """A share of *bad* things must read 0% when there is nothing to measure.

    A scaffolded repository used to report "100% owned; 100% stale/unreviewed" on the
    same line -- the first screen a new user sees, stating two opposite things.
    """
    (tmp_path / "model" / "approved").mkdir(parents=True)
    data = reports.kpi(tmp_path, today=TODAY)
    assert data["governance"]["staleShare"] == 0.0
    assert "0% stale/unreviewed" in reports.render_kpi(data)


def test_conformance_6_8_fails_when_assumptions_are_not_in_the_description(tmp_path, example_root):
    """§6.8 is about the architecture *description*, so the check reads the document.

    It was a hardcoded 'pass' -- decorative conformance in the one report whose whole
    point is refusing to present silence as conformance.
    """
    import shutil

    repo = tmp_path / "repo"
    shutil.copytree(example_root, repo)
    clause = lambda root: next(  # noqa: E731 - local helper
        i for i in reports.conformance(root, today=TODAY)["items"] if i["clause"] == "6.8"
    )
    assert clause(repo)["status"] == "pass"

    (repo / "docs" / "architecture-description.md").unlink()
    failed = clause(repo)
    assert failed["status"] == "fail"
    assert "easkills docs" in failed["detail"]


def test_kpi_demand_metrics(example_root):
    """AaaS is measured by consumption: offerings, requests, SLA state, fulfilment."""
    data = reports.kpi(example_root, today=TODAY)
    service = data["service"]
    assert service["offerings"] == 3
    assert service["requests"] == 2
    assert service["open"] == 0 and service["fulfilled"] == 2
    assert service["slaBreaches"] == []
    assert service["avgFulfilmentDays"] == 3.5


def test_kpi_flags_sla_breach(tmp_path, example_root):
    import shutil

    repo = tmp_path / "repo"
    shutil.copytree(example_root, repo)
    (repo / "governance-log" / "requests" / "req-late.yaml").write_text(
        "id: req-late\n"
        "service: svc-context-pack\n"
        "requestedBy: someone@aurorafoods.example\n"
        "requested: 2026-07-01\n"
        "status: open\n",
        encoding="utf-8",
    )
    data = reports.kpi(repo, today=TODAY)
    assert data["service"]["slaBreaches"] == ["req-late"]


def test_staleness_carries_demand(example_root):
    """Demand-weighted maintenance: requests' scopes count per element."""
    data = reports.staleness(example_root, today=TODAY)
    by_id = {r["id"]: r for r in data["rows"]}
    assert by_id["app-erp-core"]["demand"] == 1
    assert by_id["app-order-portal"]["demand"] == 1
    assert by_id["app-wms"]["demand"] == 0
    assert data["neverRequested"] == 17


# ------------------------------------------------------------------------------ debt


def test_debt_register_on_example(example_root):
    data = reports.debt(example_root, today=TODAY)
    kinds = {item["kind"] for item in data["items"]}
    # The example's only debt is the deliberately waived on-premise standard.
    assert kinds == {"dead-standard-reference"}
    assert all("disp-onprem-legacy" in i["detail"] for i in data["items"])


def test_debt_register_on_broken(broken_root):
    data = reports.debt(broken_root, today=date(2026, 7, 30))
    kinds = {item["kind"] for item in data["items"]}
    assert "isolated-element" in kinds
    assert "duplicate-name" in kinds
    assert "stale-content" in kinds
    assert "dead-standard-reference" in kinds


# ------------------------------------------------------- overlap and rationalization


def _overlap_root(tmp_path, body: str):
    """A throwaway model root. Overlap is a portfolio shape, and the worked example is
    deliberately not that shape -- a wholesaler that ran two order systems would be a
    worse teaching example, so these queries are exercised on fixtures built per test."""
    approved = tmp_path / "model" / "approved"
    approved.mkdir(parents=True)
    (approved / "overlap.yaml").write_text(body, encoding="utf-8", newline="\n")
    return tmp_path


def _kinds(data, kind: str) -> list[dict]:
    return [item for item in data["items"] if item["kind"] == kind]


TWO_REALIZERS = """\
elements:
  - id: cap-billing
    type: Capability
    name: Billing
  - id: app-legacy
    type: ApplicationComponent
    name: Legacy Suite
    properties:
      timeDisposition: Eliminate
      functionalFit: poor
  - id: app-saas
    type: ApplicationComponent
    name: SaaS Platform
    properties:
      lifecycle: production
  - id: role-collections
    type: BusinessRole
    name: Collections Team
relationships:
  - id: rel-legacy-billing
    type: Realization
    source: app-legacy
    target: cap-billing
  - id: rel-saas-billing
    type: Realization
    source: app-saas
    target: cap-billing
  - id: rel-role-billing
    type: Realization
    source: role-collections
    target: cap-billing
"""


def test_a_capability_realized_twice_is_a_rationalization_candidate(tmp_path):
    data = reports.debt(_overlap_root(tmp_path, TWO_REALIZERS), today=TODAY)
    candidates = _kinds(data, "rationalization-candidate")
    assert [c["concept"] for c in candidates] == ["cap-billing"]
    assert [r["id"] for r in candidates[0]["realizers"]] == ["app-legacy", "app-saas"]
    # Every finding names its items: the realizer ids are in the printed line too, not
    # only in the JSON, so the terminal reader never has to go looking.
    assert "app-legacy" in candidates[0]["detail"] and "app-saas" in candidates[0]["detail"]


def test_a_business_role_realizing_a_capability_is_not_duplicate_functionality(tmp_path):
    """Division of labour is not overlap.

    The golden set's Appointment Booking is realized by the booking portal *and* the
    front desk -- correct modelling of a clinic. Counting the role as a realizer would
    make the query fire on it, which is the RDY008 mistake: for an advisory report the
    only real failure mode is noise.
    """
    data = reports.debt(_overlap_root(tmp_path, TWO_REALIZERS), today=TODAY)
    realizers = _kinds(data, "rationalization-candidate")[0]["realizers"]
    assert "role-collections" not in {r["id"] for r in realizers}
    assert "BusinessRole" not in reports.RATIONALIZATION_REALIZER_TYPES


def test_the_candidate_carries_the_properties_the_decision_needs(tmp_path):
    """"Two systems do this" is a question; "two systems do this, one Eliminate with a
    poor fit, one in production" is a decision. Unset keys say so rather than vanishing,
    and keys this repository never invented are printed because the operator's own fit
    score is exactly the column that matters."""
    data = reports.debt(_overlap_root(tmp_path, TWO_REALIZERS), today=TODAY)
    rendered = reports.render_debt(data)
    assert "timeDisposition: Eliminate" in rendered
    assert "functionalFit: poor" in rendered, "an operator's own property key is not dropped"
    assert "lifecycle: not recorded" in rendered, "an unset portfolio key is stated, not omitted"


TWO_SHARED = """\
elements:
  - id: cap-billing
    type: Capability
    name: Billing
  - id: cap-crm
    type: Capability
    name: Customer Management
  - id: app-legacy
    type: ApplicationComponent
    name: Legacy Suite
  - id: app-saas
    type: ApplicationComponent
    name: SaaS Platform
relationships:
  - id: rel-legacy-billing
    type: Realization
    source: app-legacy
    target: cap-billing
  - id: rel-saas-billing
    type: Realization
    source: app-saas
    target: cap-billing
  - id: rel-legacy-crm
    type: Realization
    source: app-legacy
    target: cap-crm
  - id: rel-saas-crm
    type: Realization
    source: app-saas
    target: cap-crm
"""


def test_an_application_pair_sharing_two_capabilities_is_reported_once(tmp_path):
    data = reports.debt(_overlap_root(tmp_path, TWO_SHARED), today=TODAY)
    pairs = _kinds(data, "overlapping-applications")
    assert len(pairs) == 1, "an unordered pair is one finding, not two"
    assert pairs[0]["pair"] == ["app-legacy", "app-saas"]
    assert pairs[0]["shared"] == ["cap-billing", "cap-crm"]


def test_one_shared_capability_is_not_yet_a_pair(tmp_path):
    """The threshold is what separates the two queries. One shared capability is already
    a rationalization candidate; the *pair* only becomes a merge conversation when the
    overlap repeats, and reporting both at one shared capability would just say the same
    thing twice in two vocabularies."""
    body = TWO_SHARED.replace(
        "  - id: rel-saas-crm\n    type: Realization\n    source: app-saas\n    target: cap-crm\n", ""
    )
    data = reports.debt(_overlap_root(tmp_path, body), today=TODAY)
    assert _kinds(data, "overlapping-applications") == []
    assert [c["concept"] for c in _kinds(data, "rationalization-candidate")] == ["cap-billing"]
    assert reports.OVERLAP_MIN_SHARED == 2


def test_two_realizations_between_one_pair_do_not_invent_an_overlap(tmp_path):
    """A duplicated edge is a modelling slip. Counting it as a second realizer would turn
    that slip into a portfolio finding, and someone would go to a meeting about it."""
    body = TWO_REALIZERS + """\
  - id: rel-legacy-billing-again
    type: Realization
    source: app-legacy
    target: cap-billing
"""
    body = body.replace(
        "  - id: rel-saas-billing\n    type: Realization\n    source: app-saas\n    target: cap-billing\n", ""
    )
    data = reports.debt(_overlap_root(tmp_path, body), today=TODAY)
    assert _kinds(data, "rationalization-candidate") == []


DUPLICATE_SERVICES = """\
elements:
  - id: app-legacy
    type: ApplicationComponent
    name: Legacy Suite
  - id: role-collections
    type: BusinessRole
    name: Collections Team
  - id: svc-invoice-a
    type: ApplicationService
    name: Invoice Issuing
  - id: svc-invoice-b
    type: BusinessService
    name: invoice   issuing
relationships:
  - id: rel-legacy-invoice
    type: Realization
    source: app-legacy
    target: svc-invoice-a
  - id: rel-collections-invoice
    type: Assignment
    source: role-collections
    target: svc-invoice-b
"""


def test_services_named_alike_and_offered_by_different_providers_are_reported(tmp_path):
    """The plain duplicate-name query compares type *and* name, so it cannot see these
    two at all -- and it would say nothing about who offers them, which is the only fact
    that separates "two teams built the same thing" from "someone typed a name twice"."""
    data = reports.debt(_overlap_root(tmp_path, DUPLICATE_SERVICES), today=TODAY)
    duplicates = _kinds(data, "duplicate-service")
    assert [d["concept"] for d in duplicates] == ["svc-invoice-b"]
    assert duplicates[0]["duplicateOf"] == "svc-invoice-a"
    assert duplicates[0]["providers"] == ["role-collections"]
    assert duplicates[0]["otherProviders"] == ["app-legacy"]
    assert _kinds(data, "duplicate-name") == [], "different types -- the older query is blind here"
    # Whitespace and case are noise in a name comparison; the register would otherwise
    # miss the most common way a duplicate actually gets typed.
    assert "invoice   issuing" in duplicates[0]["detail"]


def test_a_service_realizing_an_identically_named_service_is_idiomatic_layering(tmp_path):
    """An application service realizing the business service of the same name is textbook
    ArchiMate. A query that flagged it would punish correct modelling -- so a pair already
    joined by a relationship is excluded, and this test is what keeps the exclusion."""
    body = DUPLICATE_SERVICES + """\
  - id: rel-app-realizes-business
    type: Realization
    source: svc-invoice-a
    target: svc-invoice-b
"""
    data = reports.debt(_overlap_root(tmp_path, body), today=TODAY)
    assert _kinds(data, "duplicate-service") == []


def test_one_component_publishing_two_same_named_services_is_not_portfolio_duplication(tmp_path):
    """Same provider, so nothing was built twice. That is a modelling slip for
    duplicate-name to catch, and reporting it here would put a naming typo on the
    rationalization list."""
    body = DUPLICATE_SERVICES.replace("source: role-collections", "source: app-legacy")
    data = reports.debt(_overlap_root(tmp_path, body), today=TODAY)
    assert _kinds(data, "duplicate-service") == []


def test_the_worked_example_and_the_golden_set_are_overlap_free(example_root, repo_root):
    """Both are teaching material. A wholesaler running two order systems, or a two-doctor
    clinic running two EHRs, would teach the wrong shape -- so the overlap queries must
    stay silent on them, and this test is how a future edit that introduces duplication
    by accident gets caught."""
    for root in (example_root, repo_root / "eval" / "golden" / "clinic"):
        kinds = {item["kind"] for item in reports.debt(root, today=TODAY)["items"]}
        assert not (kinds & set(reports.OVERLAP_KINDS)), f"{root.name} has grown an overlap"
        assert kinds <= set(reports.DEBT_KINDS), "the register emits a kind nothing documents"


def test_overlap_findings_are_stable_across_hash_seeds(tmp_path, repo_root):
    """Byte stability, tested the only way that can fail.

    The overlap queries build sets of ids, and set iteration order moves with the
    interpreter's string-hash seed -- which is randomised *per process*, so comparing
    two calls inside one test would pass while the register produced a different
    diff on every real run. Two subprocesses with pinned, different seeds is the check.
    """
    import subprocess
    import sys

    root = _overlap_root(tmp_path, TWO_SHARED)
    outputs = []
    for seed in ("0", "12345"):
        result = subprocess.run(
            [sys.executable, "-m", "easkills", "debt", "--root", str(root), "--as-of", TODAY.isoformat()],
            capture_output=True,
            text=True,
            cwd=repo_root,
            env={**os.environ, "PYTHONHASHSEED": seed, "NO_COLOR": "1"},
        )
        assert result.returncode == 0, result.stderr
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
    assert "app-legacy" in outputs[0] and "cap-crm" in outputs[0]


# ----------------------------------------------------------------------- conformance


def test_conformance_passes_the_checkable_clauses(example_root):
    data = reports.conformance(example_root, today=TODAY)
    assert data["failed"] == 0
    by_clause = {i["clause"]: i["status"] for i in data["items"]}
    assert by_clause["6.9"] == "pass"
    assert by_clause["6.10"] == "pass"


def test_an_unimplemented_clause_would_still_be_labelled_a_gap(tmp_path):
    """The `gap` status must stay reachable. It is the mechanism that keeps silence from
    reading as conformance, and the day every clause passes on an empty repository is the
    day the checklist has become decoration."""
    items = reports.conformance(tmp_path)["items"]
    assert {i["clause"] for i in items if i["status"] == "gap"} == {"6.9"}
    assert next(i for i in items if i["clause"] == "6.10")["status"] == "fail"


def test_conformance_fails_without_the_apparatus(tmp_path):
    data = reports.conformance(tmp_path)
    assert data["failed"] > 0


# ------------------------------------------------------------------------------ delta


def test_delta_lists_unmodelled_entities_and_unused_facts(example_root):
    data = reports.delta(example_root)
    unmodelled = {row["entity"] for row in data["unmodelledEntities"]}
    assert "service-desk" in unmodelled, "the interview names a service desk the model does not have"
    assert "erp-core" not in unmodelled, "name-matched entities are not candidates"
    unused = {row["fact"] for row in data["unusedFacts"]}
    assert "fact-po-retention" not in unused, "facts cited by the model are used"


# ---------------------------------------------------------------------- context packs


def test_context_pack_for_an_application(example_root):
    pack = contextpack.build(example_root, "app-erp-core", today=TODAY)
    text = pack.markdown
    assert "Retain Purchase Orders for Seven Years" in text, "binding requirement present"
    assert "disp-onprem-legacy" in text and "2027-06-30" in text, "waiver with expiry present"
    assert "The order API stays the only integration" in text, "related decision present"
    assert "-- current." in text, "freshness statement present"
    assert "Order Portal" not in text.split("## Integration context")[0], "pack stays scoped"


def test_context_pack_flags_stale_content(example_root):
    pack = contextpack.build(example_root, "app-erp-core", today=date(2028, 1, 1))
    assert "Freshness warning" in pack.markdown
    assert "advisory" in pack.markdown


def test_context_pack_never_calls_an_unreadable_review_date_current(tmp_path):
    """The freshness banner is the pack's one mandatory claim; it must not be bluffed.

    It used to be decided by testing for the substring "stale", so an element whose
    review date was not a date at all fell through to "-- current."
    """
    (tmp_path / "model" / "approved").mkdir(parents=True)
    (tmp_path / "model/approved/m.yaml").write_text(
        "elements:\n"
        "  - id: app-x\n    type: ApplicationComponent\n    name: App X\n"
        "    owner: owner@example.test\n    lastReviewed: '2026-06-31'\n"
        "    assumed: true\n    rationale: Probe element with a date that is not a date.\n",
        encoding="utf-8",
        newline="\n",
    )
    text = contextpack.build(tmp_path, "app-x", today=TODAY).markdown
    assert "Freshness warning" in text and "unreadable review date" in text
    assert "-- current." not in text


def test_context_pack_for_a_capability_expands_to_realizers(example_root):
    pack = contextpack.build(example_root, "cap-order-management", today=TODAY)
    assert "`app-erp-core`" in pack.markdown


def test_context_pack_unknown_scope_raises(example_root):
    import pytest

    with pytest.raises(contextpack.ContextError):
        contextpack.build(example_root, "no-such-element", today=TODAY)


def test_context_pack_is_byte_stable(example_root):
    first = contextpack.build(example_root, "app-erp-core", today=TODAY).markdown
    second = contextpack.build(example_root, "app-erp-core", today=TODAY).markdown
    assert first == second


# ------------------------------------------------------------------------------- CLI


def test_cli_reports_run_clean(example_root, capsys):
    for command in ("staleness", "kpi", "debt", "delta"):
        assert cli.main([command, "--root", str(example_root)]) == 0
        capsys.readouterr()


def test_cli_conformance_strict_gate(example_root, tmp_path, capsys):
    assert cli.main(["conformance", "--root", str(example_root), "--strict"]) == 0
    capsys.readouterr()
    assert cli.main(["conformance", "--root", str(tmp_path), "--strict"]) == 1
    capsys.readouterr()


def test_cli_context_writes_a_pack(example_root, tmp_path, capsys):
    out = tmp_path / "pack.md"
    assert cli.main(["context", "--root", str(example_root), "--scope", "app-erp-core", "--out", str(out)]) == 0
    capsys.readouterr()
    assert "EA context: ERP Core" in out.read_text(encoding="utf-8")


def test_cli_context_unknown_scope_exits_one(example_root, capsys):
    assert cli.main(["context", "--root", str(example_root), "--scope", "nope"]) == 1
    capsys.readouterr()
