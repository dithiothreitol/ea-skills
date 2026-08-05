"""Brownfield import: the exchange format read back, with the repository's rules
applied to what comes in.

Two sources of truth here. The worked example round-trips through its own compiled
exchange file, which pins the importer to `aoef.py` -- if either side drifts, the
structural-equality test says so. The foreign fixture pins the messy half: mixed-case
identifiers, unnamed junctions, vendor types, matrix-illegal relationships, nested
diagram nodes. The importer's job is to survive all of it *loudly*; judging the model
stays the gate's job."""

import shutil
from pathlib import Path

import pytest

from easkills import aoef, cli, dsl, importer, validate

REPO_ROOT = Path(__file__).resolve().parents[1]
FOREIGN = REPO_ROOT / "eval" / "fixtures" / "exchange" / "legacy-crm.xml"


@pytest.fixture()
def exported_example(example_root, tmp_path) -> Path:
    """The example compiled to exchange XML, in a fresh repository root."""
    result = aoef.compile_model(example_root, out=tmp_path / "example.xml")
    assert result.ok
    return tmp_path / "example.xml"


# ------------------------------------------------------------------------ round trip


def test_round_trip_preserves_structure(example_root, exported_example, tmp_path):
    report = importer.import_exchange(tmp_path, exported_example, ids="identifiers")
    gold, _docs, _config = dsl.load(example_root, "approved")
    imported, _docs2, _config2 = dsl.load(tmp_path, "staging")

    assert set(imported.elements) == set(gold.elements)
    for element_id, element in gold.elements.items():
        twin = imported.elements[element_id]
        assert (twin.type, twin.name) == (element.type, element.name)
        assert twin.owner == element.owner, "governance metadata survives the round trip"
        assert twin.last_reviewed == element.last_reviewed
        assert twin.properties.get("timeDisposition") == element.properties.get("timeDisposition")
    assert {(r.type, r.source, r.target) for r in imported.relationships.values()} == {
        (r.type, r.source, r.target) for r in gold.relationships.values()
    }
    assert set(imported.views) == set(gold.views)
    for view_id, view in gold.views.items():
        assert set(imported.views[view_id].include) == set(view.include)
    assert report.skipped == []


def test_everything_imported_is_assumed(exported_example, tmp_path):
    """The old tool's content arrives as claims, not evidence -- even our own."""
    importer.import_exchange(tmp_path, exported_example, ids="identifiers")
    model, _docs, _config = dsl.load(tmp_path, "staging")
    concepts = list(model.elements.values()) + list(model.relationships.values())
    assert concepts and all(c.assumed for c in concepts)
    assert all("not yet evidenced" in c.rationale for c in concepts if "Imported" in c.rationale)
    # The exporter's provenance claim is kept as information, never as verification.
    erp = model.elements["app-erp-core"]
    assert "provenance" in erp.properties and not erp.provenance


def test_names_mode_produces_readable_ids_and_remaps_applies_to(exported_example, tmp_path):
    importer.import_exchange(tmp_path, exported_example, ids="names")
    model, _docs, _config = dsl.load(tmp_path, "staging")
    assert "order-portal" in model.elements
    retention = next(e for e in model.elements.values() if "retain-purchase-orders" in e.id)
    assert set(retention.applies_to) <= set(model.elements), (
        "lifted appliesTo references must be renamed together with the elements they bind"
    )


def test_import_is_byte_stable(exported_example, tmp_path):
    target = tmp_path / "model" / "staging" / "example.yaml"
    importer.import_exchange(tmp_path, exported_example)
    first = target.read_bytes()
    target.unlink()
    importer.import_exchange(tmp_path, exported_example)
    assert target.read_bytes() == first


# -------------------------------------------------------------------- foreign export


@pytest.fixture()
def foreign_repo(tmp_path) -> tuple[Path, importer.ImportReport]:
    report = importer.import_exchange(tmp_path, FOREIGN)
    return tmp_path, report


def test_foreign_identifiers_are_slugified_and_reported(foreign_repo):
    repo, report = foreign_repo
    model, _docs, _config = dsl.load(repo, "staging")
    assert "crm-suite" in model.elements
    assert "sales-rep" in model.elements
    renames = {r["from"]: r["to"] for r in report.renamed}
    assert renames["EAID_44F0"] == "sales-rep"


def test_a_duplicate_name_gets_a_suffix_not_a_silent_merge(foreign_repo):
    repo, _report = foreign_repo
    model, _docs, _config = dsl.load(repo, "staging")
    assert "crm-suite-2" in model.elements
    assert model.elements["crm-suite-2"].name == "CRM Suite"


def test_unsupported_types_are_skipped_and_named(foreign_repo):
    repo, report = foreign_repo
    skipped = {(s["kind"], s["identifier"]) for s in report.skipped}
    assert ("element", "id-9Z") in skipped, "a vendor type is not an ArchiMate concept"
    assert ("relationship", "r3") in skipped, "a relationship loses its endpoint with it"
    model, _docs, _config = dsl.load(repo, "staging")
    assert not any(e.name == "Notes Canvas" for e in model.elements.values())


def test_junctions_are_mapped_and_an_unnamed_element_is_named(foreign_repo):
    repo, report = foreign_repo
    model, _docs, _config = dsl.load(repo, "staging")
    junction = next(e for e in model.elements.values() if e.type == "Junction")
    assert junction.name, "the DSL requires a name; the export had none"
    assert any("AndJunction" in note for note in report.notes)


def test_owner_is_lifted_and_vendor_properties_survive(foreign_repo):
    repo, _report = foreign_repo
    model, _docs, _config = dsl.load(repo, "staging")
    crm = model.elements["crm-suite"]
    assert crm.owner == "crm-team@meridian.example"
    assert crm.properties.get("vendor") == "Solterra"
    assert "owner" not in crm.properties, "lifted metadata must not exist twice"


def test_nested_view_nodes_are_walked_and_dropped_elements_excluded(foreign_repo):
    repo, report = foreign_repo
    model, _docs, _config = dsl.load(repo, "staging")
    view = model.views["sales-overview"]
    assert set(view.include) == {"crm-suite", "sales-rep"}
    assert any("geometry discarded" in note for note in report.notes)


def test_the_import_does_not_judge_but_the_gate_does(foreign_repo):
    """The matrix-illegal relationship is imported as-is; REL001 is validate's line."""
    repo, report = foreign_repo
    assert "r2" not in {s["identifier"] for s in report.skipped}
    findings = validate.validate(repo, zone="staging")
    rel001 = [f for f in findings.findings if f.code == "REL001"]
    assert rel001, "the previous tool allowed it; the 3.2 matrix does not"


def test_imported_staging_has_migration_debt_as_warnings(foreign_repo):
    """No owners on most elements, no review dates anywhere: staging says so and does
    not block -- that list *is* the adoption backlog."""
    repo, _report = foreign_repo
    findings = validate.validate(repo, zone="staging")
    codes = {f.code for f in findings.warnings}
    assert {"GOV001", "GOV002"} <= codes


# -------------------------------------------------------------------------- refusals


def test_import_never_overwrites(exported_example, tmp_path):
    importer.import_exchange(tmp_path, exported_example)
    with pytest.raises(importer.ImportRefusal, match="never overwrites"):
        importer.import_exchange(tmp_path, exported_example)


def test_unparseable_xml_is_refused(tmp_path):
    source = tmp_path / "broken.xml"
    source.write_text("<model><unclosed>", encoding="utf-8")
    with pytest.raises(importer.ImportRefusal, match="not parseable"):
        importer.import_exchange(tmp_path, source)


def test_a_non_model_document_is_refused(tmp_path):
    source = tmp_path / "other.xml"
    source.write_text('<?xml version="1.0"?><catalog/>', encoding="utf-8")
    with pytest.raises(importer.ImportRefusal, match="expected <model>"):
        importer.import_exchange(tmp_path, source)


def test_an_empty_model_is_refused(tmp_path):
    source = tmp_path / "empty.xml"
    source.write_text(
        '<?xml version="1.0"?><model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"/>',
        encoding="utf-8",
    )
    with pytest.raises(importer.ImportRefusal, match="no importable content"):
        importer.import_exchange(tmp_path, source)


def test_a_missing_source_is_refused(tmp_path):
    with pytest.raises(importer.ImportRefusal, match="does not exist"):
        importer.import_exchange(tmp_path, tmp_path / "nope.xml")


# ------------------------------------------------------------------------------- CLI


def test_cli_import_reports_and_writes_json(exported_example, tmp_path, capsys):
    target_json = tmp_path / "report.json"
    assert (
        cli.main(
            [
                "import",
                "--root",
                str(tmp_path),
                "--file",
                str(exported_example),
                "--json",
                str(target_json),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "Imported 17 element(s), 15 relationship(s), 4 view(s)" in out
    assert "staging proposal" in out
    import json

    data = json.loads(target_json.read_text(encoding="utf-8"))
    assert data["counts"] == {"elements": 17, "relationships": 15, "views": 4}
    assert data["sourceSha256"]


def test_cli_import_refusal_exits_one(tmp_path, capsys):
    assert cli.main(["import", "--root", str(tmp_path), "--file", str(tmp_path / "no.xml")]) == 1
    assert "ERROR" in capsys.readouterr().out
