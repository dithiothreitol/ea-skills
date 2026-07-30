"""Validation oracle: ArchiMate 3.2 concept registry and permitted-relationship matrix.

The rule data is NOT authored here. It is vendored under ``oracle/`` from primary
sources and hash-pinned, so the semantic checks in :mod:`easkills.validate` are
grounded in the same table the Archi tool enforces:

* ``oracle/relationships.xml``      -- permitted (source, target) -> relationship letters
* ``oracle/relationships-keys.xml`` -- letter -> relationship type legend
* ``oracle/archimate3_*.xsd``       -- Open Group Model Exchange File Format schemas

Vendoring is deliberate: pubs.opengroup.org is behind SSO, so nothing may be
fetched at validation time.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from lxml import etree

ORACLE_DIR = Path(__file__).resolve().parent.parent / "oracle"

RELATIONSHIPS_XML = ORACLE_DIR / "relationships.xml"
RELATIONSHIP_KEYS_XML = ORACLE_DIR / "relationships-keys.xml"
MODEL_XSD = ORACLE_DIR / "archimate3_Model.xsd"
DIAGRAM_XSD = ORACLE_DIR / "archimate3_Diagram.xsd"
XML_NAMESPACE_XSD = ORACLE_DIR / "xml.xsd"
CHECKSUMS = ORACLE_DIR / "SHA256SUMS"

# The Open Group model schema declares
#   <xs:import namespace="http://www.w3.org/XML/1998/namespace"
#              schemaLocation="http://www.w3.org/2001/xml.xsd" />
# so a naive schema build silently reaches out to w3.org -- which works on a developer
# machine and fails in a sandboxed CI runner, the worst possible failure mode for a
# validation gate. The referenced schema is vendored and mapped here instead. The
# vendored XSDs themselves stay byte-identical, because they are hash-pinned.
REMOTE_SCHEMA_MAP: dict[str, Path] = {
    "http://www.w3.org/2001/xml.xsd": XML_NAMESPACE_XSD,
    "https://www.w3.org/2001/xml.xsd": XML_NAMESPACE_XSD,
}

AOEF_NS = "http://www.opengroup.org/xsd/archimate/3.0/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

# ``Relationship`` appears in relationships.xml only as a *target* concept: it stands
# for "an association pointing at another relationship". It is not an element type.
PSEUDO_CONCEPTS = frozenset({"Relationship"})

LAYER_ORDER = (
    "Strategy",
    "Business",
    "Application",
    "Technology",
    "Physical",
    "Motivation",
    "Implementation",
    "Other",
)

# ArchiMate 3.2 layer/aspect assignment per the specification (Chapters 6-13).
ELEMENT_LAYER: dict[str, str] = {
    # Strategy
    "Resource": "Strategy",
    "Capability": "Strategy",
    "CourseOfAction": "Strategy",
    "ValueStream": "Strategy",
    # Business
    "BusinessActor": "Business",
    "BusinessRole": "Business",
    "BusinessCollaboration": "Business",
    "BusinessInterface": "Business",
    "BusinessProcess": "Business",
    "BusinessFunction": "Business",
    "BusinessInteraction": "Business",
    "BusinessEvent": "Business",
    "BusinessService": "Business",
    "BusinessObject": "Business",
    "Contract": "Business",
    "Representation": "Business",
    "Product": "Business",
    # Application
    "ApplicationComponent": "Application",
    "ApplicationCollaboration": "Application",
    "ApplicationInterface": "Application",
    "ApplicationFunction": "Application",
    "ApplicationInteraction": "Application",
    "ApplicationProcess": "Application",
    "ApplicationEvent": "Application",
    "ApplicationService": "Application",
    "DataObject": "Application",
    # Technology
    "Node": "Technology",
    "Device": "Technology",
    "SystemSoftware": "Technology",
    "TechnologyCollaboration": "Technology",
    "TechnologyInterface": "Technology",
    "Path": "Technology",
    "CommunicationNetwork": "Technology",
    "TechnologyFunction": "Technology",
    "TechnologyProcess": "Technology",
    "TechnologyInteraction": "Technology",
    "TechnologyEvent": "Technology",
    "TechnologyService": "Technology",
    "Artifact": "Technology",
    # Physical (part of the Technology layer since 3.2, kept separate for layout)
    "Equipment": "Physical",
    "Facility": "Physical",
    "DistributionNetwork": "Physical",
    "Material": "Physical",
    # Motivation
    "Stakeholder": "Motivation",
    "Driver": "Motivation",
    "Assessment": "Motivation",
    "Goal": "Motivation",
    "Outcome": "Motivation",
    "Principle": "Motivation",
    "Requirement": "Motivation",
    "Constraint": "Motivation",
    "Meaning": "Motivation",
    "Value": "Motivation",
    # Implementation & Migration
    "WorkPackage": "Implementation",
    "Deliverable": "Implementation",
    "ImplementationEvent": "Implementation",
    "Plateau": "Implementation",
    "Gap": "Implementation",
    # Cross-cutting / composite
    "Location": "Other",
    "Grouping": "Other",
    "Junction": "Other",
}

# Relationship classification used by the structural-cycle and strength checks.
STRUCTURAL_RELATIONSHIPS = frozenset({"Composition", "Aggregation", "Assignment", "Realization"})
DEPENDENCY_RELATIONSHIPS = frozenset({"Serving", "Access", "Influence", "Association"})
DYNAMIC_RELATIONSHIPS = frozenset({"Triggering", "Flow"})
OTHER_RELATIONSHIPS = frozenset({"Specialization"})

# Behaviour elements: names should read as verb phrases (naming convention check).
BEHAVIOUR_SUFFIXES = (
    "Process",
    "Function",
    "Interaction",
    "Event",
    "Service",
    "ValueStream",
    "CourseOfAction",
)


class OracleError(RuntimeError):
    """Raised when the vendored oracle is missing or fails its integrity check."""


@dataclass(frozen=True)
class ChecksumResult:
    name: str
    expected: str
    actual: str

    @property
    def ok(self) -> bool:
        return self.expected.lower() == self.actual.lower()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksums() -> list[ChecksumResult]:
    """Compare vendored oracle files against the pinned SHA-256 sums."""
    if not CHECKSUMS.exists():
        raise OracleError(f"missing checksum pin file: {CHECKSUMS}")
    results: list[ChecksumResult] = []
    for line in CHECKSUMS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        expected, _, name = line.partition("  ")
        name = name.strip()
        if not name:
            continue
        path = ORACLE_DIR / name
        actual = sha256(path) if path.exists() else ""
        results.append(ChecksumResult(name=name, expected=expected.strip(), actual=actual))
    return results


@lru_cache(maxsize=1)
def relationship_letters() -> dict[str, str]:
    """Letter -> short relationship type name (``v`` -> ``Serving``)."""
    if not RELATIONSHIP_KEYS_XML.exists():
        raise OracleError(f"missing oracle file: {RELATIONSHIP_KEYS_XML}")
    root = etree.parse(str(RELATIONSHIP_KEYS_XML)).getroot()
    mapping: dict[str, str] = {}
    for key in root.iter("key"):
        char = key.get("char")
        name = key.get("relationship", "")
        if char and name:
            mapping[char] = name.removesuffix("Relationship")
    if len(mapping) != 11:
        raise OracleError(f"expected 11 relationship keys, found {len(mapping)}")
    return mapping


@lru_cache(maxsize=1)
def relationship_types() -> frozenset[str]:
    return frozenset(relationship_letters().values())


@lru_cache(maxsize=1)
def _matrix() -> tuple[dict[tuple[str, str], frozenset[str]], frozenset[str], str]:
    if not RELATIONSHIPS_XML.exists():
        raise OracleError(f"missing oracle file: {RELATIONSHIPS_XML}")
    letters = relationship_letters()
    root = etree.parse(str(RELATIONSHIPS_XML)).getroot()
    version = root.get("version", "unknown")
    table: dict[tuple[str, str], frozenset[str]] = {}
    concepts: set[str] = set()
    for source in root.iter("source"):
        src = source.get("concept")
        if not src:
            continue
        concepts.add(src)
        for target in source.iter("target"):
            tgt = target.get("concept")
            if not tgt:
                continue
            concepts.add(tgt)
            allowed = {letters[ch] for ch in target.get("relations", "") if ch in letters}
            table[(src, tgt)] = frozenset(allowed)
    if not table:
        raise OracleError("relationship matrix parsed empty")
    return table, frozenset(concepts), version


def matrix_version() -> str:
    """ArchiMate version declared by the vendored matrix (expected: 3.2)."""
    return _matrix()[2]


class _OfflineResolver(etree.Resolver):
    """Resolve schema imports from the vendored oracle and refuse the network.

    Anything not vendored raises rather than being fetched, so an offline gap shows up
    as a loud error at development time instead of a green local run and a red CI run.
    """

    def resolve(self, system_url, public_id, context):  # noqa: D102 - lxml callback
        if system_url in REMOTE_SCHEMA_MAP:
            local = REMOTE_SCHEMA_MAP[system_url]
            if not local.is_file():
                raise OracleError(f"vendored schema missing for {system_url}: expected {local}")
            return self.resolve_filename(str(local), context)
        if system_url and (system_url.startswith("file:") or Path(system_url).exists()):
            return None  # local include between the vendored schemas; default handling
        raise OracleError(
            f"refusing to fetch a schema resource over the network: {system_url}. "
            "Vendor it under oracle/ and add it to REMOTE_SCHEMA_MAP."
        )


def schema_parser() -> etree.XMLParser:
    parser = etree.XMLParser(no_network=True)
    parser.resolvers.add(_OfflineResolver())
    return parser


@lru_cache(maxsize=1)
def exchange_schema() -> etree.XMLSchema:
    """The Open Exchange schema, built entirely from vendored files."""
    if not DIAGRAM_XSD.is_file():
        raise OracleError(f"missing oracle file: {DIAGRAM_XSD}")
    document = etree.parse(str(DIAGRAM_XSD), parser=schema_parser())
    return etree.XMLSchema(document)


@lru_cache(maxsize=1)
def element_types() -> frozenset[str]:
    """Concrete ArchiMate concept names usable as ``type:`` in the DSL."""
    _, concepts, _ = _matrix()
    return frozenset(c for c in concepts if c not in PSEUDO_CONCEPTS)


def allowed_relationships(source_type: str, target_type: str) -> frozenset[str]:
    """Relationship types permitted from ``source_type`` to ``target_type``."""
    table, _, _ = _matrix()
    return table.get((source_type, target_type), frozenset())


def layer_of(element_type: str) -> str:
    return ELEMENT_LAYER.get(element_type, "Other")


def is_behaviour(element_type: str) -> bool:
    return element_type.endswith(BEHAVIOUR_SUFFIXES)


def unmapped_layers() -> frozenset[str]:
    """Concepts present in the matrix but missing a layer assignment (drift guard)."""
    return frozenset(t for t in element_types() if t not in ELEMENT_LAYER)
