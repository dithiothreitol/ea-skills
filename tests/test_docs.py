"""Rendering and the architecture description must be deterministic, self-contained
and faithful to the model -- and the committed example outputs must stay fresh."""

import shutil
from datetime import date
from pathlib import Path

from lxml import etree

from easkills import cli, docgen, dsl, render, reports, validate


def _model(example_root):
    model, _docs, _config = dsl.load(example_root, "approved")
    return model


def test_a_mistyped_time_disposition_is_caught_and_never_silently_dropped(tmp_path, example_root):
    """One vocabulary, enforced at the gate and honest in both reports.

    `timeDisposition: tolerate` used to validate clean, count as 100% TIME-classified in
    the KPI, and disappear from the architecture description's quadrant line -- taking
    the whole application with it, because the line iterated a fixed vocabulary.
    """
    repo = tmp_path / "repo"
    shutil.copytree(example_root, repo)
    application = repo / "model" / "approved" / "application.yaml"
    application.write_text(
        application.read_text(encoding="utf-8").replace(
            "timeDisposition: Tolerate", "timeDisposition: tolerate"
        ),
        encoding="utf-8",
        newline="\n",
    )
    today = date(2026, 7, 30)

    # 1. the gate rejects the value
    assert "SCHEMA001" in {f.code for f in validate.validate(repo, today=today).errors}
    # 2. the KPI does not count it as classified
    assert reports.kpi(repo, today=today)["portfolio"]["timeClassifiedShare"] < 1.0
    # 3. and if the document is generated anyway, the application is still named
    docgen.generate(repo)
    text = (repo / "docs" / "architecture-description.md").read_text(encoding="utf-8")
    quadrants = next(line for line in text.splitlines() if line.startswith("**TIME quadrants:**"))
    assert "ERP Core" in quadrants
    assert "Not a TIME quadrant" in text


# ------------------------------------------------------------------------- rendering


def test_every_view_renders_to_valid_svg(example_root):
    model = _model(example_root)
    for view in model.views.values():
        svg = render.render_view(model, view)
        root = etree.fromstring(svg.encode("utf-8"))
        assert root.tag.endswith("svg")


def test_svg_shows_every_included_element(example_root):
    model = _model(example_root)
    view = model.views["capability-realization"]
    svg = render.render_view(model, view)
    for element_id in view.include:
        assert model.elements[element_id].name.split()[0] in svg or element_id in svg


def test_svg_draws_derived_connections_and_applicability(example_root):
    model = _model(example_root)
    svg = render.render_view(model, model.views["retention-obligations"])
    assert "applies to: req-po-retention" in svg
    assert "marker-end='url(#arrow)'" in svg  # at least one real relationship drawn


def test_rendering_is_byte_stable(example_root):
    model = _model(example_root)
    view = model.views["layered-overview"]
    assert render.render_view(model, view) == render.render_view(model, view)


def test_render_all_writes_one_file_per_view(example_root, tmp_path):
    result = render.render_all(example_root, out_dir=tmp_path)
    assert len(result.views) == 4
    for view_id, path in result.views:
        assert path.exists()
        assert path.name == f"{view_id}.svg"


# ------------------------------------------------------------------ the description


def test_description_has_the_iso_42010_sections(example_root):
    markdown = docgen.build_markdown(_model(example_root))
    for heading in (
        "## 1. Stakeholders and concerns",
        "## 2. Concern coverage",
        "## 3. Views",
        "## 4. Application portfolio",
        "## 5. Capability support",
        "## 6. Assumptions and open questions",
    ):
        assert heading in markdown


def test_description_maps_concerns_to_stakeholders_and_views(example_root):
    markdown = docgen.build_markdown(_model(example_root))
    assert "How exposed is order capture to a single point of failure?" in markdown
    assert "CIO, Head of Operations" in markdown
    assert "Layered Overview" in markdown


def test_description_surfaces_assumptions_as_open_questions(example_root):
    markdown = docgen.build_markdown(_model(example_root))
    assert "Shorten Order-to-Delivery Lead Time" in markdown
    assert "declared assumptions" in markdown


def test_description_shows_time_quadrants(example_root):
    markdown = docgen.build_markdown(_model(example_root))
    assert "**TIME quadrants:** Invest: Order Portal" in markdown


def test_as_of_date_comes_from_the_model_not_the_clock(example_root):
    markdown = docgen.build_markdown(_model(example_root))
    assert "**As of:** 2026-07-15" in markdown


def test_description_is_byte_stable(example_root):
    model = _model(example_root)
    assert docgen.build_markdown(model) == docgen.build_markdown(model)


def test_committed_example_docs_are_fresh(example_root):
    """The generated description and SVGs are committed; a change to the model or the
    generators without regeneration must fail here (same contract as the schemas)."""
    committed = (example_root / "docs" / "architecture-description.md").read_text(encoding="utf-8")
    assert committed == docgen.build_markdown(_model(example_root)), "run 'python -m easkills docs --root eval/example'"
    model = _model(example_root)
    for view_id, view in model.views.items():
        on_disk = (example_root / "docs" / "views" / f"{view_id}.svg").read_text(encoding="utf-8")
        assert on_disk == render.render_view(model, view), "run 'python -m easkills docs --root eval/example'"


# ------------------------------------------------------------------------------- CLI


def test_cli_docs_generates_description_and_views(example_root, tmp_path, capsys):
    out = tmp_path / "ad.md"
    assert cli.main(["docs", "--root", str(example_root), "--out", str(out)]) == 0
    assert "Rendered 4 view(s)" in capsys.readouterr().out
    assert out.exists()


def test_cli_docs_refuses_a_broken_model(broken_root, tmp_path, capsys):
    out = tmp_path / "ad.md"
    assert cli.main(["docs", "--root", str(broken_root), "--out", str(out)]) == 1
    assert "Refusing to document" in capsys.readouterr().out
    assert not out.exists()


def test_cli_render_writes_svgs(example_root, tmp_path, capsys):
    assert cli.main(["render", "--root", str(example_root), "--out", str(tmp_path)]) == 0
    assert len(list(tmp_path.glob("*.svg"))) == 4
    capsys.readouterr()
