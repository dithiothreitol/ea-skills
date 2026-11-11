"""Deterministic SVG rendering of views.

No rendering toolchain is required: the same layout the compiler writes into the
exchange file (``layout.py``: bands, nesting, hints, gutter routing) is drawn directly as
SVG. That keeps rendering dependency-free,
byte-stable (a re-run produces identical bytes, so committed views diff meaningfully)
and honest -- what the SVG shows is exactly what the model contains, because both are
derived from the same structures.

Notation is deliberately simplified: layer-coloured boxes, a part drawn inside its whole
(the Composition or Aggregation it stands for is not drawn twice), orthogonal connections
with an arrowhead, dashed for Realization and Specialization. It is a reading aid for
stakeholders, not a substitute for opening the exchange file in a real ArchiMate tool.

``--heatmap <property>`` colours the same boxes by one property instead of by layer --
lifecycle, TIME disposition, criticality, owner -- with a legend that counts each value
and names the elements carrying none. A heatmap is written beside the view
(``<view>.heatmap-<property>.svg``), never over it, so the committed views stay what the
freshness check compares.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

from . import dsl, genschema, layout, oracle, query

# Archi-like layer fills, so anyone who has seen an ArchiMate diagram reads these.
LAYER_FILL = {
    "Strategy": "#F5DEAA",
    "Business": "#FFFFB5",
    "Application": "#B5FFFF",
    "Technology": "#C9E7B7",
    "Physical": "#C9E7B7",
    "Motivation": "#CCCCFF",
    "Implementation": "#FFE0E0",
    "Other": "#EEEEEE",
}

DASHED_RELATIONSHIPS = {"Realization", "Specialization"}

# Light, distinguishable fills that keep black text readable (ColorBrewer Set3). A value
# keeps its colour across every view: a closed vocabulary assigns by its schema order, a
# free one by sorted value over the whole model.
HEATMAP_PALETTE = (
    "#8DD3C7", "#FFFFB3", "#BEBADA", "#FB8072", "#80B1D3", "#FDB462",
    "#B3DE69", "#FCCDE5", "#D9D9D9", "#BC80BD", "#CCEBC5", "#FFED6F",
)
NO_VALUE_FILL = "#FFFFFF"
NAME_LIMIT = 24
LEGEND_ROW = 18
FONT = "font-family='Segoe UI, Arial, sans-serif'"


class RenderError(RuntimeError):
    pass


@dataclass
class RenderResult:
    out_dir: Path
    views: list[tuple[str, Path]] = field(default_factory=list)  # (view id, file)


def _clip_to_box(x1: float, y1: float, x2: float, y2: float, bx: float, by: float, bw: float, bh: float) -> tuple[float, float]:
    """Point where the line from (x1,y1) to the box centre (x2,y2) meets the box edge."""
    dx, dy = x1 - x2, y1 - y2
    if dx == 0 and dy == 0:
        return x2, y2
    scale = float("inf")
    if dx:
        scale = min(scale, (bw / 2) / abs(dx))
    if dy:
        scale = min(scale, (bh / 2) / abs(dy))
    return x2 + dx * scale, y2 + dy * scale


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _wrap(text: str, limit: int = NAME_LIMIT) -> list[str]:
    """A name on one line if it fits, otherwise two -- broken at a space where there is
    one -- and only the second line is ever cut short. Truncating at 24 characters made
    "Warehouse Management Sys…" the name a stakeholder read."""
    if len(text) <= limit:
        return [text]
    cut = text.rfind(" ", 0, limit + 1)
    first, rest = (text[:limit], text[limit:]) if cut <= 0 else (text[:cut], text[cut + 1 :])
    return [first, _truncate(rest, limit)]


def _vocabulary(key: str) -> list[str]:
    spec = genschema.load_schema()["$defs"]["element"]["properties"]["properties"]["properties"].get(key, {})
    return [str(v) for v in spec.get("enum", [])]


def heatmap_colours(model: dsl.Model, key: str) -> dict[str, str]:
    """Value -> fill for one property, stable across views of the same model."""
    order = _vocabulary(key)
    present = sorted({query.field_value(e, key) for e in model.elements.values()} - {""})
    values = order + [v for v in present if v not in order]
    return {value: HEATMAP_PALETTE[index % len(HEATMAP_PALETTE)] for index, value in enumerate(values)}


def _points(points: list[tuple[float, float]], dy: float) -> str:
    return " ".join(f"{x:.1f},{y + dy:.1f}" for x, y in points)


def render_view(model: dsl.Model, view: dsl.View, heatmap: str | None = None) -> str:
    plan = layout.compute(model, view)
    title_height = 34
    width = plan.width
    height = plan.height + title_height
    colours = heatmap_colours(model, heatmap) if heatmap else {}
    counts: dict[str, int] = {}
    legend_top = height
    if heatmap:
        for element_id in sorted(plan.boxes):
            value = query.field_value(model.elements[element_id], heatmap)
            counts[value] = counts.get(value, 0) + 1
        height += 10 + LEGEND_ROW * len(counts)
        width = max(width, 320)
    title = f"{view.name} — {heatmap}" if heatmap else view.name

    lines: list[str] = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}'>",
        "<defs><marker id='arrow' markerWidth='10' markerHeight='8' refX='9' refY='4' orient='auto'>"
        "<path d='M0,0 L10,4 L0,8 z' fill='#555555'/></marker></defs>",
        f"<rect x='0' y='0' width='{width}' height='{height}' fill='#FFFFFF'/>",
        f"<text x='{layout.MARGIN}' y='22' {FONT} font-size='15' font-weight='bold'>"
        f"{escape(title)}</text>",
    ]

    def centre(element_id: str) -> tuple[float, float]:
        box = plan.boxes[element_id]
        return box.cx, box.y + title_height + box.h / 2

    # Boxes first, outermost first, so a part is drawn on top of its whole; connections
    # after, so a route is never hidden under the box it runs beside.
    for element_id in sorted(plan.boxes, key=lambda e: (plan.depth(e), e)):
        element = model.elements[element_id]
        box = plan.boxes[element_id]
        x, y = box.x, box.y + title_height
        dash = ""
        if heatmap:
            value = query.field_value(element, heatmap)
            fill = colours.get(value, NO_VALUE_FILL)
            dash = "" if value else " stroke-dasharray='4,3'"
            tooltip = f"{element.name} ({element.type}) -- {heatmap}: {value or 'no value'}"
        else:
            fill = LAYER_FILL.get(oracle.layer_of(element.type), LAYER_FILL["Other"])
            tooltip = f"{element.name} ({element.type})"
        centre_x = box.cx
        if box.children:
            # A whole holding its parts: its name in the header, above them.
            name_svg = (
                f"<text x='{centre_x}' y='{y + 15}' {FONT} font-size='11' "
                f"text-anchor='middle'>{escape(_truncate(element.name, NAME_LIMIT + 8))}</text>"
            )
            type_y = y + 27
        else:
            name_lines = _wrap(element.name)
            if len(name_lines) == 1:
                name_svg = (
                    f"<text x='{centre_x}' y='{y + 26}' {FONT} font-size='11' "
                    f"text-anchor='middle'>{escape(name_lines[0])}</text>"
                )
                type_y = y + 42
            else:
                name_svg = "".join(
                    f"<text x='{centre_x}' y='{y + offset}' {FONT} font-size='11' "
                    f"text-anchor='middle'>{escape(line)}</text>"
                    for offset, line in zip((20, 33), name_lines)
                )
                type_y = y + 48
        lines.append(
            f"<g><rect x='{x}' y='{y}' width='{box.w}' height='{box.h}' "
            f"rx='3' fill='{fill}' stroke='#777777'{dash}/>"
            f"<title>{escape(tooltip)}</title>"
            f"{name_svg}"
            f"<text x='{centre_x}' y='{type_y}' {FONT} font-size='9' "
            f"fill='#555555' text-anchor='middle'>{escape(element.type)}</text></g>"
        )

    shown = set(plan.boxes)
    for relationship_id in sorted(model.relationships):
        relationship = model.relationships[relationship_id]
        if relationship.source not in shown or relationship.target not in shown:
            continue
        if relationship.id in plan.nested:
            continue  # the nesting is this relationship's notation
        route = plan.route(relationship.source, relationship.target)
        if not route:
            continue
        dash = " stroke-dasharray='6,4'" if relationship.type in DASHED_RELATIONSHIPS else ""
        lines.append(
            f"<polyline points='{_points(route, title_height)}' fill='none' "
            f"stroke='#555555' stroke-width='1.2'{dash} marker-end='url(#arrow)'>"
            f"<title>{escape(relationship.type)}: {escape(relationship.source)} → "
            f"{escape(relationship.target)}</title></polyline>"
        )

    # Applicability bindings (appliesTo) are selector links, not relationships:
    # drawn dotted and straight, no arrowhead, so they cannot be misread as ArchiMate
    # semantics -- and never routed like a relationship.
    for element_id in sorted(shown):
        element = model.elements[element_id]
        for ref in element.applies_to:
            if ref not in shown or ref == element_id:
                continue
            sx, sy = centre(element_id)
            tx, ty = centre(ref)
            target = plan.boxes[ref]
            ex, ey = _clip_to_box(sx, sy, tx, ty, target.x, target.y + title_height, target.w, target.h)
            lines.append(
                f"<line x1='{sx:.1f}' y1='{sy:.1f}' x2='{ex:.1f}' y2='{ey:.1f}' "
                f"stroke='#999999' stroke-width='1' stroke-dasharray='2,3'>"
                f"<title>applies to: {escape(element_id)} → {escape(ref)}</title></line>"
            )

    if heatmap:
        ordered = [v for v in colours if v in counts] + ([""] if "" in counts else [])
        for row, value in enumerate(ordered):
            top = legend_top + 4 + row * LEGEND_ROW
            dash = " stroke-dasharray='4,3'" if not value else ""
            label = value or "no value"
            lines.append(
                f"<g><rect x='{layout.MARGIN}' y='{top}' width='14' height='12' "
                f"fill='{colours.get(value, NO_VALUE_FILL)}' stroke='#777777'{dash}/>"
                f"<text x='{layout.MARGIN + 20}' y='{top + 10}' {FONT} font-size='11'>"
                f"{escape(label)} ({counts[value]})</text></g>"
            )

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def render_all(
    root: Path, zone: str = "approved", out_dir: Path | None = None, heatmap: str | None = None
) -> RenderResult:
    """Render every view of the zone to ``docs/views/<id>.svg`` (path-sorted, stable),
    or with ``heatmap`` to ``<id>.heatmap-<property>.svg`` beside it."""
    # load_zone, not load: 'staging' is the overlay, so a delta renders against the
    # approved model it proposes to change instead of reporting "no views".
    model, _documents, _config = dsl.load_zone(root, zone)
    target_dir = out_dir or (root / "docs" / "views")
    target_dir.mkdir(parents=True, exist_ok=True)
    result = RenderResult(out_dir=target_dir)
    for view_id in sorted(model.views):
        view = model.views[view_id]
        missing = [e for e in view.include if e not in model.elements]
        if missing:
            raise RenderError(
                f"view '{view.id}' includes unknown element(s) {missing}; validate before rendering"
            )
        name = f"{view.id}.heatmap-{heatmap}.svg" if heatmap else f"{view.id}.svg"
        path = target_dir / name
        path.write_text(render_view(model, view, heatmap), encoding="utf-8", newline="\n")
        result.views.append((view.id, path))
    return result
