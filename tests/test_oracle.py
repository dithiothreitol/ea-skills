"""The oracle is the foundation of every semantic check: guard it explicitly."""

import pytest
from lxml import etree

from easkills import oracle


def test_matrix_declares_archimate_32():
    assert oracle.matrix_version() == "3.2"


def test_checksums_match_pins():
    failures = [r.name for r in oracle.verify_checksums() if not r.ok]
    assert not failures, f"oracle files drifted from their pinned hashes: {failures}"


def test_eleven_relationship_types():
    assert oracle.relationship_types() == {
        "Access",
        "Aggregation",
        "Assignment",
        "Association",
        "Composition",
        "Flow",
        "Influence",
        "Realization",
        "Serving",
        "Specialization",
        "Triggering",
    }


def test_every_concept_has_a_layer():
    assert oracle.unmapped_layers() == frozenset()


def test_layer_assignment_covers_only_real_concepts():
    assert set(oracle.ELEMENT_LAYER) == set(oracle.element_types())


def test_pseudo_concept_is_not_an_element_type():
    assert "Relationship" not in oracle.element_types()


def test_matrix_is_directional():
    """Realization application -> business process is legal; the reverse is not."""
    assert "Realization" in oracle.allowed_relationships("ApplicationComponent", "BusinessProcess")
    assert "Realization" not in oracle.allowed_relationships("BusinessProcess", "ApplicationComponent")


def test_matrix_rejects_nonsense_pairing():
    assert "Serving" not in oracle.allowed_relationships("DataObject", "BusinessActor")
    assert "Composition" not in oracle.allowed_relationships("BusinessActor", "ApplicationComponent")


def test_matrix_permits_canonical_pairings():
    assert "Serving" in oracle.allowed_relationships("ApplicationService", "BusinessProcess")
    assert "Realization" in oracle.allowed_relationships("ApplicationComponent", "Capability")
    assert "Composition" in oracle.allowed_relationships("Node", "SystemSoftware")


def test_exchange_schema_builds_without_network():
    """The Open Group schema imports xml.xsd from w3.org by URL.

    The parser is built with ``no_network=True``, so this succeeding proves the import
    resolved from the vendored copy. A regression here would produce a validator that
    works on a developer machine and fails in a sandboxed runner.
    """
    schema = oracle.exchange_schema()
    assert isinstance(schema, etree.XMLSchema)


def test_vendored_xml_namespace_schema_is_present_and_pinned():
    assert oracle.XML_NAMESPACE_XSD.is_file()
    pinned = {r.name for r in oracle.verify_checksums()}
    assert "xml.xsd" in pinned


def test_resolver_refuses_unvendored_network_resources():
    resolver = oracle._OfflineResolver()
    with pytest.raises(oracle.OracleError, match="refusing to fetch"):
        resolver.resolve("http://example.invalid/other.xsd", None, None)


def test_layer_lookup():
    assert oracle.layer_of("Capability") == "Strategy"
    assert oracle.layer_of("BusinessProcess") == "Business"
    assert oracle.layer_of("ApplicationComponent") == "Application"
    assert oracle.layer_of("Node") == "Technology"
    assert oracle.layer_of("Facility") == "Physical"
    assert oracle.layer_of("Goal") == "Motivation"
    assert oracle.layer_of("Plateau") == "Implementation"
