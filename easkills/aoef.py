"""Compile the YAML DSL into The Open Group ArchiMate Model Exchange File Format.

The exchange file is a build artifact, never edited by hand. It is validated against
the vendored Open Group XSDs on every build, so a model that cannot be opened by a
conforming tool fails the pipeline instead of reaching a reviewer.

Views declare *content* (which elements to show); geometry is computed here by a
deterministic layered grid. Authors and language models never hand-place
coordinates -- that keeps diffs meaningful and layout reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from . import dsl, oracle

NS = oracle.AOEF_NS
XSI = oracle.XSI_NS
NSMAP = {None: NS, "xsi": XSI}
SCHEMA_LOCATION = (
    "http://www.opengroup.org/xsd/archimate/3.0/ "
    "http://www.opengroup.org/xsd/archimate/3.1/archimate3_Diagram.xsd"
)

# Deterministic grid layout parameters (pixels, matching Archi's default node size).
NODE_WIDTH = 145
NODE_HEIGHT = 60
GAP_X = 25
GAP_Y = 45
MARGIN = 20
COLUMNS = 6


class CompileError(RuntimeError):
    pass


@dataclass
class CompileResult:
    path: Path
    xml: bytes
    elements: int
    relationships: int
    views: int
    schema_errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.schema_errors


def _qn(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def concept_id(slug: str) -> str:
    """DSL slugs become xsd:ID values; the prefix guarantees a valid NCName."""
    return f"id-{slug}"


def _property_definition_id(key: str) -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in key).strip("-").lower()
    return f"propid-{safe or 'prop'}"


def _append_text(parent: etree._Element, tag: str, text: str) -> None:
    if not text:
        return
    node = etree.SubElement(parent, _qn(tag))
    node.text = text


def _append_properties(parent: etree._Element, properties: dict[str, str], definitions: dict[str, str]) -> None:
    if not properties:
        return
    container = etree.SubElement(parent, _qn("properties"))
    for key in sorted(properties):
        prop = etree.SubElement(container, _qn("property"))
        prop.set("propertyDefinitionRef", definitions[key])
        value = etree.SubElement(prop, _qn("value"))
        value.text = properties[key]


def _governance_properties(concept: dsl.Concept) -> dict[str, str]:
    """Surface governance and traceability metadata as model properties.

    They must survive into any ArchiMate tool, otherwise ownership and provenance
    exist only in the source YAML and are invisible to the people reviewing views.
    """
    props = dict(concept.properties)
    if concept.owner:
        props.setdefault("owner", concept.owner)
    if concept.last_reviewed:
        props.setdefault("lastReviewed", concept.last_reviewed)
    if concept.assumed:
        props.setdefault("assumed", "true")
        if concept.rationale:
            props.setdefault("assumptionRationale", concept.rationale)
    if concept.provenance:
        props.setdefault(
            "provenance",
            "; ".join(f"fact:{p.fact}" if p.fact else p.file for p in concept.provenance),
        )
    applies_to = getattr(concept, "applies_to", None)
    if applies_to:
        props.setdefault("appliesTo", ", ".join(applies_to))
    return props


def _layout(model: dsl.Model, element_ids: list[str]) -> dict[str, tuple[int, int]]:
    """Layered grid: one band per ArchiMate layer, top to bottom."""
    by_layer: dict[str, list[str]] = {}
    for element_id in element_ids:
        element = model.elements[element_id]
        by_layer.setdefault(oracle.layer_of(element.type), []).append(element_id)

    positions: dict[str, tuple[int, int]] = {}
    y = MARGIN
    for layer in oracle.LAYER_ORDER:
        members = sorted(by_layer.get(layer, []))
        if not members:
            continue
        for index, element_id in enumerate(members):
            row, column = divmod(index, COLUMNS)
            x = MARGIN + column * (NODE_WIDTH + GAP_X)
            positions[element_id] = (x, y + row * (NODE_HEIGHT + GAP_Y))
        rows = (len(members) + COLUMNS - 1) // COLUMNS
        y += rows * (NODE_HEIGHT + GAP_Y) + GAP_Y
    return positions


def build_tree(model: dsl.Model) -> etree._ElementTree:
    root = etree.Element(_qn("model"), nsmap=NSMAP)
    root.set(f"{{{XSI}}}schemaLocation", SCHEMA_LOCATION)
    root.set("identifier", "id-model")

    _append_text(root, "name", model.name)
    _append_text(root, "documentation", model.documentation)

    # Collect every property key up front: definitions are declared once per model.
    definitions: dict[str, str] = {}
    for concept in list(model.elements.values()) + list(model.relationships.values()):
        for key in _governance_properties(concept):
            definitions.setdefault(key, _property_definition_id(key))

    element_ids = sorted(model.elements)
    if element_ids:
        container = etree.SubElement(root, _qn("elements"))
        for element_id in element_ids:
            element = model.elements[element_id]
            node = etree.SubElement(container, _qn("element"))
            node.set("identifier", concept_id(element.id))
            node.set(f"{{{XSI}}}type", element.type)
            _append_text(node, "name", element.name)
            _append_text(node, "documentation", element.documentation)
            _append_properties(node, _governance_properties(element), definitions)

    relationship_ids = sorted(model.relationships)
    if relationship_ids:
        container = etree.SubElement(root, _qn("relationships"))
        for relationship_id in relationship_ids:
            relationship = model.relationships[relationship_id]
            if relationship.source not in model.elements or relationship.target not in model.elements:
                raise CompileError(
                    f"relationship '{relationship.id}' has an unresolved endpoint; validate before compiling"
                )
            node = etree.SubElement(container, _qn("relationship"))
            node.set("identifier", concept_id(relationship.id))
            node.set("source", concept_id(relationship.source))
            node.set("target", concept_id(relationship.target))
            node.set(f"{{{XSI}}}type", relationship.type)
            _append_text(node, "name", relationship.name)
            _append_text(node, "documentation", relationship.documentation)
            _append_properties(node, _governance_properties(relationship), definitions)

    # Organizations mirror the ArchiMate layers so the model tree is navigable.
    by_layer: dict[str, list[str]] = {}
    for element_id in element_ids:
        by_layer.setdefault(oracle.layer_of(model.elements[element_id].type), []).append(element_id)
    if by_layer or relationship_ids:
        organizations = etree.SubElement(root, _qn("organizations"))
        for layer in oracle.LAYER_ORDER:
            members = by_layer.get(layer)
            if not members:
                continue
            item = etree.SubElement(organizations, _qn("item"))
            _append_text(item, "label", layer)
            for element_id in sorted(members):
                child = etree.SubElement(item, _qn("item"))
                child.set("identifierRef", concept_id(element_id))
        if relationship_ids:
            item = etree.SubElement(organizations, _qn("item"))
            _append_text(item, "label", "Relations")
            for relationship_id in relationship_ids:
                child = etree.SubElement(item, _qn("item"))
                child.set("identifierRef", concept_id(relationship_id))

    if definitions:
        container = etree.SubElement(root, _qn("propertyDefinitions"))
        for key in sorted(definitions):
            node = etree.SubElement(container, _qn("propertyDefinition"))
            node.set("identifier", definitions[key])
            node.set("type", "string")
            _append_text(node, "name", key)

    view_ids = sorted(model.views)
    if view_ids:
        views = etree.SubElement(root, _qn("views"))
        diagrams = etree.SubElement(views, _qn("diagrams"))
        for view_id in view_ids:
            view = model.views[view_id]
            included = [e for e in view.include if e in model.elements]
            node = etree.SubElement(diagrams, _qn("view"))
            node.set("identifier", concept_id(f"view-{view.id}"))
            node.set(f"{{{XSI}}}type", "Diagram")
            if view.viewpoint:
                node.set("viewpoint", view.viewpoint)
            _append_text(node, "name", view.name)
            _append_text(node, "documentation", view.documentation)

            positions = _layout(model, included)
            node_ids: dict[str, str] = {}
            for element_id in sorted(included):
                x, y = positions[element_id]
                node_identifier = concept_id(f"node-{view.id}-{element_id}")
                node_ids[element_id] = node_identifier
                visual = etree.SubElement(node, _qn("node"))
                visual.set("identifier", node_identifier)
                visual.set(f"{{{XSI}}}type", "Element")
                visual.set("elementRef", concept_id(element_id))
                visual.set("x", str(x))
                visual.set("y", str(y))
                visual.set("w", str(NODE_WIDTH))
                visual.set("h", str(NODE_HEIGHT))

            shown = set(included)
            for relationship_id in relationship_ids:
                relationship = model.relationships[relationship_id]
                if relationship.source not in shown or relationship.target not in shown:
                    continue
                connection = etree.SubElement(node, _qn("connection"))
                connection.set("identifier", concept_id(f"conn-{view.id}-{relationship.id}"))
                connection.set(f"{{{XSI}}}type", "Relationship")
                connection.set("relationshipRef", concept_id(relationship.id))
                connection.set("source", node_ids[relationship.source])
                connection.set("target", node_ids[relationship.target])

    return etree.ElementTree(root)


def validate_against_xsd(xml: bytes) -> list[str]:
    schema = oracle.exchange_schema()
    document = etree.fromstring(xml)
    if schema.validate(document):
        return []
    return [f"line {e.line}: {e.message}" for e in schema.error_log]


def compile_model(root: Path, zone: str = "approved", out: Path | None = None) -> CompileResult:
    model, _documents, _config = dsl.load(root, zone)
    tree = build_tree(model)
    xml = etree.tostring(tree, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    target = out or (root / "build" / "model.xml")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(xml)
    return CompileResult(
        path=target,
        xml=xml,
        elements=len(model.elements),
        relationships=len(model.relationships),
        views=len(model.views),
        schema_errors=validate_against_xsd(xml),
    )
