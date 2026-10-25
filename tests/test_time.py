"""Phase 8.5, time: KPI snapshots, the trend across them, and the two diffs.

Snapshots are records (D9): the date is explicit, a re-run of an unchanged model is a
no-op, and a changed model cannot rewrite a past date. The trend reads only what was
committed. ``diff --ref`` reads git and must leave the working tree exactly as it found
it; ``diff --plateau`` reads the same membership ``roadmap`` reads.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from easkills import cli, diff, genschema, reports, timeline

REPO_ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-07-30"


@pytest.fixture
def repo(tmp_path, example_root) -> Path:
    target = tmp_path / "repo"
    shutil.copytree(example_root, target)
    return target


def _tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


# ------------------------------------------------------------------------ snapshots


@pytest.mark.parametrize(
    "fixture", ["eval/example", "eval/fixtures/finco", "eval/fixtures/secco", "eval/fixtures/broken", "template"]
)
def test_kpi_output_is_always_a_valid_snapshot(fixture):
    """The schema and ``kpi`` must not drift apart: a snapshot that ``trend`` later
    refuses would be a record nobody can read. Every repository shape is checked,
    including one that keeps clarification questions and one that is empty."""
    from datetime import date

    data = reports.kpi(REPO_ROOT / fixture, today=date(2026, 7, 30))
    errors = list(Draft202012Validator(genschema.build_metrics_schema()).iter_errors(data))
    assert not errors, errors[0].message


def test_the_metrics_schema_is_registered_and_committed():
    assert (genschema.METRICS_SCHEMA_PATH, genschema.build_metrics_schema) in genschema.SCHEMAS
    committed = json.loads(genschema.METRICS_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert committed == genschema.build_metrics_schema()


def test_a_snapshot_needs_a_date_because_the_name_is_the_date(repo):
    assert cli.main(["kpi", "--root", str(repo), "--snapshot"]) == 1
    assert not (repo / timeline.METRICS_DIR).exists()


def test_a_snapshot_is_the_kpi_json_and_a_rerun_is_a_no_op(repo, capsys):
    assert cli.main(["kpi", "--root", str(repo), "--as-of", AS_OF, "--snapshot"]) == 0
    path = repo / timeline.METRICS_DIR / f"{AS_OF}.json"
    from datetime import date

    assert json.loads(path.read_text(encoding="utf-8")) == reports.kpi(repo, today=date(2026, 7, 30))
    assert path.read_bytes().endswith(b"\n") and b"\r" not in path.read_bytes()
    before = path.read_bytes()
    assert cli.main(["kpi", "--root", str(repo), "--as-of", AS_OF, "--snapshot"]) == 0
    assert "unchanged" in capsys.readouterr().out
    assert path.read_bytes() == before


def test_a_changed_model_cannot_rewrite_a_past_date(repo):
    assert cli.main(["kpi", "--root", str(repo), "--as-of", AS_OF, "--snapshot"]) == 0
    path = repo / timeline.METRICS_DIR / f"{AS_OF}.json"
    before = path.read_bytes()
    (repo / "model" / "approved" / "migration.yaml").unlink()
    assert cli.main(["kpi", "--root", str(repo), "--as-of", AS_OF, "--snapshot"]) == 1
    assert path.read_bytes() == before, "the record of that date is untouched"


# ---------------------------------------------------------------------------- trend


def _snapshot(repo: Path, day: str, **changes) -> None:
    from datetime import date

    data = reports.kpi(repo, today=date.fromisoformat(day))
    for dotted, value in changes.items():
        section, key = dotted.split("__")
        data[section][key] = value
    timeline.write_snapshot(repo, data)


def test_no_snapshot_is_a_message_not_a_failure(repo, capsys):
    assert cli.main(["trend", "--root", str(repo)]) == 0
    assert "kpi --snapshot" in capsys.readouterr().out


def test_one_snapshot_is_a_point_not_a_trend(repo, capsys):
    _snapshot(repo, "2026-06-30")
    assert cli.main(["trend", "--root", str(repo), "--strict"]) == 0
    assert "point, not a trend" in capsys.readouterr().out


def test_the_trend_names_what_regressed_and_strict_gates_on_it(repo, capsys):
    _snapshot(repo, "2026-06-30", evidence__evidencedShare=1.0, quality__orphans=[])
    _snapshot(repo, "2026-07-30", quality__orphans=["app-x", "app-y"])
    data = timeline.trend(repo)
    regressed = {item["key"] for item in data["regressions"]}
    assert {"evidenced", "orphans"} <= regressed
    assert data["snapshots"] == ["2026-06-30", "2026-07-30"]
    assert cli.main(["trend", "--root", str(repo)]) == 0
    assert cli.main(["trend", "--root", str(repo), "--strict"]) == 1
    out = capsys.readouterr().out
    assert "Regressed since the previous snapshot" in out and "Orphans: 0" in out


def test_growth_and_open_waivers_are_never_called_regressions(repo):
    """A bigger model is not a worse one, and a waiver is a legitimate record: marking
    either as a regression would reward deleting things to clear a report."""
    _snapshot(repo, "2026-06-30", size__elements=5, governance__openDispensations=0)
    _snapshot(repo, "2026-07-30", governance__openDispensations=4)
    regressed = {item["key"] for item in timeline.trend(repo)["regressions"]}
    assert not regressed & {"elements", "relationships", "dispensations", "open-requests", "open-questions"}


def test_an_unreadable_snapshot_is_named_and_fails(repo, capsys):
    directory = repo / timeline.METRICS_DIR
    directory.mkdir(parents=True)
    (directory / "2026-06-30.json").write_text("{not json", encoding="utf-8")
    (directory / "2026-07-01.json").write_text(json.dumps({"asOf": "2026-07-01"}), encoding="utf-8")
    _snapshot(repo, "2026-07-30")
    renamed = directory / "2026-08-01.json"
    shutil.copy(directory / "2026-07-30.json", renamed)
    data = timeline.trend(repo)
    files = {error["file"].rsplit("/", 1)[-1] for error in data["errors"]}
    assert files == {"2026-06-30.json", "2026-07-01.json", "2026-08-01.json"}
    assert any("the name is the date" in error["message"] for error in data["errors"])
    assert cli.main(["trend", "--root", str(repo)]) == 1


def test_last_limits_the_columns_not_the_comparison(repo):
    for day in ("2026-05-30", "2026-06-30", "2026-07-30"):
        _snapshot(repo, day)
    data = timeline.trend(repo, last=2)
    assert data["snapshots"] == ["2026-06-30", "2026-07-30"] and data["total"] == 3
    assert all(len(row["values"]) == 2 for row in data["metrics"])


# --------------------------------------------------------------------- diff plateau


ROADMAP = """
elements:
  - {id: plateau-now, type: Plateau, name: Now, properties: {plateauDate: 2026-01-01}, assumed: true, rationale: test}
  - {id: plateau-next, type: Plateau, name: Next, properties: {plateauDate: 2027-01-01}, assumed: true, rationale: test}
  - {id: gap-move, type: Gap, name: Move, assumed: true, rationale: test}
relationships:
  - {id: r1, type: Aggregation, source: plateau-now, target: app-wms, assumed: true, rationale: test}
  - {id: r2, type: Aggregation, source: plateau-now, target: app-erp-core, assumed: true, rationale: test}
  - {id: r3, type: Composition, source: plateau-next, target: app-erp-core, assumed: true, rationale: test}
  - {id: r4, type: Aggregation, source: plateau-next, target: app-order-portal, assumed: true, rationale: test}
  - {id: r5, type: Association, source: gap-move, target: plateau-now, assumed: true, rationale: test}
"""


def test_plateau_diff_reads_the_roadmaps_membership(repo):
    (repo / "model" / "approved" / "roadmap-test.yaml").write_text(ROADMAP, encoding="utf-8")
    data = diff.plateaus(repo, "plateau-now", "plateau-next")
    assert [r["id"] for r in data["enters"]] == ["app-order-portal"]
    assert [r["id"] for r in data["leaves"]] == ["app-wms"]
    assert [r["id"] for r in data["stays"]] == ["app-erp-core"]
    assert [(g["id"], g["plateaus"]) for g in data["gaps"]] == [("gap-move", ["plateau-now"])]
    roadmap = {row["id"]: set(row["includes"]) for row in reports.roadmap(repo)["plateaus"]}
    assert roadmap["plateau-now"] - roadmap["plateau-next"] == {"app-wms"}, "one definition of membership"


def test_plateau_diff_refuses_what_is_not_a_plateau(repo, capsys):
    assert cli.main(["diff", "--root", str(repo), "--plateau", "app-wms", "plateau-2026-baseline"]) == 1
    assert "not a Plateau" in capsys.readouterr().out
    assert cli.main(["diff", "--root", str(repo), "--plateau", "nope", "plateau-2026-baseline"]) == 1


def test_the_worked_example_says_why_its_plateaus_hold_the_same_thing(example_root, capsys):
    assert cli.main(["diff", "--root", str(example_root), "--plateau", "plateau-2026-baseline", "plateau-2028-wms-cloud"]) == 0
    out = capsys.readouterr().out
    assert "gap-wms-hosting" in out and "Both plateaus hold the same elements" in out


# -------------------------------------------------------------------------- diff ref


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *args],
        cwd=root, check=True, capture_output=True,
    )


@pytest.fixture
def history(repo) -> Path:
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")
    return repo


def test_diff_since_names_changes_by_field_and_ignores_moves(history):
    approved = history / "model" / "approved"
    application = approved / "application.yaml"
    text = application.read_text(encoding="utf-8")
    assert "lifecycle: active" in text
    application.write_text(text.replace("lifecycle: active", "lifecycle: phase-out", 1), encoding="utf-8")
    # Move a whole file: where a concept is written is not what it says.
    (approved / "technology.yaml").rename(approved / "infrastructure.yaml")
    (approved / "extra.yaml").write_text(
        "elements:\n  - {id: app-new, type: ApplicationComponent, name: New, assumed: true, rationale: test}\n",
        encoding="utf-8",
    )
    (approved / "migration.yaml").unlink()
    before = _tree(history)
    data = diff.since(history, "HEAD")
    assert _tree(history) == before, "diff --ref never touches the working tree"
    elements = data["elements"]
    assert [r["id"] for r in elements["added"]] == ["app-new"]
    assert {r["id"] for r in elements["removed"]} == {"gap-wms-hosting", "plateau-2026-baseline", "plateau-2028-wms-cloud"}
    changed = {r["id"]: r["fields"] for r in elements["changed"]}
    assert list(changed.values()) == [["properties.lifecycle"]], changed
    assert len(data["relationships"]["removed"]) == 4 and not data["relationships"]["changed"]


def test_diff_since_an_unchanged_tree_says_nothing_changed(history, capsys):
    assert cli.main(["diff", "--root", str(history), "--ref", "HEAD"]) == 0
    assert "Nothing in the approved zone changed" in capsys.readouterr().out


def test_diff_since_an_unknown_ref_is_a_refusal(history, capsys):
    assert cli.main(["diff", "--root", str(history), "--ref", "no-such-ref"]) == 1
    assert "not a commit this repository knows" in capsys.readouterr().out


def test_diff_since_outside_git_is_a_refusal(repo):
    with pytest.raises(diff.DiffError):
        diff.since(repo, "HEAD")
