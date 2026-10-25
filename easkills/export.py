"""Views as diagram text: PlantUML (ArchiMate notation) and Mermaid.

The SVG ``render`` draws is a reading aid with a fixed layout. Architects paste diagrams
into wikis, pull requests and slide tools that already render PlantUML or Mermaid, and
redrawing a view by hand there is how a diagram starts to disagree with the model. The
export is generated from the same view definitions, byte-stable, and carries no layout of
its own -- the receiving tool lays it out.

**PlantUML** uses the ArchiMate library in PlantUML's standard library
(``!include <archimate/Archimate>``): one procedure per element type and one per
relationship type. The mapping below was checked against ``stdlib/archimate/Archimate.puml``
at plantuml-stdlib commit ``d4a391be`` (Archimate-PlantUML 3.2.2), and a test holds every
type the oracle knows to a procedure that file defines. **Mermaid** has no ArchiMate
notation, so a view becomes a flowchart: the layer colours ``render`` uses, the type
under the name, dashed arrows for Realization and Specialization -- the same simplified
notation, in a format GitHub renders inline.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import dsl, oracle
from .render import DASHED_RELATIONSHIPS, LAYER_FILL

FORMATS = ("plantuml", "mermaid")
SUFFIX = {"plantuml": ".puml", "mermaid": ".mmd"}

# The procedures stdlib/archimate/Archimate.puml defines (plantuml-stdlib d4a391be),
# without the _Up/_Down/_Left/_Right layout variants. Copied, not guessed: a procedure
# name that does not exist makes PlantUML fail the whole diagram.
PLANTUML_PROCEDURES = frozenset(
    """
    Strategy_Resource Strategy_Capability Strategy_CourseOfAction Strategy_ValueStream
    Business_Actor Business_Role Business_Collaboration Business_Interface Business_Process
    Business_Function Business_Interaction Business_Event Business_Service Business_Object
    Business_Contract Business_Representation Business_Product Business_Location
    Application_Component Application_Collaboration Application_Interface Application_Function
    Application_Interaction Application_Process Application_Event Application_Service
    Application_DataObject Technology_Node Technology_Device Technology_SystemSoftware
    Technology_Collaboration Technology_Interface Technology_Path Technology_CommunicationNetwork
    Technology_Function Technology_Process Technology_Interaction Technology_Event
    Technology_Service Technology_Artifact Physical_Equipment Physical_Facility
    Physical_DistributionNetwork Physical_Material Motivation_Stakeholder Motivation_Driver
    Motivation_Assessment Motivation_Goal Motivation_Outcome Motivation_Principle
    Motivation_Requirement Motivation_Constraint Motivation_Meaning Motivation_Value
    Implementation_WorkPackage Implementation_Deliverable Implementation_Event
    Implementation_Plateau Implementation_Gap Other_Location Other_Grouping Junction_Or
    Junction_And Grouping Rel_Composition Rel_Aggregation Rel_Assignment Rel_Specialization
    Rel_Serving Rel_Association Rel_Flow Rel_Realization Rel_Triggering Rel_Access
    Rel_Influence
    """.split()
)

# Where the type name does not follow "<Layer>_<type minus its layer word>". A junction's
# and/or kind is not modelled here, so it is drawn as the stdlib's Or junction; Grouping
# is the container form, which needs no body to render.
PLANTUML_EXCEPTIONS = {"Grouping": "Other_Grouping", "Junction": "Junction_Or", "Location": "Other_Location"}

MERMAID_RESERVED = {"end", "graph", "subgraph", "flowchart", "style", "class", "classdef", "click", "linkstyle", "direction"}


class ExportError(RuntimeError):
    pass


def plantuml_procedure(element_type: str) -> str:
    if element_type in PLANTUML_EXCEPTIONS:
        return PLANTUML_EXCEPTIONS[element_type]
    layer = oracle.layer_of(element_type) or "Other"
    rest = element_type[len(layer):] if element_type.startswith(layer) and element_type != layer else element_type
    return f"{layer}_{rest}"


def _aliases(ids: list[str]) -> dict[str, str]:
    """Diagram-safe names, injective: slugs may hold '.', '_' and '-', diagrams may not."""
    out: dict[str, str] = {}
    taken: set[str] = set()
    for element_id in sorted(ids):
        base = re.sub(r"[^a-z0-9_]", "_", element_id.lower())
        if base[0].isdigit() or base in MERMAID_RESERVED:
            base = f"e_{base}"
        alias, n = base, 2
        while alias in taken:
            alias, n = f"{base}_{n}", n + 1
        taken.add(alias)
        out[element_id] = alias
    return out


def _quote_plantuml(text: str) -> str:
    return text.replace('"', "'").replace("\n", " ")


def _quote_mermaid(text: str) -> str:
    return text.replace('"', "#quot;").replace("\n", " ")


def _shown(model: dsl.Model, view: dsl.View) -> tuple[list[str], list[dsl.Relationship]]:
    missing = [e for e in view.include if e not in model.elements]
    if missing:
        raise ExportError(f"view '{view.id}' includes unknown element(s) {missing}; validate before exporting")
    shown = list(dict.fromkeys(view.include))
    members = set(shown)
    relationships = [
        model.relationships[r]
        for r in sorted(model.relationships)
        if model.relationships[r].source in members and model.relationships[r].target in members
    ]
    return shown, relationships


def plantuml(model: dsl.Model, view: dsl.View) -> str:
    shown, relationships = _shown(model, view)
    alias = _aliases(shown)
    lines = [
        f"@startuml {re.sub(r'[^A-Za-z0-9_-]', '_', view.id)}",
        "!include <archimate/Archimate>",
        f"title {_quote_plantuml(view.name)}",
        "",
    ]
    for element_id in sorted(shown):
        element = model.elements[element_id]
        lines.append(f'{plantuml_procedure(element.type)}({alias[element_id]}, "{_quote_plantuml(element.name)}")')
    if relationships:
        lines.append("")
    for relationship in relationships:
        label = _quote_plantuml(relationship.name)
        lines.append(
            f'Rel_{relationship.type}({alias[relationship.source]}, {alias[relationship.target]}, "{label}")'
        )
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def mermaid(model: dsl.Model, view: dsl.View) -> str:
    shown, relationships = _shown(model, view)
    alias = _aliases(shown)
    lines = ["---", f"title: {_quote_mermaid(view.name)}", "---", "flowchart TB"]
    layers: dict[str, list[str]] = {}
    for element_id in sorted(shown):
        element = model.elements[element_id]
        lines.append(
            f'  {alias[element_id]}["{_quote_mermaid(element.name)}<br/>«{element.type}»"]'
        )
        layer = oracle.layer_of(element.type) or "Other"
        layers.setdefault(layer, []).append(alias[element_id])
    for relationship in relationships:
        arrow = "-.->" if relationship.type in DASHED_RELATIONSHIPS else "-->"
        lines.append(f"  {alias[relationship.source]} {arrow}|{relationship.type}| {alias[relationship.target]}")
    for layer in sorted(layers):
        fill = LAYER_FILL.get(layer, LAYER_FILL["Other"])
        lines.append(f"  classDef {layer.lower()} fill:{fill},stroke:#777777,color:#000000")
        lines.append(f"  class {','.join(layers[layer])} {layer.lower()}")
    return "\n".join(lines) + "\n"


def export(root: Path, fmt: str, zone: str = "approved", view_id: str | None = None) -> dict[str, str]:
    """``{view id: diagram text}`` for one view or every view, in id order."""
    if fmt not in FORMATS:
        raise ExportError(f"unknown format '{fmt}' -- one of {', '.join(FORMATS)}")
    model, _documents, _config = dsl.load_zone(root, zone)
    if view_id is not None and view_id not in model.views:
        raise ExportError(f"'{view_id}' is not a view of the {zone} model")
    ids = [view_id] if view_id else sorted(model.views)
    writer = plantuml if fmt == "plantuml" else mermaid
    out: dict[str, str] = {}
    for vid in ids:
        if not model.views[vid].include:
            continue
        out[vid] = writer(model, model.views[vid])
    return out
