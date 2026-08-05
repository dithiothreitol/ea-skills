"""Import an Open Group ArchiMate Model Exchange file into ``model/staging/``.

The adoption path for a repository that does not start empty. Real organisations have
an architecture already -- in Archi, in a commercial tool, in whatever exported the
XML -- and a discipline nobody can migrate *into* is a discipline nobody adopts. So
this is ``aoef.py`` run backwards, with the repository's own rules applied to what
comes in:

* **Everything lands in staging.** An import is a proposal like any other; promotion
  is still the only write path into ``approved/`` and still runs the gate.
* **Nothing imported is evidence.** The old tool's content arrives as *claims*: every
  concept without governance metadata to say otherwise is marked ``assumed: true``
  with an import rationale, so ``PROV006`` lists it and the fact-register work starts
  from an honest zero. A ``provenance`` property from a previous export is kept as
  information, never trusted as verification.
* **Geometry is discarded.** Layout is computed deterministically at render time; the
  import keeps a view's *content* (which elements it shows) and drops the pixels.
* **What cannot be imported is named.** Unsupported types, skipped relationships and
  every identifier that had to be renamed are in the report -- a migration summary
  that quietly drops content is how models lose limbs.

The import itself never judges the model: a relationship the ArchiMate 3.2 matrix
forbids is imported as-is and left for ``validate`` to report, because "your previous
tool allowed this" is exactly the finding a migration should surface, in the gate
where every other finding lives.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from lxml import etree

from . import aoef, oracle

# Property keys `aoef.py` writes for governance metadata; lifted back into DSL fields
# on import (and removed from the property map, so nothing exists twice).
LIFTED_SCALARS = {"owner": "owner", "lastReviewed": "lastReviewed"}
LIFTED_LISTS = {"appliesTo": "appliesTo", "standards": "standards"}

# The exchange format models a junction as a typed element; the 3.2 matrix (and this
# DSL) knows the one concept `Junction`. Mapped, not dropped: junctions sit on
# relationship chains, and removing one silently severs the chain.
TYPE_ALIASES = {"AndJunction": "Junction", "OrJunction": "Junction"}

SLUG_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789._-")


class ImportRefusal(RuntimeError):
    pass


@dataclass
class ImportReport:
    source: str
    target: str
    ids: str
    sha256: str
    elements: int = 0
    relationships: int = 0
    views: int = 0
    renamed: list[dict[str, str]] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    xsd_errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "sourceSha256": self.sha256,
            "target": self.target,
            "ids": self.ids,
            "counts": {
                "elements": self.elements,
                "relationships": self.relationships,
                "views": self.views,
            },
            "renamed": self.renamed,
            "skipped": self.skipped,
            "notes": self.notes,
            "xsdErrors": self.xsd_errors,
        }


def _slugify(text: str) -> str:
    lowered = text.lower()
    replaced = "".join(ch if ch in SLUG_CHARS else "-" for ch in lowered)
    collapsed = re.sub(r"-{2,}", "-", replaced)
    trimmed = collapsed.strip("-._")
    return trimmed[:80].rstrip("-._")


def _strip_export_prefix(identifier: str) -> str:
    """``aoef.concept_id`` prefixes every slug with ``id-`` (and views additionally
    with ``view-``) to make a valid NCName; peel both so a round-trip recovers the
    original slugs. Foreign identifiers only get cleaner for it."""
    for prefix in ("id-view-", "id-"):
        if identifier.startswith(prefix) and len(identifier) > len(prefix):
            return identifier[len(prefix) :]
    return identifier


@dataclass
class _IdAllocator:
    mode: str  # "names" | "identifiers"
    report: ImportReport
    used: set[str] = field(default_factory=set)

    def allocate(self, identifier: str, name: str) -> str:
        from_identifier = _slugify(_strip_export_prefix(identifier))
        from_name = _slugify(name)
        candidates = (
            [from_name, from_identifier] if self.mode == "names" else [from_identifier, from_name]
        )
        base = next((c for c in candidates if c), "imported")
        slug = base
        suffix = 2
        while slug in self.used:
            slug = f"{base}-{suffix}"
            suffix += 1
        self.used.add(slug)
        if slug != identifier:
            self.report.renamed.append({"from": identifier, "to": slug})
        return slug


def _text_of(node: etree._Element, tag: str) -> str:
    child = node.find(f"{{*}}{tag}")
    return (child.text or "").strip() if child is not None else ""


def _properties_of(node: etree._Element, definitions: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    container = node.find("{*}properties")
    if container is None:
        return out
    for prop in container.findall("{*}property"):
        key = definitions.get(prop.get("propertyDefinitionRef", ""), "")
        value = _text_of(prop, "value")
        if key:
            out[key] = value
    return out


def _lift_governance(item: dict[str, Any], properties: dict[str, str], source_name: str) -> None:
    """Move exported governance metadata back into DSL fields; mark the rest assumed.

    The `provenance` property, if present, is *kept as a property*: it says what the
    previous tool claimed, and this repository has verified none of it. Verification
    is the fact register's job, quote by quote, after import.
    """
    for prop_key, field_name in LIFTED_SCALARS.items():
        value = properties.pop(prop_key, "")
        if value:
            item[field_name] = value
    for prop_key, field_name in LIFTED_LISTS.items():
        value = properties.pop(prop_key, "")
        if value:
            item[field_name] = [part for part in (p.strip() for p in value.split(",")) if part]
    assumed = properties.pop("assumed", "") == "true"
    rationale = properties.pop("assumptionRationale", "")
    item["assumed"] = True
    item["rationale"] = (
        rationale
        if assumed and rationale
        else f"Imported from {source_name}; not yet evidenced in this repository."
    )
    if properties:
        item["properties"] = dict(sorted(properties.items()))


def read_exchange(xml: bytes, ids: str, report: ImportReport) -> dict[str, Any]:
    """Exchange XML -> the DSL document, best-effort with every omission reported."""
    try:
        root = etree.fromstring(xml)
    except etree.XMLSyntaxError as exc:
        raise ImportRefusal(f"not parseable as XML: {exc}") from exc
    if etree.QName(root).localname != "model":
        raise ImportRefusal(f"root element is <{etree.QName(root).localname}>, expected <model>")

    xsi_type = f"{{{oracle.XSI_NS}}}type"
    known_types = oracle.element_types()

    definitions: dict[str, str] = {}
    for definition in root.findall("{*}propertyDefinitions/{*}propertyDefinition"):
        definitions[definition.get("identifier", "")] = _text_of(definition, "name")

    allocator = _IdAllocator(mode=ids, report=report)
    source_name = report.source
    elements: list[dict[str, Any]] = []
    id_map: dict[str, str] = {}  # XML identifier -> DSL slug
    for node in root.findall("{*}elements/{*}element"):
        identifier = node.get("identifier", "")
        declared = node.get(xsi_type, "")
        mapped = TYPE_ALIASES.get(declared, declared)
        if mapped != declared:
            report.notes.append(f"element '{identifier}': type {declared} imported as {mapped}")
        if mapped not in known_types:
            report.skipped.append(
                {
                    "kind": "element",
                    "identifier": identifier,
                    "reason": f"'{declared}' is not an ArchiMate {oracle.matrix_version()} concept",
                }
            )
            continue
        name = _text_of(node, "name")
        slug = allocator.allocate(identifier, name)
        id_map[identifier] = slug
        item: dict[str, Any] = {"id": slug, "type": mapped, "name": name or slug}
        if not name:
            report.notes.append(f"element '{identifier}': unnamed in the export, named '{slug}'")
        documentation = _text_of(node, "documentation")
        if documentation:
            item["documentation"] = documentation
        _lift_governance(item, _properties_of(node, definitions), source_name)
        elements.append(item)

    relationships: list[dict[str, Any]] = []
    for node in root.findall("{*}relationships/{*}relationship"):
        identifier = node.get("identifier", "")
        rel_type = node.get(xsi_type, "")
        source_ref = node.get("source", "")
        target_ref = node.get("target", "")
        if source_ref not in id_map or target_ref not in id_map:
            report.skipped.append(
                {
                    "kind": "relationship",
                    "identifier": identifier,
                    "reason": "an endpoint was not imported",
                }
            )
            continue
        name = _text_of(node, "name")
        fallback = f"{id_map[source_ref]}-{rel_type.lower()}-{id_map[target_ref]}"
        slug = allocator.allocate(identifier, name or (fallback if ids == "names" else ""))
        item = {
            "id": slug,
            "type": rel_type,
            "source": id_map[source_ref],
            "target": id_map[target_ref],
        }
        if name:
            item["name"] = name
        documentation = _text_of(node, "documentation")
        if documentation:
            item["documentation"] = documentation
        _lift_governance(item, _properties_of(node, definitions), source_name)
        relationships.append(item)

    views: list[dict[str, Any]] = []
    dropped_geometry = False
    for node in root.findall("{*}views/{*}diagrams/{*}view"):
        identifier = node.get("identifier", "")
        name = _text_of(node, "name")
        slug = allocator.allocate(identifier, name)
        include: list[str] = []
        for visual in node.iter("{*}node"):
            ref = visual.get("elementRef", "")
            mapped_ref = id_map.get(ref)
            if mapped_ref and mapped_ref not in include:
                include.append(mapped_ref)
            if visual.get("x") is not None:
                dropped_geometry = True
        item = {"id": slug, "name": name or slug}
        viewpoint = node.get("viewpoint", "")
        if viewpoint:
            item["viewpoint"] = viewpoint
        documentation = _text_of(node, "documentation")
        if documentation:
            item["documentation"] = documentation
        if include:
            item["include"] = include
        views.append(item)
    if dropped_geometry:
        report.notes.append(
            "diagram geometry discarded: layout is computed deterministically at render time"
        )

    # Lifted `appliesTo` values are the *exporting* repository's slugs; the elements
    # they bind were just renamed. Remap them through the identifier map (an exported
    # slug appears as the identifier `id-<slug>`), and leave anything unmapped as-is
    # for MOT001 to report -- rewriting a reference to nothing would hide a dangle.
    stripped_map = {_strip_export_prefix(xml_id): slug for xml_id, slug in id_map.items()}
    for item in elements:
        if "appliesTo" in item:
            item["appliesTo"] = [stripped_map.get(ref, ref) for ref in item["appliesTo"]]

    report.elements = len(elements)
    report.relationships = len(relationships)
    report.views = len(views)
    document: dict[str, Any] = {}
    if elements:
        document["elements"] = elements
    if relationships:
        document["relationships"] = relationships
    if views:
        document["views"] = views
    return document


def _header(report: ImportReport) -> str:
    return (
        f"# Imported from {report.source} (sha256 {report.sha256[:16]}) by\n"
        "# `python -m easkills import`. This file is a *proposal* in staging: every\n"
        "# concept without verified evidence is marked `assumed`, diagram geometry was\n"
        "# discarded (layout is computed at render time), and promotion still runs the\n"
        "# gate. Identifier changes are listed in the import report.\n"
    )


def import_exchange(
    root: Path, source: Path, out: Path | None = None, ids: str = "names"
) -> ImportReport:
    if not source.is_file():
        raise ImportRefusal(f"{source} does not exist")
    xml = source.read_bytes()
    target = out or (root / "model" / "staging" / f"{_slugify(source.stem) or 'imported'}.yaml")
    if target.exists():
        raise ImportRefusal(
            f"{target} already exists -- an import never overwrites; move the file aside first"
        )
    report = ImportReport(
        source=source.name,
        target=str(target),
        ids=ids,
        sha256=hashlib.sha256(xml).hexdigest(),
    )
    # Advisory, not a refusal: the point of importing is meeting the previous tool
    # where it is, and its export quirks are findings for the report, not blockers.
    try:
        report.xsd_errors = aoef.validate_against_xsd(xml)
    except etree.XMLSyntaxError:
        pass  # unparseable XML is refused below, with the parser's own message

    document = read_exchange(xml, ids, report)
    if not document:
        raise ImportRefusal(f"{source.name} contains no importable content")

    target.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(
        document, sort_keys=False, allow_unicode=True, default_flow_style=False, width=98
    )
    target.write_text(_header(report) + "\n" + body, encoding="utf-8", newline="\n")
    return report
