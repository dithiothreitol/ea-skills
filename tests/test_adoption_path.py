"""The adoption path, walked end to end and deterministically.

Two end-to-end runs found defects no unit test could see, and both were of one kind:
**output that is correct and unusable.** The scorer compared vocabulary instead of content;
the importer wrote a single file, which made its own skill's "promote in slices" advice
unreachable. Every test at the time asserted on content, none on whether the artifacts
could be used the way the documentation says they can.

So the path itself is a test now: a repository scaffolded from `template/`, a handed-over
spreadsheet and a foreign tool's export in, a reviewed slice in `approved/` out -- with the
human's decisions from the 2026-08-05 run written down as code rather than remembered. No
network, no language model: everything here is the deterministic half, which is exactly the
half that has to keep working while the prose changes.

The fixtures live in `eval/fixtures/adoption/`.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

from easkills import cli, dsl, impact, validate

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "eval" / "fixtures" / "adoption"
EXPORT = FIXTURES / "meridian-export.xml"
HANDOVER = FIXTURES / "systems-handover.csv"
TODAY = "2026-08-06"
ILLEGAL_RELATIONSHIP = "database-host-serving-customer-record"


@dataclass
class Adoption:
    """What the walk produced, so each property gets its own named assertion."""

    root: Path
    exits: dict[str, int] = field(default_factory=dict)
    reports: dict[str, Any] = field(default_factory=dict)
    files: dict[str, list[str]] = field(default_factory=dict)


def _staging(root: Path) -> list[str]:
    return sorted(p.name for p in (root / "model" / "staging").glob("*.yaml"))


def _approved(root: Path) -> list[str]:
    return sorted(p.name for p in (root / "model" / "approved").glob("*.yaml"))


@pytest.fixture(scope="module")
def adopted(tmp_path_factory) -> Adoption:
    root = tmp_path_factory.mktemp("adoption") / "meridian-ea"
    shutil.copytree(REPO_ROOT / "template", root)
    walk = Adoption(root=root)

    # 1. The spreadsheet somebody e-mailed, turned into a citable source document.
    walk.exits["intake-csv"] = cli.main(
        ["intake-csv", "--root", str(root), "--file", str(HANDOVER)]
    )
    # 2. The incumbent tool's export, read as a staging proposal.
    walk.exits["import"] = cli.main(
        ["import", "--root", str(root), "--file", str(EXPORT), "--ids", "names"]
    )
    walk.files["afterImport"] = _staging(root)
    walk.reports["afterImport"] = validate.validate(root, zone="staging")

    # 3. The human decisions, as taken on 2026-08-05 and now recorded:
    #    (a) the matrix-illegal edge is *dropped*, not retyped -- "hosting" is not "access",
    #        and inventing a legal relationship to silence a gate is how a model starts
    #        lying. The question goes to the owner instead.
    relations = root / "model" / "staging" / "relations.yaml"
    data = yaml.safe_load(relations.read_text(encoding="utf-8"))
    data["relationships"] = [
        item for item in data["relationships"] if item["id"] != ILLEGAL_RELATIONSHIP
    ]
    relations.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    #    (b) the application owner vouches for the application slice, and only that slice.
    application = root / "model" / "staging" / "application.yaml"
    data = yaml.safe_load(application.read_text(encoding="utf-8"))
    for element in data["elements"]:
        element.setdefault("owner", "crm-team@meridian.example")
        element["lastReviewed"] = TODAY
    application.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    walk.reports["afterDecisions"] = validate.validate(root, zone="staging")

    # 4. Promote that one file. Everything else stays a proposal.
    walk.exits["promote"] = cli.main(
        ["promote", "--root", str(root), "--file", "model/staging/application.yaml"]
    )
    walk.files["approved"] = _approved(root)
    walk.files["staging"] = _staging(root)

    # 5. The first two questions a new adopter asks, in both zones.
    walk.reports["impactApproved"] = impact.analyse(root, "crm-suite", zone="approved")
    walk.reports["impactStaging"] = impact.analyse(root, "crm-suite", zone="staging")
    walk.exits["docs"] = cli.main(["docs", "--root", str(root)])
    return walk


# ------------------------------------------------------------------ every stage succeeds


def test_every_command_on_the_path_succeeds(adopted):
    assert adopted.exits == {"intake-csv": 0, "import": 0, "promote": 0, "docs": 0}


# --------------------------------------------------------------------- the spreadsheet


def test_the_spreadsheet_becomes_a_source_that_can_be_quoted(adopted):
    document = adopted.root / "facts" / "sources" / "systems-handover.md"
    text = document.read_text(encoding="utf-8")
    assert "**SHA-256:**" in text, "a quote is only traceable if the bytes are recorded"
    assert "delimiter `;`" in text, "the delimiter is a reading decision, so it is stated"
    assert "no owner named" in text, "a cell must never vanish from a document quoted from"
    assert "Route Planner" in text, "including the row IT did not know about"


# ---------------------------------------------------------- the import, and its shape


def test_the_import_is_sliceable_rather_than_one_file(adopted):
    """The defect the first adoption run found, pinned so it cannot come back."""
    assert adopted.files["afterImport"] == [
        "application.yaml",
        "business.yaml",
        "relations.yaml",
        "technology.yaml",
        "views.yaml",
    ]


def test_every_element_file_is_reference_closed(adopted):
    """*Why* that shape works, stated as the property rather than as tidiness.

    An element file has no outbound references, so it can be promoted alone; a
    relationships file references both endpoints, so it can only follow them. Splitting
    relationships by their source's layer looks tidier and fails immediately -- edges cross
    layers, so every slice dangles into a layer still in staging (`REF001`).
    """
    staging = adopted.root / "model" / "staging"
    for name in ("business.yaml", "technology.yaml"):
        data = yaml.safe_load((staging / name).read_text(encoding="utf-8"))
        assert "relationships" not in data, f"{name} must not carry edges"
        for element in data["elements"]:
            assert not element.get("appliesTo"), "an element file must reference nothing"
    edges = yaml.safe_load((staging / "relations.yaml").read_text(encoding="utf-8"))
    layers = {
        edge["id"]: {edge["source"], edge["target"]} for edge in edges["relationships"]
    }
    assert any(
        {"app-server-01", "crm-suite"} == endpoints for endpoints in layers.values()
    ), "relationships cross layers, which is why they are filed together"


def test_nothing_imported_is_trusted(adopted):
    model, _documents, _config = dsl.load(adopted.root, "staging")
    assert model.elements and all(element.assumed for element in model.elements.values())
    assert all(element.rationale for element in model.elements.values())


def test_the_gate_refuses_the_relationship_the_previous_tool_allowed(adopted):
    """Third time this rule has caught this class on live material."""
    report = adopted.reports["afterImport"]
    offending = [f for f in report.errors if f.code == "REL001"]
    assert [f.concept for f in offending] == [ILLEGAL_RELATIONSHIP]
    assert "Permitted here: Access, Association" in offending[0].message


def test_the_import_is_a_backlog_not_a_model(adopted):
    """Missing owners and dates are warnings in staging -- the adoption to-do list."""
    report = adopted.reports["afterImport"]
    assert {f.code for f in report.warnings} >= {"GOV001", "GOV002"}
    assert any(f.code == "PROV006" for f in report.findings), "every claim is listed for a human"


# ------------------------------------------------------------ the reviewed slice lands


def test_the_decisions_clear_the_gate(adopted):
    report = adopted.reports["afterDecisions"]
    assert report.ok, report.render()


def test_only_the_vouched_for_slice_is_approved(adopted):
    assert adopted.files["approved"] == ["application.yaml"]
    assert adopted.files["staging"] == [
        "business.yaml",
        "relations.yaml",
        "technology.yaml",
        "views.yaml",
    ]


def test_the_approved_zone_validates_on_its_own(adopted):
    report = validate.validate(adopted.root, zone="approved")
    assert report.ok, report.render()


# ------------------------------------------------------- what the adopter asks next


def test_a_change_triage_reads_the_proposal_not_only_the_signed_model(adopted):
    """1 element versus 2 in the same repository, on the same question.

    `impact` defaulted to `approved` because `docs` does, and the failure modes are
    opposite: a document that mixes proposals with signed content over-claims, while a
    triage that ignores proposals *under*-reports the blast radius.
    """
    approved = adopted.reports["impactApproved"]
    staging = adopted.reports["impactStaging"]
    assert approved.elements == ["crm-suite"]
    assert staging.elements == ["crm-suite", "order-intake"]
    assert staging.affected[0].kind == "Serving"
    assert staging.unowned == ["order-intake"], "and it says who cannot be consulted"


def test_the_adopter_gets_an_architecture_description_on_day_one(adopted):
    text = (adopted.root / "docs" / "architecture-description.md").read_text(encoding="utf-8")
    assert "CRM Suite" in text
    assert "Order Intake" not in text, "the approved zone only -- staging is not documentation"


def test_the_walk_is_repeatable(tmp_path):
    """Same inputs, same bytes: the path is a fixture, not a demonstration."""
    outputs = []
    for index in range(2):
        root = tmp_path / f"run{index}"
        shutil.copytree(REPO_ROOT / "template", root)
        assert cli.main(["intake-csv", "--root", str(root), "--file", str(HANDOVER)]) == 0
        assert cli.main(
            ["import", "--root", str(root), "--file", str(EXPORT), "--ids", "names"]
        ) == 0
        outputs.append(
            {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted((root / "model" / "staging").glob("*.yaml"))
            }
            | {
                "source": (root / "facts" / "sources" / "systems-handover.md").read_bytes()
            }
        )
    assert outputs[0] == outputs[1]
