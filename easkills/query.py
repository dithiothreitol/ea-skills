"""Ask the model a question without writing a script: type, properties, relationship hops.

Every report in this repository answers one fixed question. ``query`` answers the ones
nobody anticipated -- "which public application components hold restricted data", "what
is within two hops of the ledger along Serving", "which requirements bind the CRM" --
over the same loaded model the reports read, and it cannot change anything (D9).

The filter language is deliberately small. ``key=value`` is equality, ``key!=value`` its
negation, ``key~value`` *token membership* in a space-joined value (``regulatoryScope~dora``
matches ``dora gdpr`` -- the lesson 0.15.0 learned the hard way about equality on that
property), and ``key=`` with nothing after it matches an absent or empty value. A key is
a property name, or one of the element's own fields: ``id``, ``type``, ``name``,
``owner``, ``lastReviewed``, ``layer``, ``assumed``.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import dsl, oracle, ui

APPLIES_TO = "appliesTo"  # the motivation binding, walkable like a relationship (AD-09)
DIRECTIONS = ("out", "in", "both")
CONDITION = re.compile(r"^(?P<key>[A-Za-z][A-Za-z0-9_.-]*)(?P<op>!=|=|~)(?P<value>.*)$")


class QueryError(RuntimeError):
    pass


@dataclass(frozen=True)
class Condition:
    key: str
    op: str
    value: str

    def matches(self, element: dsl.Element) -> bool:
        actual = field_value(element, self.key)
        if self.op == "=":
            return actual == self.value
        if self.op == "!=":
            return actual != self.value
        return self.value in actual.split()


def parse_condition(text: str) -> Condition:
    match = CONDITION.match(text.strip())
    if not match:
        raise QueryError(
            f"cannot read the condition {text!r} -- write key=value, key!=value, key~token, or key= for absent"
        )
    return Condition(match["key"], match["op"], match["value"].strip())


def field_value(element: dsl.Element, key: str) -> str:
    own = {
        "id": element.id,
        "type": element.type,
        "name": element.name,
        "owner": element.owner,
        "lastReviewed": element.last_reviewed,
        "layer": oracle.layer_of(element.type) or "",
        "assumed": "true" if element.assumed else "false",
    }
    if key in own:
        return own[key]
    return element.properties.get(key, "")


def _edges(model: dsl.Model, kinds: set[str] | None) -> list[tuple[str, str, str]]:
    """(source, target, kind) for every walkable link, relationships and bindings alike."""
    edges = [
        (r.source, r.target, r.type)
        for r in model.relationships.values()
        if kinds is None or r.type in kinds
    ]
    if kinds is None or APPLIES_TO in kinds:
        edges.extend(
            (e.id, ref, APPLIES_TO) for e in model.elements.values() for ref in e.applies_to
        )
    return edges


def _reach(model: dsl.Model, start: str, hops: int, kinds: set[str] | None, direction: str) -> dict[str, dict[str, Any]]:
    neighbours: dict[str, list[tuple[str, str, str]]] = {}
    for source, target, kind in sorted(_edges(model, kinds)):
        if direction in ("out", "both"):
            neighbours.setdefault(source, []).append((target, kind, "out"))
        if direction in ("in", "both"):
            neighbours.setdefault(target, []).append((source, kind, "in"))
    found: dict[str, dict[str, Any]] = {}
    queue = deque([(start, 0)])
    seen = {start}
    while queue:
        current, depth = queue.popleft()
        if depth == hops:
            continue
        for far, kind, way in neighbours.get(current, []):
            if far in seen or far not in model.elements:
                continue
            seen.add(far)
            found[far] = {"hop": depth + 1, "via": kind, "direction": way, "from": current}
            queue.append((far, depth + 1))
    return found


def run(
    root: Path,
    zone: str = "approved",
    types: list[str] | None = None,
    where: list[str] | None = None,
    start: str | None = None,
    hops: int = 1,
    relations: list[str] | None = None,
    direction: str = "both",
    show: list[str] | None = None,
) -> dict[str, Any]:
    model, _documents, _config = dsl.load_zone(root, zone)
    conditions = [parse_condition(text) for text in where or []]
    known_types = set(oracle.element_types())
    for name in types or []:
        if name not in known_types:
            raise QueryError(f"'{name}' is not an ArchiMate element type (the oracle names {len(known_types)})")
    kinds: set[str] | None = None
    if relations:
        allowed = set(oracle.relationship_types()) | {APPLIES_TO}
        unknown = sorted(set(relations) - allowed)
        if unknown:
            raise QueryError(f"not a relationship type: {', '.join(unknown)} (or '{APPLIES_TO}' for the binding)")
        kinds = set(relations)
    if direction not in DIRECTIONS:
        raise QueryError(f"direction must be one of {', '.join(DIRECTIONS)}")
    if hops < 1:
        raise QueryError("--hops counts steps away from --from, so it starts at 1")

    reached: dict[str, dict[str, Any]] | None = None
    if start is not None:
        if start not in model.elements:
            raise QueryError(f"'{start}' is not an element of the {zone} model")
        reached = _reach(model, start, hops, kinds, direction)
        candidates = [model.elements[i] for i in reached]
    else:
        candidates = list(model.elements.values())

    rows: list[dict[str, Any]] = []
    for element in candidates:
        if types and element.type not in types:
            continue
        if not all(condition.matches(element) for condition in conditions):
            continue
        row: dict[str, Any] = {"id": element.id, "type": element.type, "name": element.name}
        if reached is not None:
            row.update(reached[element.id])
        for key in show or []:
            row[key] = field_value(element, key)
        rows.append(row)
    rows.sort(key=lambda r: (r.get("hop", 0), r["id"]))
    return {
        "zone": zone,
        "query": {
            "types": list(types or []),
            "where": [f"{c.key}{c.op}{c.value}" for c in conditions],
            "from": start,
            "hops": hops if start is not None else None,
            "relations": sorted(kinds) if kinds else [],
            "direction": direction if start is not None else None,
        },
        "count": len(rows),
        "results": rows,
        "show": list(show or []),
    }


def render(data: dict[str, Any]) -> str:
    rows = data["results"]
    if not rows:
        return "No element matches."
    walked = data["query"]["from"] is not None
    columns = ["id", "type", "name"] + (["hop", "via"] if walked else []) + data["show"]
    cells = [[str(row.get(c, "")) for c in columns] for row in rows]
    widths = [max(len(c), *(len(r[i]) for r in cells)) for i, c in enumerate(columns)]
    lines = [ui.dim("  ".join(c.ljust(w) for c, w in zip(columns, widths)).rstrip())]
    for row in cells:
        lines.append("  ".join(v.ljust(w) for v, w in zip(row, widths)).rstrip())
    lines.append("")
    lines.append(f"{data['count']} element(s) in the {data['zone']} model.")
    return "\n".join(lines)
