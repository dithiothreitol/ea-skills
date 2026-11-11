"""The view layout (D12): nesting, hints, routing -- content-shaped, never coordinates.

What a reader of a generated view relies on is tested here as geometry: a part inside its
whole and its relationship not drawn twice; hints obeyed; no box on top of another; no
connection through a box it does not belong to; the junction's kind surviving a round
trip; and an imported view keeping its reading order while losing its pixels.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest
import yaml
from lxml import etree

from easkills import aoef, dsl, importer, layout, render, validate

REPO_ROOT = Path(__file__).resolve().parents[1]
NS = {"a": "http://www.opengroup.org/xsd/archimate/3.0/"}


def _crossings(model: dsl.Model, plan: layout.Layout) -> list[str]:
    found = []
    for relationship in model.relationships.values():
        if relationship.source not in plan.boxes or relationship.target not in plan.boxes or relationship.id in plan.nested:
            continue
        allowed = {relationship.source, relationship.target}
        allowed |= plan.ancestors(relationship.source) | plan.ancestors(relationship.target)
        points = plan.route(relationship.source, relationship.target)
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            for box in plan.boxes.values():
                if box.id in allowed:
                    continue
                if x1 == x2:
                    low, high = sorted((y1, y2))
                    hit = box.x < x1 < box.right and low < box.bottom and high > box.y
                else:
                    low, high = sorted((x1, x2))
                    hit = box.y < y1 < box.bottom and low < box.right and high > box.x
                if hit:
                    found.append(f"{relationship.id} crosses {box.id}")
    return found


def _overlaps(plan: layout.Layout) -> list[tuple[str, str]]:
    tops = [b for b in plan.boxes.values() if b.parent is None]
    return [
        (a.id, c.id)
        for i, a in enumerate(tops)
        for c in tops[i + 1 :]
        if not (a.right <= c.x or c.right <= a.x or a.bottom <= c.y or c.bottom <= a.y)
    ]


@pytest.mark.parametrize("view_id", ["layered-overview", "capability-realization", "customer-service-gap", "retention-obligations"])
def test_the_example_views_have_no_overlap_and_no_route_through_a_box(example_root, view_id):
    model, _docs, _config = dsl.load(example_root, "approved")
    plan = layout.compute(model, model.views[view_id])
    assert _overlaps(plan) == []
    assert _crossings(model, plan) == []
    for box in plan.boxes.values():
        if box.parent:
            whole = plan.boxes[box.parent]
            assert whole.x < box.x and box.right < whole.right and whole.y < box.y and box.bottom < whole.bottom


def test_a_part_is_drawn_inside_its_whole_and_not_connected_twice(example_root):
    model, _docs, _config = dsl.load(example_root, "approved")
    view = model.views["layered-overview"]
    plan = layout.compute(model, view)
    assert plan.boxes["sysswt-postgresql"].parent == "node-erp-app-server"
    assert plan.nested == {"rel-erp-server-composes-postgresql"}
    svg = render.render_view(model, view)
    assert "Composition: node-erp-app-server" not in svg
    assert "Serving: node-erp-app-server → app-erp-core" in svg, "every other relationship is still drawn"


def test_a_large_view_routes_through_free_channels(tmp_path):
    spec = importlib.util.spec_from_file_location("synth_repo", REPO_ROOT / "tools" / "synth_repo.py")
    synth = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(synth)
    root = synth.build(tmp_path / "repo", 48, view_size=40)
    model, _docs, _config = dsl.load(root, "approved")
    plan = layout.compute(model, model.views["synthetic-landscape"])
    assert len(plan.bands) == 7, "40 components wrap into rows of six"
    assert _overlaps(plan) == []
    assert _crossings(model, plan) == []


def _hinted(tmp_path: Path, layout_hints: dict) -> tuple[dsl.Model, dsl.View]:
    root = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "eval" / "example", root, ignore=shutil.ignore_patterns("docs", "build", "approvals"))
    views = root / "model" / "approved" / "views.yaml"
    data = yaml.safe_load(views.read_text(encoding="utf-8"))
    data["views"][0]["layout"] = layout_hints
    views.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    model, _docs, _config = dsl.load(root, "approved")
    return model, model.views[data["views"][0]["id"]]


def test_hints_set_the_bands_the_width_and_the_reading_order(tmp_path):
    model, view = _hinted(
        tmp_path, {"groupBy": "timeDisposition", "columns": 2, "order": ["service-order-api", "actor-b2b-customer"]}
    )
    plan = layout.compute(model, view)
    rows: dict[int, list[str]] = {}
    for box in plan.boxes.values():
        if box.parent is None:
            rows.setdefault(box.band, []).append(box.id)
    assert all(len(members) <= 2 for members in rows.values())
    dispositions = {}
    for band, members in rows.items():
        values = {model.elements[m].properties.get("timeDisposition", "") for m in members}
        assert len(values) == 1, f"band {band} mixes {values}"
        dispositions[band] = values.pop()
    ordered = [dispositions[band] for band in sorted(dispositions)]
    assert ordered.index("Invest") < ordered.index("Tolerate"), "a closed vocabulary keeps its schema order"
    assert ordered[-1] == "", "elements with no value come last"
    first_unvalued = min(b for b, v in dispositions.items() if v == "")
    row = sorted(rows[first_unvalued], key=lambda e: plan.boxes[e].x)
    assert row == ["service-order-api", "actor-b2b-customer"], "order is honoured inside a band"


def test_an_order_naming_nothing_on_the_page_is_reported(tmp_path):
    model, view = _hinted(tmp_path, {"order": ["app-wms", "not-in-this-view"]})
    findings = validate.check_views(model)
    assert [(f.code, f.concept) for f in findings] == [("VIEW001", view.id)]


@pytest.mark.parametrize(("code", "severity"), [("VIEW001", "warning"), ("VIEW002", "info")])
def test_both_view_rules_fire_on_the_negative_fixture(broken_root, code, severity):
    findings = [f for f in validate.validate(broken_root).findings if f.code == code]
    assert findings and all(f.severity == severity for f in findings)


def _junction_repo(tmp_path: Path, junction_type: str | None) -> Path:
    root = tmp_path / "repo"
    (root / "model" / "approved").mkdir(parents=True)
    (root / "ea.config.yaml").write_text("name: Junctions\n", encoding="utf-8")
    props = f"    properties:\n      junctionType: {junction_type}\n" if junction_type else ""
    (root / "model" / "approved" / "m.yaml").write_text(
        "elements:\n"
        "  - id: proc-a\n    type: BusinessProcess\n    name: Take Order\n    assumed: true\n    rationale: test\n"
        "  - id: proc-b\n    type: BusinessProcess\n    name: Ship Order\n    assumed: true\n    rationale: test\n"
        f"  - id: junction-x\n    type: Junction\n    name: Either Way\n{props}    assumed: true\n    rationale: test\n"
        "relationships:\n"
        "  - id: rel-a\n    type: Triggering\n    source: proc-a\n    target: junction-x\n    assumed: true\n    rationale: test\n"
        "  - id: rel-b\n    type: Triggering\n    source: junction-x\n    target: proc-b\n    assumed: true\n    rationale: test\n",
        encoding="utf-8",
    )
    return root


@pytest.mark.parametrize(("declared", "exchanged"), [("or", "OrJunction"), ("and", "AndJunction"), (None, "AndJunction")])
def test_a_junction_compiles_to_a_type_the_exchange_schema_knows_and_comes_back(tmp_path, declared, exchanged):
    """Found while adding nesting: the compiler emitted xsi:type="Junction", which the Open
    Group schema does not have -- any model with a junction failed XSD validation -- and the
    importer folded OrJunction into a plain Junction, so the kind did not survive a trip."""
    root = _junction_repo(tmp_path, declared)
    result = aoef.compile_model(root)
    assert result.ok, result.schema_errors
    tree = etree.fromstring(result.xml)
    node = tree.find(".//a:element[@identifier='id-junction-x']", NS)
    assert node.get("{http://www.w3.org/2001/XMLSchema-instance}type") == exchanged
    back = tmp_path / "back"
    (back / "model").mkdir(parents=True)
    importer.import_exchange(back, result.path)
    imported = yaml.safe_load((back / "model" / "staging" / "other.yaml").read_text(encoding="utf-8"))
    junction = next(e for e in imported["elements"] if e["type"] == "Junction")
    assert junction["properties"]["junctionType"] == (declared or "and")


def test_an_imported_view_keeps_its_reading_order_and_drops_its_pixels(tmp_path, example_root):
    result = aoef.compile_model(example_root, out=tmp_path / "model.xml")
    tree = etree.fromstring(result.xml)
    view = tree.find(".//a:view[@identifier='id-view-layered-overview']", NS)
    expected = [
        node.get("elementRef")
        for node in sorted(view.iter("{http://www.opengroup.org/xsd/archimate/3.0/}node"), key=lambda n: (int(n.get("y")), int(n.get("x"))))
    ]
    target = tmp_path / "repo"
    (target / "model").mkdir(parents=True)
    importer.import_exchange(target, tmp_path / "model.xml", ids="identifiers")
    views = yaml.safe_load((target / "model" / "staging" / "views.yaml").read_text(encoding="utf-8"))["views"]
    overview = next(v for v in views if v["name"] == "Layered Overview")
    order = overview["layout"]["order"]
    assert [f"id-{e}" for e in order] == expected or order == [e.removeprefix("id-") for e in expected]
    assert "x" not in yaml.safe_dump(overview), "no coordinate survives the import"


def test_a_route_in_the_last_band_stays_on_the_canvas(example_root):
    """Found by the session review: a same-band connection runs in the gutter below its
    band, and the canvas used to end before the last band's gutter."""
    model, _docs, _config = dsl.load(example_root, "approved")
    for view in model.views.values():
        plan = layout.compute(model, view)
        for relationship in model.relationships.values():
            if relationship.source in plan.boxes and relationship.target in plan.boxes:
                for _x, y in plan.route(relationship.source, relationship.target):
                    assert 0 <= y <= plan.height, (view.id, relationship.id, y, plan.height)
