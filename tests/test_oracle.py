"""The oracle is the foundation of every semantic check: guard it explicitly."""

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


def test_layer_lookup():
    assert oracle.layer_of("Capability") == "Strategy"
    assert oracle.layer_of("BusinessProcess") == "Business"
    assert oracle.layer_of("ApplicationComponent") == "Application"
    assert oracle.layer_of("Node") == "Technology"
    assert oracle.layer_of("Facility") == "Physical"
    assert oracle.layer_of("Goal") == "Motivation"
    assert oracle.layer_of("Plateau") == "Implementation"
