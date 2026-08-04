"""The YAML authoring DSL: loading, configuration and the in-memory model.

Design notes (see docs/BLUEPRINT.md, AD-01/AD-03/AD-04):

* The DSL is the single source of truth and lives in fragmented YAML so git diffs
  stay reviewable. Interchange formats (Open Exchange XML) are build artifacts.
* Identifiers are author-supplied stable slugs, never generated -- re-running the
  pipeline must produce reviewable diffs, not rewrites.
* Every concept carries provenance (source file + verbatim quote) or is explicitly
  marked ``assumed`` with a rationale. Nothing is invented silently.
"""

from __future__ import annotations

import datetime as _datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ZONES = ("approved", "staging")
CONFIG_FILENAME = "ea.config.yaml"

DEFAULT_CONFIG: dict[str, Any] = {
    "name": "Enterprise Architecture Model",
    "documentation": "",
    # Elements not reviewed within this many days raise a staleness warning.
    "stalenessDays": 365,
    # Minimum similarity for a provenance quote to count as an approximate match.
    "quoteMatchThreshold": 0.90,
    # Directory (relative to root) that provenance file references resolve against.
    "factsRoot": ".",
    # Directory (relative to root) holding the raw source documents ea-intake reads.
    "sourcesDir": "facts/sources",
}


@dataclass(frozen=True)
class Provenance:
    """Either a direct citation (``file`` + ``quote``) or a reference to a fact in
    the register (``fact``), whose own quotes are already mechanically verified."""

    file: str = ""
    quote: str = ""
    fact: str = ""


@dataclass
class Concept:
    """Common fields of elements and relationships."""

    id: str
    type: str
    name: str
    documentation: str = ""
    owner: str = ""
    last_reviewed: str = ""
    provenance: list[Provenance] = field(default_factory=list)
    assumed: bool = False
    rationale: str = ""
    properties: dict[str, str] = field(default_factory=dict)
    source_path: Path | None = None
    locator: str = ""


@dataclass
class Element(Concept):
    # Motivation-layer applicability selector (AD-09): which elements this
    # requirement/constraint/principle/goal binds. Validated by MOT001/MOT002.
    applies_to: list[str] = field(default_factory=list)
    # SIB references: standards this element claims to follow. Validated by STD001-004
    # against standards/ lifecycle states and open dispensations.
    standards: list[str] = field(default_factory=list)


@dataclass
class Relationship(Concept):
    source: str = ""
    target: str = ""


@dataclass
class View:
    id: str
    name: str
    viewpoint: str = ""
    documentation: str = ""
    include: list[str] = field(default_factory=list)
    # ISO 42010: the concerns this view frames. Checked by the ISO* rules.
    concerns: list[str] = field(default_factory=list)
    source_path: Path | None = None
    locator: str = ""


@dataclass
class Stakeholder:
    """ISO 42010 §6.3: someone with an interest in the architecture. Part of the
    architecture-description apparatus, not an ArchiMate model element."""

    id: str
    name: str
    description: str = ""
    concerns: list[str] = field(default_factory=list)
    source_path: Path | None = None
    locator: str = ""


@dataclass
class Concern:
    """ISO 42010 §6.4: an interest in the system relevant to a stakeholder."""

    id: str
    statement: str
    source_path: Path | None = None
    locator: str = ""


@dataclass
class Document:
    path: Path
    data: dict[str, Any] | None
    parse_error: str = ""


@dataclass
class Model:
    root: Path
    zone: str
    config: dict[str, Any]
    elements: dict[str, Element] = field(default_factory=dict)
    relationships: dict[str, Relationship] = field(default_factory=dict)
    views: dict[str, View] = field(default_factory=dict)
    stakeholders: dict[str, Stakeholder] = field(default_factory=dict)
    concerns: dict[str, Concern] = field(default_factory=dict)
    duplicate_ids: list[tuple[str, Path, Path]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return str(self.config.get("name", DEFAULT_CONFIG["name"]))

    @property
    def documentation(self) -> str:
        return str(self.config.get("documentation", ""))

    def facts_root(self) -> Path:
        return (self.root / str(self.config.get("factsRoot", "."))).resolve()


def load_config(root: Path) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    path = root / CONFIG_FILENAME
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            config.update(loaded)
    return config


def config_number(
    config: dict[str, Any],
    key: str,
    default: int | float,
    minimum: int | float | None = None,
    maximum: int | float | None = None,
) -> tuple[Any, str]:
    """Coerce a configured number, never raising. Returns ``(value, problem)``.

    ``ea.config.yaml`` is repository content, and two of its keys decide how strict
    other rules are. A typo there must therefore produce a *finding* (SCHEMA002, with
    the default applied) rather than a traceback that takes the whole gate down --
    and a threshold outside its usable range must be caught, because
    ``quoteMatchThreshold: 90`` would silently turn every verified quote into an error.
    """
    raw = config.get(key, default)
    if isinstance(raw, bool):  # bool is an int subclass; a flag here is a mistake
        return default, f"{key}: expected a number, got the boolean {raw!r}"
    try:
        value = type(default)(raw)
    except (TypeError, ValueError):
        return default, f"{key}: expected a number, got {raw!r}"
    if minimum is not None and value < minimum:
        return default, f"{key}: {value} is below the usable minimum {minimum}"
    if maximum is not None and value > maximum:
        return default, f"{key}: {value} is above the usable maximum {maximum}"
    return value, ""


def resolve_provenance_file(root: Path, facts_root: Path, reference: str) -> tuple[Path | None, str]:
    """Resolve a provenance ``file:`` reference, refusing to leave the repository.

    Returns ``(path, problem)``. Traceability must point at content a reviewer can
    open in this repository: a reference that escapes it (``../../secrets.txt``) is
    either a mistake or a way to have the validator confirm a quote against a file
    nobody reviews -- which, in CI on untrusted content, also probes the runner's
    filesystem. Reported as PROV008 / FACT008 instead of being read.
    """
    candidate = (facts_root / reference).resolve()
    if not candidate.is_relative_to(root.resolve()):
        return None, f"resolves outside the repository: {candidate}"
    return candidate, ""


def zone_dir(root: Path, zone: str) -> Path:
    return root / "model" / zone


def _normalize_scalars(value: Any) -> Any:
    """Render YAML's implicit date/datetime types back as ISO strings.

    ``lastReviewed: 2026-07-15`` is parsed by YAML as a ``datetime.date``, which would
    otherwise fail schema validation and force authors to quote every date. Normalizing
    here keeps both spellings valid.
    """
    if isinstance(value, dict):
        return {k: _normalize_scalars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_scalars(v) for v in value]
    if isinstance(value, _datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, _datetime.date):
        return value.isoformat()
    return value


def load_documents(root: Path, zone: str) -> list[Document]:
    """Read every YAML file in the zone, path-sorted for deterministic output."""
    directory = zone_dir(root, zone)
    documents: list[Document] = []
    if not directory.is_dir():
        return documents
    # is_file() matters: a *directory* named like a YAML file would otherwise be opened
    # and crash the loader instead of being ignored.
    paths = sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix in {".yaml", ".yml"})
    for path in paths:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            documents.append(Document(path=path, data=None, parse_error=str(exc)))
            continue
        if data is None:
            data = {}
        if not isinstance(data, dict):
            documents.append(
                Document(path=path, data=None, parse_error="top level of a model file must be a mapping")
            )
            continue
        documents.append(Document(path=path, data=_normalize_scalars(data)))
    return documents


def _provenance(raw: Any) -> list[Provenance]:
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else [raw]
    out: list[Provenance] = []
    for item in items:
        if isinstance(item, dict):
            out.append(
                Provenance(
                    file=str(item.get("file", "") or ""),
                    quote=str(item.get("quote", "") or ""),
                    fact=str(item.get("fact", "") or ""),
                )
            )
    return out


def _properties(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(k): "" if v is None else str(v) for k, v in raw.items()}


def _common_kwargs(item: dict[str, Any], path: Path, locator: str) -> dict[str, Any]:
    return {
        "id": str(item.get("id", "")),
        "type": str(item.get("type", "")),
        "name": str(item.get("name", "")),
        "documentation": str(item.get("documentation", "") or ""),
        "owner": str(item.get("owner", "") or ""),
        "last_reviewed": str(item.get("lastReviewed", "") or ""),
        "provenance": _provenance(item.get("provenance")),
        "assumed": bool(item.get("assumed", False)),
        "rationale": str(item.get("rationale", "") or ""),
        "properties": _properties(item.get("properties")),
        "source_path": path,
        "locator": locator,
    }


def build_model(root: Path, zone: str, documents: list[Document], config: dict[str, Any]) -> Model:
    """Assemble a Model best-effort; malformed items are skipped (validator reports them)."""
    model = Model(root=root, zone=zone, config=config)
    for doc in documents:
        if doc.data is None:
            continue
        for index, item in enumerate(doc.data.get("elements") or []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            locator = f"elements[{index}]"
            applies_raw = item.get("appliesTo") or []
            standards_raw = item.get("standards") or []
            element = Element(
                **_common_kwargs(item, doc.path, locator),
                applies_to=[str(x) for x in applies_raw if isinstance(x, (str, int))],
                standards=[str(x) for x in standards_raw if isinstance(x, (str, int))],
            )
            _register(model, model.elements, element.id, element, doc.path)
        for index, item in enumerate(doc.data.get("relationships") or []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            locator = f"relationships[{index}]"
            relationship = Relationship(
                **_common_kwargs(item, doc.path, locator),
                source=str(item.get("source", "")),
                target=str(item.get("target", "")),
            )
            _register(model, model.relationships, relationship.id, relationship, doc.path)
        for index, item in enumerate(doc.data.get("views") or []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            include = item.get("include") or []
            concerns = item.get("concerns") or []
            view = View(
                id=str(item.get("id", "")),
                name=str(item.get("name", "") or ""),
                viewpoint=str(item.get("viewpoint", "") or ""),
                documentation=str(item.get("documentation", "") or ""),
                include=[str(x) for x in include if isinstance(x, (str, int))],
                concerns=[str(x) for x in concerns if isinstance(x, (str, int))],
                source_path=doc.path,
                locator=f"views[{index}]",
            )
            _register(model, model.views, view.id, view, doc.path)
        for index, item in enumerate(doc.data.get("stakeholders") or []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            concerns = item.get("concerns") or []
            stakeholder = Stakeholder(
                id=str(item.get("id", "")),
                name=str(item.get("name", "") or ""),
                description=str(item.get("description", "") or ""),
                concerns=[str(x) for x in concerns if isinstance(x, (str, int))],
                source_path=doc.path,
                locator=f"stakeholders[{index}]",
            )
            _register(model, model.stakeholders, stakeholder.id, stakeholder, doc.path)
        for index, item in enumerate(doc.data.get("concerns") or []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            concern = Concern(
                id=str(item.get("id", "")),
                statement=str(item.get("statement", "") or ""),
                source_path=doc.path,
                locator=f"concerns[{index}]",
            )
            _register(model, model.concerns, concern.id, concern, doc.path)
    return model


def _register(model: Model, bucket: dict[str, Any], key: str, value: Any, path: Path) -> None:
    existing = bucket.get(key)
    if existing is not None:
        first = existing.source_path or path
        model.duplicate_ids.append((key, first, path))
        return
    bucket[key] = value


def load(root: Path, zone: str) -> tuple[Model, list[Document], dict[str, Any]]:
    config = load_config(root)
    documents = load_documents(root, zone)
    model = build_model(root, zone, documents, config)
    return model, documents, config


def load_merged(
    root: Path,
    staging_paths: list[Path] | None = None,
    zone_label: str = "staging",
) -> tuple[Model, list[Document], dict[str, Any]]:
    """Load ``staging`` overlaid on ``approved``: staging is a proposed *delta*.

    A staging concept with the same id as an approved one replaces it (an update
    proposal); a staging relationship may reference approved elements. Duplicates
    *within* a zone are still errors. ``staging_paths`` restricts the overlay to
    selected staging files, which is what partial promotion simulates.
    """
    config = load_config(root)
    approved_docs = load_documents(root, "approved")
    staging_docs = load_documents(root, "staging")
    if staging_paths is not None:
        wanted = {p.resolve() for p in staging_paths}
        staging_docs = [d for d in staging_docs if d.path.resolve() in wanted]

    model = build_model(root, zone_label, approved_docs, config)
    overlay = build_model(root, zone_label, staging_docs, config)
    model.duplicate_ids.extend(overlay.duplicate_ids)
    model.elements.update(overlay.elements)
    model.relationships.update(overlay.relationships)
    model.views.update(overlay.views)
    model.stakeholders.update(overlay.stakeholders)
    model.concerns.update(overlay.concerns)
    return model, approved_docs + staging_docs, config
