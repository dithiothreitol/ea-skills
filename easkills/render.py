"""Deterministic SVG rendering of views.

No rendering toolchain is required: the same layered-grid layout the compiler uses
for the exchange file is drawn directly as SVG. That keeps rendering dependency-free,
byte-stable (a re-run produces identical bytes, so committed views diff meaningfully)
and honest -- what the SVG shows is exactly what the model contains, because both are
derived from the same structures.

Notation is deliberately simplified: layer-coloured boxes, solid connections with an
arrowhead, dashed lines for Realization and Specialization. It is a reading aid for
stakeholders, not a substitute for opening the exchange file in a real ArchiMate tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

from . import aoef, dsl, oracle

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


def render_view(model: dsl.Model, view: dsl.View) -> str:
    included = [e for e in view.include if e in model.elements]
    positions = aoef._layout(model, included)

    width = max((x for x, _ in positions.values()), default=0) + aoef.NODE_WIDTH + aoef.MARGIN
    height = max((y for _, y in positions.values()), default=0) + aoef.NODE_HEIGHT + aoef.MARGIN
    title_height = 34
    height += title_height

    lines: list[str] = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}'>",
        "<defs><marker id='arrow' markerWidth='10' markerHeight='8' refX='9' refY='4' orient='auto'>"
        "<path d='M0,0 L10,4 L0,8 z' fill='#555555'/></marker></defs>",
        f"<rect x='0' y='0' width='{width}' height='{height}' fill='#FFFFFF'/>",
        f"<text x='{aoef.MARGIN}' y='22' {FONT} font-size='15' font-weight='bold'>"
        f"{escape(view.name)}</text>",
    ]

    def centre(element_id: str) -> tuple[float, float]:
        x, y = positions[element_id]
        return x + aoef.NODE_WIDTH / 2, y + title_height + aoef.NODE_HEIGHT / 2

    shown = set(included)
    for relationship_id in sorted(model.relationships):
        relationship = model.relationships[relationship_id]
        if relationship.source not in shown or relationship.target not in shown:
            continue
        sx, sy = centre(relationship.source)
        tx, ty = centre(relationship.target)
        gx, gy = positions[relationship.target]
        ex, ey = _clip_to_box(sx, sy, tx, ty, gx, gy + title_height, aoef.NODE_WIDTH, aoef.NODE_HEIGHT)
        dash = " stroke-dasharray='6,4'" if relationship.type in DASHED_RELATIONSHIPS else ""
        lines.append(
            f"<line x1='{sx:.1f}' y1='{sy:.1f}' x2='{ex:.1f}' y2='{ey:.1f}' "
            f"stroke='#555555' stroke-width='1.2'{dash} marker-end='url(#arrow)'>"
            f"<title>{escape(relationship.type)}: {escape(relationship.source)} → "
            f"{escape(relationship.target)}</title></line>"
        )

    # Applicability bindings (appliesTo) are selector links, not relationships:
    # drawn dotted, no arrowhead, so they cannot be misread as ArchiMate semantics.
    for element_id in sorted(shown):
        element = model.elements[element_id]
        for ref in element.applies_to:
            if ref not in shown:
                continue
            sx, sy = centre(element_id)
            tx, ty = centre(ref)
            gx, gy = positions[ref]
            ex, ey = _clip_to_box(sx, sy, tx, ty, gx, gy + title_height, aoef.NODE_WIDTH, aoef.NODE_HEIGHT)
            lines.append(
                f"<line x1='{sx:.1f}' y1='{sy:.1f}' x2='{ex:.1f}' y2='{ey:.1f}' "
                f"stroke='#999999' stroke-width='1' stroke-dasharray='2,3'>"
                f"<title>applies to: {escape(element_id)} → {escape(ref)}</title></line>"
            )

    for element_id in sorted(shown):
        element = model.elements[element_id]
        x, y = positions[element_id]
        y += title_height
        fill = LAYER_FILL.get(oracle.layer_of(element.type), LAYER_FILL["Other"])
        lines.append(
            f"<g><rect x='{x}' y='{y}' width='{aoef.NODE_WIDTH}' height='{aoef.NODE_HEIGHT}' "
            f"rx='3' fill='{fill}' stroke='#777777'/>"
            f"<title>{escape(element.name)} ({escape(element.type)})</title>"
            f"<text x='{x + aoef.NODE_WIDTH / 2}' y='{y + 26}' {FONT} font-size='11' "
            f"text-anchor='middle'>{escape(_truncate(element.name, 24))}</text>"
            f"<text x='{x + aoef.NODE_WIDTH / 2}' y='{y + 42}' {FONT} font-size='9' "
            f"fill='#555555' text-anchor='middle'>{escape(element.type)}</text></g>"
        )

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def render_all(root: Path, zone: str = "approved", out_dir: Path | None = None) -> RenderResult:
    """Render every view of the zone to ``docs/views/<id>.svg`` (path-sorted, stable)."""
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
        path = target_dir / f"{view.id}.svg"
        path.write_text(render_view(model, view), encoding="utf-8", newline="\n")
        result.views.append((view.id, path))
    return result
