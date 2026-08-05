"""Maintenance reports and agent context packs must be deterministic, honest about
gaps, and scoped to the approved zone only."""

from datetime import date

from easkills import cli, contextpack, reports

TODAY = date(2026, 8, 3)


# ------------------------------------------------------------------------- staleness


def test_staleness_counts_and_ages(example_root):
    data = reports.staleness(example_root, today=TODAY)
    assert data["elements"] == 17
    assert data["stale"] == 0 and data["unreviewed"] == 0
    oldest = max(r["age"] for r in data["rows"])
    assert oldest == (TODAY - date(2026, 6, 30)).days


def test_staleness_flags_old_content(example_root):
    data = reports.staleness(example_root, today=date(2028, 1, 1))
    assert data["stale"] == data["elements"]


# ------------------------------------------------------------------------------- KPI


def test_kpi_metrics(example_root):
    data = reports.kpi(example_root, today=TODAY)
    assert data["size"]["elements"] == 17
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
    assert data["neverRequested"] == 14


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
