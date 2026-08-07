"""Reference models: the third oracle class.

Alongside the ArchiMate matrix and the Open Group XSDs, a *reference model* is
vendored, hash-pinned rule data -- except that it lives in the **consuming**
repository, because the useful ones (BIAN, APQC PCF, eTOM, ACORD) are licensed and
this repository ships mechanism, not content:

    reference/<name>/model.yaml    the taxonomy   -- pinned
    reference/<name>/NOTICE.md     source+licence -- pinned
    reference/<name>/SHA256SUMS    the pins
    reference/<name>/mappings.yaml the local judgement -- deliberately *not* pinned

``mappings.yaml`` is the one file an architect edits, so pinning it would mean
re-pinning after every mapping decision -- which trains exactly the habit
(``pin-reference`` as a reflex) that would make the pins worthless. The taxonomy is
what must not move underneath a coverage claim, and that is what is pinned. A pin
mismatch refuses the pack outright, the same way ``ORACLE001`` refuses the matrix:
coverage measured against a taxonomy someone edited is not a measurement.

**A taxonomy, not a model.** Nodes carry a parent and nothing else relational: no
relationships, no behaviour. Edges between architecture elements are what ``model/``
is for, and the oracle governs them. Resist adding them here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import dsl
from .genschema import REFERENCE_MAPPING_STATUSES, REFERENCE_NODE_KINDS
from .oracle import ChecksumResult, sha256

REFERENCE_DIRNAME = "reference"
MODEL_FILENAME = "model.yaml"
MAPPINGS_FILENAME = "mappings.yaml"
NOTICE_FILENAME = "NOTICE.md"
CHECKSUMS_FILENAME = "SHA256SUMS"

# What a pack must pin to be readable at all. The mapping file is excluded on purpose
# (see the module docstring); the NOTICE is included because a pack whose provenance
# can be swapped silently is a licence problem, not a formatting one.
PINNED_FILES = (MODEL_FILENAME, NOTICE_FILENAME)

# The vocabularies live in genschema with the other closed enumerations, because the
# generated schema is what enforces them; re-exported here so a reader of the loader
# does not have to go looking.
NODE_KINDS = REFERENCE_NODE_KINDS
MAPPING_STATUSES = REFERENCE_MAPPING_STATUSES


class ReferenceError(RuntimeError):
    """Raised for an operator mistake (an unknown pack name), never for pack content."""


@dataclass(frozen=True)
class ReferenceNode:
    """One node of a reference taxonomy."""

    id: str
    name: str
    kind: str
    parent: str = ""
    description: str = ""
    external_id: str = ""
    locator: str = ""


@dataclass(frozen=True)
class NodeMapping:
    """One recorded judgement: what local content answers a reference node, or why
    the node is out of this architecture's scope."""

    ref: str
    status: str
    elements: tuple[str, ...] = ()
    note: str = ""
    rationale: str = ""
    locator: str = ""


@dataclass
class ReferencePack:
    name: str
    directory: Path
    # Declaration order is preserved: a taxonomy reads top-down (GV, GV.OC, GV.RM),
    # and sorting it alphabetically would scramble the only structure it has.
    order: list[str] = field(default_factory=list)
    nodes: dict[str, ReferenceNode] = field(default_factory=dict)
    mappings: list[NodeMapping] = field(default_factory=list)
    documents: list[dsl.Document] = field(default_factory=list)
    checksums: list[ChecksumResult] = field(default_factory=list)
    # Non-empty means the pack was **not read**: the pins are missing or broken.
    refused: str = ""
    # Structural impossibilities the schema cannot express (duplicate node id, a
    # parent that is no node here). Reported as ALN000: the file does not read as a
    # taxonomy, so nothing downstream may rely on it.
    defects: list[tuple[str, str]] = field(default_factory=list)  # (message, locator)

    @property
    def children(self) -> dict[str, list[str]]:
        """Node id -> child ids, in declaration order."""
        out: dict[str, list[str]] = {node_id: [] for node_id in self.order}
        for node_id in self.order:
            parent = self.nodes[node_id].parent
            if parent and parent in out:
                out[parent].append(node_id)
        return out

    def roots(self) -> list[str]:
        return [node_id for node_id in self.order if not self.nodes[node_id].parent]

    def is_leaf(self, node_id: str) -> bool:
        return not self.children.get(node_id)

    def ancestors(self, node_id: str) -> list[str]:
        """Parents from the nearest upwards, stopping at a repeat.

        Cycle-safe by construction: a taxonomy whose parents loop is a defect
        (reported as ALN000), and a walk that hangs is not a way to report it.
        """
        chain: list[str] = []
        seen = {node_id}
        current = self.nodes[node_id].parent if node_id in self.nodes else ""
        while current and current in self.nodes and current not in seen:
            chain.append(current)
            seen.add(current)
            current = self.nodes[current].parent
        return chain

    def in_parent_cycle(self, node_id: str) -> bool:
        """True when walking ``parent`` from here comes back to something already seen."""
        seen = {node_id}
        current = self.nodes[node_id].parent if node_id in self.nodes else ""
        while current and current in self.nodes:
            if current in seen:
                return True
            seen.add(current)
            current = self.nodes[current].parent
        return False


def reference_dir(root: Path) -> Path:
    return root / REFERENCE_DIRNAME


def pack_names(root: Path) -> list[str]:
    """Names of the reference packs present, sorted for deterministic reports."""
    base = reference_dir(root)
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir())


def _read_pins(directory: Path) -> tuple[list[ChecksumResult], str]:
    """Verify a pack's pins. Returns ``(results, problem)``.

    ``problem`` non-empty means the pack cannot be verified *at all* -- which is not a
    softer state than a mismatch. The oracle raises in the same situation.
    """
    pin_file = directory / CHECKSUMS_FILENAME
    if not pin_file.is_file():
        return [], f"no {CHECKSUMS_FILENAME}: an unpinned reference pack cannot be verified"
    try:
        text = pin_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [], f"cannot read {CHECKSUMS_FILENAME}: {exc}"

    expected: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, name = line.partition("  ")
        name = name.strip().lstrip("*")  # sha256sum marks binary reads with '*'
        if not name:
            continue
        # Containment, for the same reason PROV008 exists: a pin naming
        # ../../elsewhere would have the verifier confirm a file no reviewer opens.
        if (directory / name).resolve().parent != directory.resolve():
            return [], f"{CHECKSUMS_FILENAME} pins '{name}', which is not a file of this pack"
        expected[name] = digest.strip()

    missing = [name for name in PINNED_FILES if name not in expected]
    if missing:
        return [], f"{CHECKSUMS_FILENAME} does not pin {', '.join(missing)}"

    results: list[ChecksumResult] = []
    for name in sorted(expected):
        path = directory / name
        results.append(
            ChecksumResult(name=name, expected=expected[name], actual=sha256(path) if path.is_file() else "")
        )
    return results, ""


def failed_checksums(directory: Path) -> list[ChecksumResult]:
    results, _problem = _read_pins(directory)
    return [result for result in results if not result.ok]


def _read_yaml(path: Path) -> dsl.Document:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except dsl.YAML_ERRORS as exc:
        return dsl.Document(path=path, data=None, parse_error=str(exc))
    except (OSError, UnicodeDecodeError) as exc:
        return dsl.Document(path=path, data=None, parse_error=str(exc))
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return dsl.Document(path=path, data=None, parse_error="top level of a reference file must be a mapping")
    return dsl.Document(path=path, data=dsl._normalize_scalars(data))


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _text(value: Any) -> str:
    """A prose field, whitespace-collapsed.

    Notes, rationales and descriptions are written as YAML folded scalars, which arrive
    with a trailing newline and the author's line breaks embedded. Those are layout of
    the *source file*, not content, and leaving them in put blank lines through the
    middle of every report. Collapsed once, here, so the rendered and JSON reports
    agree and stay byte-stable.
    """
    return " ".join(_str(value).split())


def load_pack(root: Path, name: str) -> ReferencePack:
    """Load one pack best-effort. Never raises: the report is what says what is wrong."""
    directory = reference_dir(root) / name
    pack = ReferencePack(name=name, directory=directory)

    results, problem = _read_pins(directory)
    pack.checksums = results
    broken = [result for result in results if not result.ok]
    if problem:
        pack.refused = problem
        return pack
    if broken:
        pack.refused = "; ".join(
            f"{result.name}: pinned {result.expected[:16] or '(none)'}..., found "
            f"{result.actual[:16] if result.actual else 'missing file'}"
            for result in broken
        )
        return pack

    model_doc = _read_yaml(directory / MODEL_FILENAME)
    pack.documents.append(model_doc)
    if model_doc.data is not None:
        raw_nodes = model_doc.data.get("nodes")
        for index, item in enumerate(raw_nodes if isinstance(raw_nodes, list) else []):
            locator = f"nodes[{index}]"
            if not isinstance(item, dict) or not item.get("id"):
                continue  # the schema check reports the shape
            node = ReferenceNode(
                id=str(item["id"]),
                name=_str(item.get("name")),
                kind=_str(item.get("kind")),
                parent=_str(item.get("parent")),
                description=_text(item.get("description")),
                external_id=_str(item.get("externalId")),
                locator=locator,
            )
            if node.id in pack.nodes:
                pack.defects.append((f"duplicate reference node id '{node.id}'", locator))
                continue
            pack.nodes[node.id] = node
            pack.order.append(node.id)

    for node_id in pack.order:
        node = pack.nodes[node_id]
        if node.parent and node.parent not in pack.nodes:
            pack.defects.append(
                (f"node '{node_id}' names parent '{node.parent}', which is not a node of this pack", node.locator)
            )
        elif pack.in_parent_cycle(node_id):
            pack.defects.append((f"node '{node_id}' is its own ancestor -- a taxonomy is a hierarchy", node.locator))

    mappings_path = directory / MAPPINGS_FILENAME
    if mappings_path.is_file():
        mapping_doc = _read_yaml(mappings_path)
        pack.documents.append(mapping_doc)
        if mapping_doc.data is not None:
            raw = mapping_doc.data.get("mappings")
            for index, item in enumerate(raw if isinstance(raw, list) else []):
                if not isinstance(item, dict) or not item.get("ref"):
                    continue
                elements = item.get("elements") or []
                pack.mappings.append(
                    NodeMapping(
                        ref=str(item["ref"]),
                        status=_str(item.get("status")),
                        elements=tuple(str(x) for x in elements if isinstance(x, (str, int))),
                        note=_text(item.get("note")),
                        rationale=_text(item.get("rationale")),
                        locator=f"mappings[{index}]",
                    )
                )
    return pack


def load(root: Path, names: list[str] | None = None) -> list[ReferencePack]:
    """Every pack present, or the named ones. Unknown names raise -- a typo in
    ``--reference`` must not read as "that reference has no gaps"."""
    available = pack_names(root)
    if names is None:
        wanted = available
    else:
        unknown = [name for name in names if name not in available]
        if unknown:
            raise ReferenceError(
                f"no reference pack named {', '.join(repr(n) for n in unknown)} under "
                f"{REFERENCE_DIRNAME}/ (present: {', '.join(available) or 'none'})"
            )
        wanted = [name for name in available if name in set(names)]
    return [load_pack(root, name) for name in wanted]


def write_pins(directory: Path) -> list[str]:
    """Rewrite a pack's ``SHA256SUMS``. Deliberate act only -- see ``pin-reference``."""
    missing = [name for name in PINNED_FILES if not (directory / name).is_file()]
    if missing:
        raise ReferenceError(f"{directory} is missing {', '.join(missing)}")
    lines = [f"{sha256(directory / name)}  {name}" for name in PINNED_FILES]
    (directory / CHECKSUMS_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return lines
