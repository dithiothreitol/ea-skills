"""Generate the JSON Schema for the model DSL from the vendored oracle.

The schema is a build artifact, not hand-authored: its ``type`` enumerations come
straight from the ArchiMate 3.2 relationship matrix, so the DSL can never drift
from the oracle the semantic validator uses. Regenerate with::

    python -m easkills gen-schema
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import oracle

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "model.schema.json"

SLUG_PATTERN = "^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$"
DATE_PATTERN = "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"


def build_schema() -> dict[str, Any]:
    element_types = sorted(oracle.element_types())
    relationship_types = sorted(oracle.relationship_types())

    provenance_item = {
        "type": "object",
        "additionalProperties": False,
        "required": ["file", "quote"],
        "properties": {
            "file": {
                "type": "string",
                "minLength": 1,
                "description": "Path to the source document, relative to the repository root.",
            },
            "quote": {
                "type": "string",
                "minLength": 8,
                "description": "Verbatim excerpt from that document; verified mechanically.",
            },
        },
    }

    common_properties: dict[str, Any] = {
        "id": {"$ref": "#/$defs/slug"},
        "name": {"type": "string", "minLength": 1, "maxLength": 120},
        "documentation": {"type": "string"},
        "owner": {"type": "string", "minLength": 1},
        "lastReviewed": {"type": "string", "pattern": DATE_PATTERN},
        "provenance": {
            "type": "array",
            "minItems": 1,
            "items": {"$ref": "#/$defs/provenance"},
        },
        "assumed": {
            "type": "boolean",
            "description": "True when the concept is not evidenced by a source; requires a rationale.",
        },
        "rationale": {"type": "string", "minLength": 1},
        "properties": {
            "type": "object",
            "additionalProperties": {"type": ["string", "number", "boolean", "null"]},
        },
    }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:ea-skills:schema:model",
        "title": "EA Skills model file",
        "description": (
            "One fragment of the enterprise architecture model. Enumerations are generated "
            f"from the vendored ArchiMate {oracle.matrix_version()} oracle."
        ),
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "elements": {"type": "array", "items": {"$ref": "#/$defs/element"}},
            "relationships": {"type": "array", "items": {"$ref": "#/$defs/relationship"}},
            "views": {"type": "array", "items": {"$ref": "#/$defs/view"}},
        },
        "$defs": {
            "slug": {
                "type": "string",
                "pattern": SLUG_PATTERN,
                "maxLength": 80,
                "description": "Stable author-supplied identifier; never regenerated.",
            },
            "provenance": provenance_item,
            "element": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "type", "name"],
                "properties": {
                    **common_properties,
                    "type": {"enum": element_types},
                },
            },
            "relationship": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "type", "source", "target"],
                "properties": {
                    **common_properties,
                    "name": {"type": "string", "maxLength": 120},
                    "type": {"enum": relationship_types},
                    "source": {"$ref": "#/$defs/slug"},
                    "target": {"$ref": "#/$defs/slug"},
                },
            },
            "view": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "name"],
                "properties": {
                    "id": {"$ref": "#/$defs/slug"},
                    "name": {"type": "string", "minLength": 1, "maxLength": 120},
                    "documentation": {"type": "string"},
                    "viewpoint": {
                        "type": "string",
                        "description": "ArchiMate example viewpoint name, e.g. Layered or Capability Map.",
                    },
                    "include": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/slug"},
                        "description": "Element ids to show; connections are derived from the model.",
                    },
                },
            },
        },
    }


def write_schema(path: Path | None = None) -> Path:
    target = path or SCHEMA_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_schema(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def load_schema(path: Path | None = None) -> dict[str, Any]:
    target = path or SCHEMA_PATH
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    return build_schema()
