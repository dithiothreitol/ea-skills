"""The compiler must emit files a conforming ArchiMate tool can actually open."""

from pathlib import Path

import pytest
from lxml import etree

from easkills import aoef, dsl

NS = {"a": aoef.NS, "xsi": aoef.XSI}


@pytest.fixture(scope="module")
def compiled(example_root, tmp_path_factory):
    out = tmp_path_factory.mktemp("build") / "model.xml"
    return aoef.compile_model(example_root, zone="approved", out=out)


def test_passes_open_group_xsd(compiled):
    assert compiled.schema_errors == [], "\n".join(compiled.schema_errors)
    assert compiled.ok


def test_counts_match_the_source_model(compiled):
    assert compiled.elements == 20
    assert compiled.relationships == 19
    assert compiled.views == 4


def test_identifiers_are_valid_xml_ids(compiled):
    root = etree.fromstring(compiled.xml)
    for node in root.iter():
        identifier = node.get("identifier")
        if identifier is None:
            continue
        assert not identifier[0].isdigit(), f"{identifier} is not a valid NCName"
        assert " " not in identifier


def test_element_types_are_archimate_concepts(compiled):
    root = etree.fromstring(compiled.xml)
    from easkills import oracle

    for element in root.findall(".//a:elements/a:element", NS):
        concept = element.get(f"{{{aoef.XSI}}}type")
        assert concept in oracle.element_types()


def test_relationship_endpoints_resolve(compiled):
    root = etree.fromstring(compiled.xml)
    identifiers = {e.get("identifier") for e in root.findall(".//a:elements/a:element", NS)}
    relationships = root.findall(".//a:relationships/a:relationship", NS)
    assert relationships
    for relationship in relationships:
        assert relationship.get("source") in identifiers
        assert relationship.get("target") in identifiers


def test_governance_metadata_survives_into_the_exchange_file(compiled):
    """Ownership and provenance must be visible to anyone opening the model."""
    root = etree.fromstring(compiled.xml)
    definitions = {
        d.findtext("a:name", namespaces=NS): d.get("identifier")
        for d in root.findall(".//a:propertyDefinitions/a:propertyDefinition", NS)
    }
    assert {"owner", "lastReviewed", "provenance"} <= set(definitions)

    portal = root.find(".//a:element[@identifier='id-app-order-portal']", NS)
    values = {
        p.get("propertyDefinitionRef"): p.findtext("a:value", namespaces=NS)
        for p in portal.findall(".//a:property", NS)
    }
    assert values[definitions["owner"]] == "ecommerce@aurorafoods.example"
    assert values[definitions["timeDisposition"]] == "Invest"


def test_applicability_and_fact_provenance_survive_into_the_exchange_file(compiled):
    """AD-09: what a requirement binds, and which fact evidences it, must be visible
    to anyone opening the model in an ArchiMate tool."""
    root = etree.fromstring(compiled.xml)
    definitions = {
        d.findtext("a:name", namespaces=NS): d.get("identifier")
        for d in root.findall(".//a:propertyDefinitions/a:propertyDefinition", NS)
    }
    requirement = root.find(".//a:element[@identifier='id-req-po-retention']", NS)
    values = {
        p.get("propertyDefinitionRef"): p.findtext("a:value", namespaces=NS)
        for p in requirement.findall(".//a:property", NS)
    }
    assert values[definitions["appliesTo"]] == "data-order-record, app-erp-core"
    assert values[definitions["provenance"]] == "fact:fact-po-retention"


def test_assumed_elements_are_flagged_in_the_exchange_file(compiled):
    root = etree.fromstring(compiled.xml)
    definitions = {
        d.findtext("a:name", namespaces=NS): d.get("identifier")
        for d in root.findall(".//a:propertyDefinitions/a:propertyDefinition", NS)
    }
    goal = root.find(".//a:element[@identifier='id-goal-shorten-lead-time']", NS)
    values = {
        p.get("propertyDefinitionRef"): p.findtext("a:value", namespaces=NS)
        for p in goal.findall(".//a:property", NS)
    }
    assert values[definitions["assumed"]] == "true"


def test_views_have_geometry_and_derived_connections(compiled):
    root = etree.fromstring(compiled.xml)
    view = root.find(".//a:views/a:diagrams/a:view[@identifier='id-view-layered-overview']", NS)
    assert view is not None
    nodes = view.findall("a:node", NS)
    assert len(nodes) == 14
    for node in nodes:
        for attribute in ("x", "y", "w", "h"):
            assert int(node.get(attribute)) >= 0
    connections = view.findall("a:connection", NS)
    assert connections, "connections should be derived from the model, not authored"
    node_ids = {n.get("identifier") for n in nodes}
    for connection in connections:
        assert connection.get("source") in node_ids
        assert connection.get("target") in node_ids


def test_layered_layout_orders_layers_top_down(compiled):
    root = etree.fromstring(compiled.xml)
    view = root.find(".//a:views/a:diagrams/a:view[@identifier='id-view-layered-overview']", NS)
    y_of = {n.get("elementRef"): int(n.get("y")) for n in view.findall("a:node", NS)}
    assert y_of["id-cap-order-management"] < y_of["id-process-order-fulfilment"]
    assert y_of["id-process-order-fulfilment"] < y_of["id-app-erp-core"]
    assert y_of["id-app-erp-core"] < y_of["id-node-erp-app-server"]


def test_organizations_group_elements_by_layer(compiled):
    root = etree.fromstring(compiled.xml)
    labels = [item.findtext("a:label", namespaces=NS) for item in root.findall("a:organizations/a:item", NS)]
    assert "Business" in labels and "Application" in labels and "Technology" in labels


def test_output_is_byte_stable(example_root, tmp_path):
    """Re-running the compiler must produce identical bytes: diffs mean real changes."""
    first = aoef.compile_model(example_root, zone="approved", out=tmp_path / "a.xml")
    second = aoef.compile_model(example_root, zone="approved", out=tmp_path / "b.xml")
    assert first.xml == second.xml


def test_compile_refuses_unresolved_endpoints(broken_root):
    model, _documents, _config = dsl.load(broken_root, "approved")
    with pytest.raises(aoef.CompileError):
        aoef.build_tree(model)


def test_written_file_matches_returned_bytes(compiled):
    assert Path(compiled.path).read_bytes() == compiled.xml
