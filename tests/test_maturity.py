"""Maturity: measured signals, documented thresholds, and no composite number.

The load-bearing tests here are about what the report refuses to do — collapse five
dimensions into one figure, hand out a level for something it could not measure, or let
a threshold change in code without the sentence explaining it moving too.
"""

import re
from datetime import date

import pytest

from easkills import alignment, maturity

TODAY = date(2026, 7, 30)


@pytest.fixture(scope="module")
def example(example_root):
    return maturity.assess(example_root, today=TODAY)


# --------------------------------------------------------------------- the ladder


def test_the_documented_thresholds_are_the_ones_the_code_uses(repo_root):
    """The constants-versus-doc pattern `impact` uses for `REARCHITECTING_STAKEHOLDERS`.

    A maturity threshold that lives only in code is a number nobody can argue with, and
    arguing with them is the point: a level is a claim about a practice, and the reader
    has to be able to see what it was measured against.
    """
    text = (repo_root / "docs" / "CLI.md").read_text(encoding="utf-8")
    block = text.split("<!-- maturity-thresholds -->", 1)[1].split("<!-- /maturity-thresholds -->", 1)[0]
    rows = re.findall(r"\|\s*`?(\w+)`?\s*\|\s*(\d)\s*\|\s*`(\w+)`\s*\|\s*(>=|<=)\s*([\d.]+)\s*\|", block)
    documented = {(d, int(level), metric, op, float(value)) for d, level, metric, op, value in rows}

    in_code = {
        (
            dimension.key,
            gate.level,
            gate.metric,
            ">=" if gate.minimum is not None else "<=",
            gate.minimum if gate.minimum is not None else gate.maximum,
        )
        for dimension in maturity.DIMENSIONS
        for gate in dimension.gates
    }
    assert documented == in_code, f"docs/CLI.md and maturity.DIMENSIONS disagree: {documented ^ in_code}"
    assert len(in_code) == 20, "five dimensions, four gates each"


def test_every_gate_reads_a_metric_that_is_actually_measured(example_root):
    metrics = maturity.measure(example_root, TODAY)
    for dimension in maturity.DIMENSIONS:
        for gate in dimension.gates:
            assert gate.metric in metrics, f"{dimension.key} level {gate.level} reads an unmeasured metric"
    assert set(metrics) >= {gate.metric for d in maturity.DIMENSIONS for gate in d.gates}


def test_gates_ascend_and_cover_levels_two_through_five():
    for dimension in maturity.DIMENSIONS:
        assert [gate.level for gate in dimension.gates] == [2, 3, 4, 5], dimension.key


def test_there_is_no_composite_number(example):
    """A single "we are a 3.4" is how maturity becomes theatre: it can be moved by the
    cheapest dimension and it hides which one moved. The absence is the feature, so it
    is tested rather than left to good intentions."""
    payload = example.as_dict()
    assert "overall" not in payload and "score" not in payload and "average" not in payload
    assert set(payload) == {"root", "asOf", "dimensions", "metrics"}
    rendered = example.render()
    assert "no composite" in rendered


# ------------------------------------------------------------------- what it reports


def test_a_level_names_the_items_blocking_the_next_one(example):
    """The named list is the deliverable; the level is the headline."""
    evidence = next(r for r in example.results if r.dimension.key == "evidence")
    assert evidence.level == 4
    assert evidence.next_gate.level == 5
    assert "goal-shorten-lead-time" in evidence.blockers, "the example's two assumptions are what block it"


def test_an_empty_repository_scores_one_and_is_failing_nothing(tmp_path):
    """Level 1 is "measured", not "bad". A report that called a young repository broken
    would be switched off before it ever measured a mature one."""
    (tmp_path / "model" / "approved").mkdir(parents=True)
    report = maturity.assess(tmp_path, today=TODAY)
    assert report.ok
    assert {r.level for r in report.results} == {1}
    assert all(r.next_gate is not None and r.next_gate.level == 2 for r in report.results)


def test_a_share_over_an_empty_population_is_unmeasurable_not_perfect(tmp_path):
    """The defect this report shipped with for one afternoon, pinned so it cannot return.

    A share over nothing is 1.0 and a count of problems over nothing is 0, so the first
    version told an empty repository it was `sustained` on Evidence and Operations. In
    the one report whose number travels into a slide, that is the worst possible default.
    """
    (tmp_path / "model" / "approved").mkdir(parents=True)
    metrics = maturity.measure(tmp_path, TODAY)
    for key in ("evidencedShare", "ownedShare", "staleShare", "sourceCoverage", "expiredDispensations"):
        assert metrics[key].value is None, f"{key} claims a level for an empty population"
        assert metrics[key].unmeasurable, f"{key} is unmeasurable and must say why"
        assert metrics[key].population == 0


def test_an_unmeasurable_metric_shuts_its_gate_rather_than_opening_it(tmp_path, example_root):
    """Scoring level 5 for owning no yardstick is the vacuous-100% trap `--min-coverage`
    already refuses, and it would be worse here: maturity is the number that travels."""
    import shutil

    root = tmp_path / "ex"
    shutil.copytree(example_root, root)
    shutil.rmtree(root / "reference")

    metric = maturity.measure(root, TODAY)["referenceCoverage"]
    assert metric.value is None
    assert "no reference pack" in metric.unmeasurable

    coverage = next(r for r in maturity.assess(root, today=TODAY).results if r.dimension.key == "coverage")
    assert coverage.level == 4, "capped, not promoted"
    assert coverage.next_gate.level == 5
    assert "no reference pack" in maturity.assess(root, today=TODAY).render()


def test_reference_shortfall_names_partials_not_only_gaps(example_root):
    """The worked example is clean under `align --strict`: its 79% is entirely half
    credits. A blocker list holding only gaps would read as "nothing to do"."""
    metric = maturity.measure(example_root, TODAY)["referenceCoverage"]
    assert metric.value is not None and metric.value < 1.0
    assert metric.items, "the partial mappings are what hold the level down"
    report = alignment.align(example_root)
    partial = {n.id for p in report.packs for n in p.nodes if n.status == alignment.STATUS_PARTIAL}
    assert partial and partial <= set(metric.items)


def test_the_metrics_agree_with_the_reports_they_come_from(example_root):
    """Nothing is measured twice. A level that disagreed with the gate it claims to
    summarise would be worse than no level at all."""
    from easkills import reports

    metrics = maturity.measure(example_root, TODAY)
    kpi = reports.kpi(example_root, today=TODAY)
    assert metrics["evidencedShare"].value == kpi["evidence"]["evidencedShare"]
    assert metrics["ownedShare"].value == kpi["governance"]["ownedShare"]
    assert metrics["staleShare"].value == kpi["governance"]["staleShare"]
    conformance = reports.conformance(example_root, today=TODAY)
    assert metrics["isoClausesFailed"].value == conformance["failed"]


def test_the_worked_example_is_not_all_fives(example):
    """Teaching material has to show the report working. An example scoring 5/5/5/5/5
    would demonstrate nothing about how a level is blocked, and would quietly become a
    target rather than a description."""
    levels = {r.dimension.key: r.level for r in example.results}
    assert set(levels) == {d.key for d in maturity.DIMENSIONS}
    assert min(levels.values()) < 5, "every dimension at the top teaches nothing"
    assert min(levels.values()) >= 3, "...but the example is a good repository, not a sick one"


def test_the_report_is_stable_across_runs(example_root):
    assert maturity.assess(example_root, today=TODAY).render() == maturity.assess(
        example_root, today=TODAY
    ).render()


def test_nothing_here_is_an_error(example, tmp_path):
    (tmp_path / "model" / "approved").mkdir(parents=True)
    assert example.ok and maturity.assess(tmp_path, today=TODAY).ok
