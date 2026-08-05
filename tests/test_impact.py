"""Impact analysis: propagation is declared, traversal is deterministic, and the
Phase H arithmetic is the only verdict the tooling is allowed to reach.

The direction tests are the load-bearing ones. A blast radius that walks relationships
in whichever direction the YAML happened to declare them is confidently wrong, and
nothing downstream would notice -- so each direction class is asserted against a model
built for it rather than against the worked example, where several types coincide.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from easkills import cli, dsl, impact, oracle

TODAY = date(2026, 7, 30)


def _repo(tmp_path: Path, elements: list[dict], relationships: list[dict] | None = None) -> Path:
    """A minimal approved model. Governance metadata is irrelevant here and omitted."""
    document = {"elements": elements, "relationships": relationships or []}
    target = tmp_path / "model" / "approved"
    target.mkdir(parents=True)
    (target / "model.yaml").write_text(
        yaml.safe_dump(document, sort_keys=False), encoding="utf-8", newline="\n"
    )
    return tmp_path


def _element(element_id: str, element_type: str = "ApplicationComponent", **extra) -> dict:
    return {
        "id": element_id,
        "type": element_type,
        "name": element_id.replace("-", " ").title(),
        "owner": "someone@example.test",
        "lastReviewed": "2026-07-01",
        "assumed": True,
        "rationale": "fixture",
        **extra,
    }


def _reached(report: impact.ImpactReport) -> set[str]:
    return {hop.element for hop in report.affected}


# ------------------------------------------------------------------ the declared table


def test_every_relationship_type_in_the_oracle_has_a_propagation_entry():
    """A future ArchiMate version must not add a type through which impact silently
    stops flowing -- the same contract the schema enumerations have with the oracle."""
    missing = sorted(set(oracle.relationship_types()) - set(impact.PROPAGATION))
    assert not missing, f"no declared propagation direction for: {missing}"
    extra = sorted(set(impact.PROPAGATION) - set(oracle.relationship_types()))
    assert not extra, f"propagation declared for types the oracle does not know: {extra}"


def test_every_propagation_entry_states_a_reason():
    for kind, (direction, reason) in impact.PROPAGATION.items():
        assert direction in {impact.FORWARD, impact.BACKWARD, impact.BOTH, impact.NONE}, kind
        assert len(reason) > 20, f"{kind}: a direction without a reason is a guess"


# ---------------------------------------------------------------------- direction


def test_serving_propagates_to_the_served(tmp_path):
    """Change the server, the served feels it -- not the other way round."""
    root = _repo(
        tmp_path,
        [_element("api", "ApplicationService"), _element("consumer")],
        [{"id": "r", "type": "Serving", "source": "api", "target": "consumer"}],
    )
    assert _reached(impact.analyse(root, "api", today=TODAY)) == {"consumer"}
    assert _reached(impact.analyse(root, "consumer", today=TODAY)) == set()


def test_access_propagates_from_the_data_to_the_accessor(tmp_path):
    """Backwards along the arrow: the reader depends on what it reads."""
    root = _repo(
        tmp_path,
        [_element("app"), _element("records", "DataObject")],
        [{"id": "r", "type": "Access", "source": "app", "target": "records"}],
    )
    assert _reached(impact.analyse(root, "records", today=TODAY)) == {"app"}
    assert _reached(impact.analyse(root, "app", today=TODAY)) == set()


def test_composition_propagates_both_ways(tmp_path):
    root = _repo(
        tmp_path,
        [_element("whole", "Node"), _element("part", "Node")],
        [{"id": "r", "type": "Composition", "source": "whole", "target": "part"}],
    )
    assert _reached(impact.analyse(root, "whole", today=TODAY)) == {"part"}
    assert _reached(impact.analyse(root, "part", today=TODAY)) == {"whole"}


def test_association_is_never_traversed_but_is_reported(tmp_path):
    """ArchiMate leaves its meaning to the modeller; inventing one would make the
    radius look thorough while being made up."""
    root = _repo(
        tmp_path,
        [_element("a"), _element("b")],
        [{"id": "r", "type": "Association", "source": "a", "target": "b"}],
    )
    report = impact.analyse(root, "a", today=TODAY)
    assert _reached(report) == set()
    assert [row["element"] for row in report.adjacent] == ["b"]


def test_applies_to_carries_impact_to_the_obligation(tmp_path):
    root = _repo(
        tmp_path,
        [
            _element("app"),
            _element("req", "Requirement", appliesTo=["app"]),
        ],
    )
    report = impact.analyse(root, "app", today=TODAY)
    assert _reached(report) == {"req"}
    assert report.obligations and report.obligations[0]["id"] == "req"


# ------------------------------------------------------------------------ traversal


def test_distance_is_the_shortest_path_and_output_is_stable(example_root):
    first = impact.analyse(example_root, "app-erp-core", today=TODAY)
    second = impact.analyse(example_root, "app-erp-core", today=TODAY)
    assert first.as_dict() == second.as_dict()
    distances = [hop.distance for hop in first.affected]
    assert distances == sorted(distances), "reported nearest-first"
    portal = next(h for h in first.affected if h.element == "app-order-portal")
    assert portal.distance == 2 and portal.frm == "service-order-api"


def test_depth_bounds_the_radius(example_root):
    unbounded = impact.analyse(example_root, "app-erp-core", today=TODAY)
    bounded = impact.analyse(example_root, "app-erp-core", depth=1, today=TODAY)
    assert len(bounded.elements) < len(unbounded.elements)
    assert all(hop.distance <= 1 for hop in bounded.affected)


def test_a_cycle_terminates(tmp_path):
    root = _repo(
        tmp_path,
        [_element("a"), _element("b")],
        [
            {"id": "r1", "type": "Serving", "source": "a", "target": "b"},
            {"id": "r2", "type": "Serving", "source": "b", "target": "a"},
        ],
    )
    report = impact.analyse(root, "a", today=TODAY)
    assert _reached(report) == {"b"}


def test_an_unknown_scope_is_refused(example_root):
    with pytest.raises(impact.ImpactError, match="not an element"):
        impact.analyse(example_root, "no-such-element", today=TODAY)


# ------------------------------------------------- the Phase H arithmetic, and its edge


def test_stakeholder_groups_are_counted_through_views_and_concerns(example_root):
    """The number ea-change-triage turns on, computed instead of eyeballed."""
    report = impact.analyse(example_root, "app-erp-core", today=TODAY)
    assert {s["id"] for s in report.stakeholders} == {
        "stakeholder-cio",
        "stakeholder-head-of-operations",
        "stakeholder-auditor",
    }
    assert report.triage_class == "re-architecting"


def test_an_element_on_no_view_touches_nobody(tmp_path):
    """And the report says so, rather than reporting 'no impact'."""
    root = _repo(tmp_path, [_element("lonely")])
    report = impact.analyse(root, "lonely", today=TODAY)
    assert report.stakeholders == [] and report.views == []
    assert report.triage_class == "incremental-or-simplification"
    rendered = impact.render(report)
    assert "gap in the views rather than an absence of impact" in rendered


def test_the_judgement_half_is_never_claimed(example_root):
    report = impact.analyse(example_root, "app-wms", today=TODAY)
    payload = report.as_dict()
    assert payload["triage"]["threshold"] == impact.REARCHITECTING_STAKEHOLDERS
    assert payload["triage"]["notEvaluated"], "the non-arithmetic test must stay declared"
    assert "judgement" in impact.render(report)


def test_the_threshold_matches_the_skill_that_documents_it(repo_root):
    skill = (repo_root / "skills" / "ea-change-triage" / "SKILL.md").read_text(encoding="utf-8")
    assert f"**≥{impact.REARCHITECTING_STAKEHOLDERS} stakeholder groups impacted**" in skill, (
        "the skill's documented threshold and the computed one must be the same number"
    )


# ---------------------------------------------------------------- governance context


def test_governance_in_the_radius_is_listed(example_root):
    report = impact.analyse(example_root, "app-erp-core", today=TODAY)
    assert [d["id"] for d in report.decisions] == ["decision-order-api-single-integration"]
    assert [d["id"] for d in report.dispensations] == ["disp-onprem-legacy"]
    assert {r["id"] for r in report.demand} >= {"req-2026-08-erp-context"}
    assert any(s["standard"] == "std-onprem-hosting" for s in report.standards)


def test_an_expired_dispensation_is_not_listed_as_cover(example_root):
    report = impact.analyse(example_root, "app-erp-core", today=date(2027, 12, 1))
    assert report.dispensations == []


def test_unowned_elements_in_the_radius_are_named(tmp_path):
    elements = [_element("a"), {**_element("b"), "owner": ""}]
    root = _repo(
        tmp_path, elements, [{"id": "r", "type": "Serving", "source": "a", "target": "b"}]
    )
    report = impact.analyse(root, "a", today=TODAY)
    assert report.unowned == ["b"]
    assert "nobody to consult" in impact.render(report)


# ------------------------------------------------------------------------------ CLI


def test_cli_impact_renders_and_writes_json(example_root, tmp_path, capsys):
    target = tmp_path / "impact.json"
    assert (
        cli.main(
            [
                "impact",
                "--root",
                str(example_root),
                "--scope",
                "app-erp-core",
                "--as-of",
                "2026-07-30",
                "--json",
                str(target),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "Blast radius" in out and "Phase H triage" in out
    import json

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["scope"] == "app-erp-core"
    assert payload["counts"]["stakeholders"] == 3
    assert payload["triage"]["mechanicalClass"] == "re-architecting"


def test_cli_impact_refuses_an_unknown_scope(example_root, capsys):
    assert cli.main(["impact", "--root", str(example_root), "--scope", "nope"]) == 1
    assert "ERROR" in capsys.readouterr().out
