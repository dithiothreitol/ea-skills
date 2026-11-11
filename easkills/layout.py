"""The view layout both the exchange file and the SVG are drawn from (D12, 0.22.0).

Views declare content, never geometry: a person or a model hand-placing coordinates turns
every diff into a diff about pixels. Until 0.22.0 the computed layout was one fixed grid --
a band per ArchiMate layer, six columns, every box the same size, every connection a
straight line through whatever stood in its way. A 300-element view was a 1035x5279 px
grid, and a component composed into a server sat beside it with an arrow.

Three content-shaped decisions are now the layout's, and none of them is a coordinate:

* **Nesting.** A part is drawn inside its whole when both are in the view and the model
  says so -- ``Composition`` first, then ``Aggregation``, one whole per part, never in a
  cycle. The nesting *is* the relationship's notation, so that one relationship is not
  drawn again as a connection (``nested``); every other relationship still is.
* **Hints**, declared on the view and closed by the schema (``layout:``): ``groupBy`` --
  ``layer`` (the default) or any element property, one band per value, so a portfolio view
  can be read by TIME disposition; ``columns`` -- how wide a band wraps (default six);
  ``order`` -- the reading order of the elements it names, the rest following by id.
  ``VIEW001`` reports an ``order`` entry the view does not include.
* **Routing.** A connection leaves the bottom (or top) of its source, runs along the gutter
  between bands, crosses intermediate bands through a vertical channel no box occupies,
  and enters its target from the gutter beside it -- orthogonal segments that do not pass
  through boxes. The bend points are written into the exchange file too.

Pixels stay computed, from the same function, so the SVG and the exchange file cannot
disagree. Same model, same bytes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from . import genschema, oracle, query

if TYPE_CHECKING:  # pragma: no cover
    from . import dsl

NODE_WIDTH = 145
NODE_HEIGHT = 60
GAP_X = 25
GAP_Y = 45
MARGIN = 20
COLUMNS = 6
HEADER = 34  # room for a container's own name above its parts
PAD = 10
INNER_COLUMNS = 3
CONTAINMENT = ("Composition", "Aggregation")
NO_VALUE = ""  # the band of elements a groupBy property leaves empty


@dataclass
class Box:
    id: str
    x: int = 0
    y: int = 0
    w: int = NODE_WIDTH
    h: int = NODE_HEIGHT
    parent: str | None = None
    band: int = 0
    children: list[str] = field(default_factory=list)

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def right(self) -> int:
        return self.x + self.w


@dataclass
class Layout:
    boxes: dict[str, Box]
    bands: list[tuple[int, int]]  # (top, bottom) of each row of top-level boxes
    nested: set[str]  # relationship ids drawn as nesting, not as connections
    width: int
    height: int

    def depth(self, element_id: str) -> int:
        depth, box = 0, self.boxes[element_id]
        while box.parent is not None:
            depth, box = depth + 1, self.boxes[box.parent]
        return depth

    def ancestors(self, element_id: str) -> set[str]:
        found, box = set(), self.boxes[element_id]
        while box.parent is not None:
            found.add(box.parent)
            box = self.boxes[box.parent]
        return found

    def route(self, source: str, target: str) -> list[tuple[float, float]]:
        """Orthogonal polyline from ``source`` to ``target`` through the gutters, or [] for a loop."""
        if source == target:
            return []
        s, t = self.boxes[source], self.boxes[target]
        s_top, s_bottom = self.bands[s.band]
        t_top, t_bottom = self.bands[t.band]
        if t.band == s.band:
            gutter = s_bottom + GAP_Y / 2
            points = [(s.cx, s.bottom), (s.cx, gutter), (t.cx, gutter), (t.cx, t.bottom)]
        elif t.band > s.band:
            leave, arrive = s_bottom + GAP_Y / 2, t_top - GAP_Y / 2
            channel = self._channel(s.band + 1, t.band, (s.cx + t.cx) / 2, s.cx, t.cx)
            points = [(s.cx, s.bottom), (s.cx, leave), (channel, leave), (channel, arrive), (t.cx, arrive), (t.cx, t.y)]
        else:
            leave, arrive = s_top - GAP_Y / 2, t_bottom + GAP_Y / 2
            channel = self._channel(t.band + 1, s.band, (s.cx + t.cx) / 2, s.cx, t.cx)
            points = [(s.cx, s.y), (s.cx, leave), (channel, leave), (channel, arrive), (t.cx, arrive), (t.cx, t.bottom)]
        return _simplify(points)

    def _channel(self, first_band: int, end_band: int, prefer: float, *keep: float) -> float:
        """An x crossing bands ``first_band..end_band-1`` without entering a box."""
        blocking = [b for b in self.boxes.values() if b.parent is None and first_band <= b.band < end_band]
        if not blocking:
            return prefer if not keep else min(keep, key=lambda x: abs(x - prefer))
        candidates = {MARGIN / 2, *keep}
        for box in blocking:
            candidates |= {box.x - GAP_X / 2, box.right + GAP_X / 2}
        free = [x for x in candidates if not any(box.x <= x <= box.right for box in blocking)]
        return min(free, key=lambda x: (abs(x - prefer), x))


def _simplify(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for point in points:
        if out and point == out[-1]:
            continue
        if len(out) >= 2:
            (ax, ay), (bx, by) = out[-2], out[-1]
            if (ax == bx == point[0]) or (ay == by == point[1]):
                out[-1] = point  # collinear: the middle point is no bend
                continue
        out.append(point)
    return out


def _vocabulary(key: str) -> list[str]:
    spec = genschema.load_schema()["$defs"]["element"]["properties"]["properties"]["properties"].get(key, {})
    return [str(value) for value in spec.get("enum", [])]


def hints(view: "dsl.View") -> dict:
    return view.layout if isinstance(view.layout, dict) else {}


def compute(model: "dsl.Model", view: "dsl.View") -> Layout:
    included = [e for e in dict.fromkeys(view.include) if e in model.elements]
    shown = set(included)
    settings = hints(view)
    order = [e for e in settings.get("order") or [] if e in shown]
    rank = {element_id: index for index, element_id in enumerate(order)}

    def reading(ids: list[str]) -> list[str]:
        return sorted(ids, key=lambda e: (0, rank[e]) if e in rank else (1, e))

    # --- nesting: one whole per part, Composition before Aggregation, never a cycle ------
    parent: dict[str, str] = {}
    nested: set[str] = set()
    containment = sorted(
        (r for r in model.relationships.values() if r.type in CONTAINMENT),
        key=lambda r: (CONTAINMENT.index(r.type), r.source, r.target, r.id),
    )
    for relationship in containment:
        whole, part = relationship.source, relationship.target
        if whole not in shown or part not in shown or whole == part:
            continue
        if parent.get(part) == whole:
            nested.add(relationship.id)
            continue
        if part in parent:
            continue
        cursor, cycle = whole, False
        while cursor in parent:
            cursor = parent[cursor]
            if cursor == part:
                cycle = True
                break
        if not cycle:
            parent[part] = whole
            nested.add(relationship.id)

    boxes = {element_id: Box(element_id, parent=parent.get(element_id)) for element_id in included}
    for element_id in included:
        if element_id in parent:
            boxes[parent[element_id]].children.append(element_id)
    for box in boxes.values():
        box.children = reading(box.children)

    def size(element_id: str) -> tuple[int, int]:
        box = boxes[element_id]
        if not box.children:
            return box.w, box.h
        sizes = [size(child) for child in box.children]
        rows = [sizes[i : i + INNER_COLUMNS] for i in range(0, len(sizes), INNER_COLUMNS)]
        width = max(sum(w for w, _ in row) + GAP_X * (len(row) - 1) for row in rows)
        height = sum(max(h for _, h in row) for row in rows) + PAD * (len(rows) - 1)
        box.w, box.h = max(NODE_WIDTH, width + 2 * PAD), HEADER + height + PAD
        return box.w, box.h

    top_level = [e for e in included if e not in parent]
    for element_id in top_level:
        size(element_id)

    # --- bands: one group per layer (or property value), wrapped at `columns` ----------
    group_by = str(settings.get("groupBy") or "layer")
    columns = int(settings.get("columns") or COLUMNS)
    if group_by == "layer":
        def key(element_id: str):
            return oracle.LAYER_ORDER.index(oracle.layer_of(model.elements[element_id].type))
        group_order = list(range(len(oracle.LAYER_ORDER)))
    else:
        values = {query.field_value(model.elements[e], group_by) for e in top_level}
        vocabulary = _vocabulary(group_by)
        group_order = [v for v in vocabulary if v in values] + sorted(values - set(vocabulary) - {NO_VALUE})
        group_order += [NO_VALUE] if NO_VALUE in values else []

        def key(element_id: str):
            return query.field_value(model.elements[element_id], group_by)

    groups: dict = {}
    for element_id in top_level:
        groups.setdefault(key(element_id), []).append(element_id)

    bands: list[tuple[int, int]] = []
    y = MARGIN
    for group in group_order:
        members = reading(groups.get(group, []))
        if not members:
            continue
        for start in range(0, len(members), columns):
            row = members[start : start + columns]
            x = MARGIN
            height = max(boxes[e].h for e in row)
            for element_id in row:
                box = boxes[element_id]
                box.x, box.y, box.band = x, y, len(bands)
                x += box.w + GAP_X
            bands.append((y, y + height))
            y += height + GAP_Y
        y += GAP_Y

    def place_children(element_id: str) -> None:
        box = boxes[element_id]
        rows = [box.children[i : i + INNER_COLUMNS] for i in range(0, len(box.children), INNER_COLUMNS)]
        cy = box.y + HEADER
        for row in rows:
            cx = box.x + PAD
            for child_id in row:
                child = boxes[child_id]
                child.x, child.y, child.band = cx, cy, box.band
                cx += child.w + GAP_X
                place_children(child_id)
            cy += max(boxes[c].h for c in row) + PAD

    for element_id in top_level:
        place_children(element_id)

    width = max((b.right for b in boxes.values()), default=0) + MARGIN
    # A connection between two boxes of one band runs in the gutter below it, so the last
    # band needs its gutter on the canvas too -- or the route is drawn off the page.
    height = max((b.bottom for b in boxes.values()), default=0) + GAP_Y
    return Layout(boxes=boxes, bands=bands, nested=nested, width=width, height=height)
