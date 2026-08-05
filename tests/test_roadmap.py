"""The Implementation & Migration layer read as a plan.

Nothing here invents a concept: `Plateau`, `Gap`, `WorkPackage` and `Deliverable` come
from the same oracle-generated enumeration as everything else, and validated the day
the schema was built. What is added is the date a plateau needs to be a *step* rather
than a state, and the rules that make the plan answerable -- above all `PLAT005`, which
is the one that catches a portfolio decision nobody scheduled.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from easkills import cli, docgen, dsl, genschema, reports, validate

TODAY = date(2026, 7, 30)


def _repo(tmp_path: Path, elements: list[dict], relationships: list[dict] | None = None) -> Path:
    target = tmp_path / "model" / "approved"
    target.mkdir(parents=True)
    (target / "model.yaml").write_text(
        yaml.safe_dump({"elements": elements, "relationships": relationships or []}, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )
    return tmp_path


def _plateau(plateau_id: str, plateau_date: str | None = "2027-01-01") -> dict:
    item = {
        "id": plateau_id,
        "type": "Plateau",
        "name": plateau_id.replace("-", " ").title(),
        "owner": "ea@example.test",
        "lastReviewed": "2026-07-01",
        "assumed": True,
        "rationale": "fixture",
    }
    if plateau_date is not None:
        item["properties"] = {"plateauDate": plateau_date}
    return item


def _app(app_id: str, disposition: str | None = None) -> dict:
    item = {
        "id": app_id,
        "type": "ApplicationComponent",
        "name": app_id.replace("-", " ").title(),
        "owner": "it@example.test",
        "lastReviewed": "2026-07-01",
        "assumed": True,
        "rationale": "fixture",
    }
    if disposition:
        item["properties"] = {"timeDisposition": disposition}
    return item


def _codes(root: Path, today: date = TODAY) -> set[str]:
    model, _documents, _config = dsl.load(root, "approved")
    return {f.code for f in validate.check_roadmap(model, today=today)}


# ------------------------------------------------------------------ nothing invented


def test_the_migration_concepts_come_from_the_oracle():
    """If these ever leave the enumeration, the roadmap stops being ArchiMate."""
    element_types = set(genschema.build_schema()["$defs"]["element"]["properties"]["type"]["enum"])
    assert {"Plateau", "Gap", "WorkPackage", "Deliverable"} <= element_types


def test_plateau_date_is_a_constrained_property():
    """An interpreted key carries a vocabulary -- the timeDisposition lesson."""
    properties = genschema.build_schema()["$defs"]["element"]["properties"]["properties"]
    assert properties["properties"]["plateauDate"]["pattern"] == genschema.DATE_PATTERN


# ------------------------------------------------------------------------- the rules


def test_a_plateau_without_a_date_is_an_error(tmp_path):
    assert "PLAT001" in _codes(_repo(tmp_path, [_plateau("p", None)]))


def test_two_plateaus_at_the_same_instant_are_an_error(tmp_path):
    root = _repo(tmp_path, [_plateau("p-a", "2027-01-01"), _plateau("p-b", "2027-01-01")])
    codes = _codes(root)
    assert "PLAT002" in codes
    model, _d, _c = dsl.load(root, "approved")
    reported = [f for f in validate.check_roadmap(model, today=TODAY) if f.code == "PLAT002"]
    assert len(reported) == 1, "reported once, against the second plateau -- not twice"


def test_an_impossible_plateau_date_is_an_error_and_not_a_crash(tmp_path):
    root = _repo(tmp_path, [_plateau("p", "2027-03-32")])
    assert "PLAT003" in _codes(root)
    assert "PLAT001" not in _codes(root), "the date exists; it is just not a date"


def test_a_gap_associated_with_no_plateau_warns(tmp_path):
    elements = [
        {
            "id": "gap-x",
            "type": "Gap",
            "name": "Floating Gap",
            "owner": "ea@example.test",
            "lastReviewed": "2026-07-01",
            "assumed": True,
            "rationale": "fixture",
        }
    ]
    assert "PLAT004" in _codes(_repo(tmp_path, elements))


def test_a_gap_that_names_its_plateau_is_clean(tmp_path):
    elements = [
        _plateau("p"),
        {
            "id": "gap-x",
            "type": "Gap",
            "name": "Anchored Gap",
            "owner": "ea@example.test",
            "lastReviewed": "2026-07-01",
            "assumed": True,
            "rationale": "fixture",
        },
    ]
    relationships = [{"id": "r", "type": "Association", "source": "gap-x", "target": "p"}]
    assert "PLAT004" not in _codes(_repo(tmp_path, elements, relationships))


def test_a_decided_disposition_with_no_plateau_warns(tmp_path):
    """The flagship: the portfolio decision is taken and nothing carries it."""
    root = _repo(tmp_path, [_plateau("p"), _app("legacy", "Eliminate")])
    assert "PLAT005" in _codes(root)


def test_the_same_disposition_inside_a_plateau_is_clean(tmp_path):
    root = _repo(
        tmp_path,
        [_plateau("p"), _app("legacy", "Eliminate")],
        [{"id": "r", "type": "Aggregation", "source": "p", "target": "legacy"}],
    )
    assert "PLAT005" not in _codes(root)


def test_no_roadmap_at_all_is_not_a_failing_roadmap(tmp_path):
    """A repository that has not started planning has no roadmap; it is not breaking
    one. `kpi` and `debt` are where an absent plan shows up."""
    assert _codes(_repo(tmp_path, [_app("legacy", "Eliminate")])) == set()


def test_a_roadmap_entirely_in_the_past_warns(tmp_path):
    root = _repo(tmp_path, [_plateau("p-old", "2020-01-01")])
    assert "PLAT006" in _codes(root)
    assert "PLAT006" not in _codes(root, today=date(2019, 1, 1))


def test_one_future_plateau_keeps_the_roadmap_alive(tmp_path):
    root = _repo(tmp_path, [_plateau("p-old", "2020-01-01"), _plateau("p-next", "2027-01-01")])
    assert "PLAT006" not in _codes(root)


def test_a_work_package_delivering_nothing_warns(tmp_path):
    elements = [
        {
            "id": "wp",
            "type": "WorkPackage",
            "name": "Project",
            "owner": "pmo@example.test",
            "lastReviewed": "2026-07-01",
            "assumed": True,
            "rationale": "fixture",
        }
    ]
    assert "PLAT007" in _codes(_repo(tmp_path, elements))


# --------------------------------------------------------------------------- report


def test_roadmap_report_on_the_example(example_root):
    data = reports.roadmap(example_root, today=TODAY)
    assert [row["id"] for row in data["plateaus"]] == [
        "plateau-2026-baseline",
        "plateau-2028-wms-cloud",
    ], "ordered by date, not by file order"
    assert data["plateaus"][0]["state"] == "reached"
    assert data["plateaus"][1]["state"] == "planned"
    assert data["plateaus"][1]["includes"] == ["app-wms"]
    assert [g["id"] for g in data["gaps"]] == ["gap-wms-hosting"]
    assert data["unscheduledIntent"] == [], "the example's only Migrate is in a plateau"


def test_undated_plateaus_sort_last_rather_than_inventing_a_position(tmp_path):
    root = _repo(tmp_path, [_plateau("p-dated", "2027-01-01"), _plateau("p-undated", None)])
    data = reports.roadmap(root, today=TODAY)
    assert [row["id"] for row in data["plateaus"]] == ["p-dated", "p-undated"]
    assert data["plateaus"][-1]["state"] == "unscheduled"


def test_the_report_names_unscheduled_intent(tmp_path):
    root = _repo(tmp_path, [_plateau("p"), _app("legacy", "Eliminate")])
    data = reports.roadmap(root, today=TODAY)
    assert [row["id"] for row in data["unscheduledIntent"]] == ["legacy"]
    assert "Intent with no plan" in reports.render_roadmap(data)


def test_an_empty_roadmap_says_so(tmp_path):
    rendered = reports.render_roadmap(reports.roadmap(_repo(tmp_path, []), today=TODAY))
    assert "No plateaus" in rendered


# ----------------------------------------------------------------- the description


def test_the_description_records_the_roadmap(example_root):
    markdown = docgen.build_markdown(dsl.load(example_root, "approved")[0])
    section = markdown.split("## 9. Roadmap", 1)[1]
    assert "2028-06-30" in section and "WMS In The Cloud" in section
    assert "WMS Hosting Gap" in section


def test_a_model_with_no_plan_says_that_too(tmp_path):
    root = _repo(tmp_path, [_app("only-app")])
    markdown = docgen.build_markdown(dsl.load(root, "approved")[0])
    assert "not where it is going" in markdown.split("## 9. Roadmap", 1)[1]


# ------------------------------------------------------------------------------ CLI


def test_cli_roadmap(example_root, capsys):
    assert cli.main(["roadmap", "--root", str(example_root), "--as-of", "2026-07-30"]) == 0
    out = capsys.readouterr().out
    assert "2 plateau(s), 1 gap(s)" in out
    assert "[reached]" in out and "[planned]" in out


def test_cli_roadmap_json(example_root, tmp_path, capsys):
    target = tmp_path / "roadmap.json"
    assert cli.main(["roadmap", "--root", str(example_root), "--json", str(target)]) == 0
    capsys.readouterr()
    import json

    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["counts"]["plateaus"] == 2 and data["counts"]["gaps"] == 1
