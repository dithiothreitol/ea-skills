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
}


@dataclass(frozen=True)
class Provenance:
    file: str
    quote: str


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
    pass


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
    paths = sorted(p for p in directory.rglob("*") if p.suffix in {".yaml", ".yml"})
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
            out.append(Provenance(file=str(item.get("file", "")), quote=str(item.get("quote", ""))))
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
            element = Element(**_common_kwargs(item, doc.path, locator))
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
            view = View(
                id=str(item.get("id", "")),
                name=str(item.get("name", "") or ""),
                viewpoint=str(item.get("viewpoint", "") or ""),
                documentation=str(item.get("documentation", "") or ""),
                include=[str(x) for x in include if isinstance(x, (str, int))],
                source_path=doc.path,
                locator=f"views[{index}]",
            )
            _register(model, model.views, view.id, view, doc.path)
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
