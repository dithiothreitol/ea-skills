"""Generate the architecture description (ISO/IEC/IEEE 42010 Clause 6 shape) plus
the audience outputs practitioners actually use (application portfolio, capability
support, open assumptions).

Reads **only** the approved zone (AD-02): staging is a proposal, and a document that
mixes proposals with signed content carries false authority. Output is deterministic
markdown -- same model, same bytes -- so the generated description can be committed
and CI can prove it is fresh. The "as of" date is the newest ``lastReviewed`` in the
model, not the wall clock: the document is as fresh as its content, not its build.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import dsl, genschema, render

# One vocabulary, defined with the schema that enforces it (genschema.TIME_DISPOSITIONS).
TIME_ORDER = genschema.TIME_DISPOSITIONS


@dataclass
class DocsResult:
    path: Path
    views_rendered: list[str] = field(default_factory=list)


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _as_of(model: dsl.Model) -> str:
    dates = [e.last_reviewed for e in model.elements.values() if e.last_reviewed]
    return max(dates) if dates else "unreviewed"


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def build_markdown(model: dsl.Model) -> str:
    out: list[str] = []
    out.append(f"# {model.name} — Architecture Description")
    out.append("")
    if model.documentation:
        out.append(model.documentation.strip())
        out.append("")
    out.append(
        f"**As of:** {_as_of(model)} (newest `lastReviewed` in the approved model) · "
        f"{len(model.elements)} elements, {len(model.relationships)} relationships, "
        f"{len(model.views)} views."
    )
    out.append("")
    out.append(
        "> Generated from `model/approved/` by `python -m easkills docs`. Do not edit; "
        "change the model and regenerate. Structured after ISO/IEC/IEEE 42010:2022 "
        "Clause 6 (stakeholders → concerns → viewpoints → views)."
    )

    # ---------------------------------------------------------------- stakeholders
    out += ["", "## 1. Stakeholders and concerns", ""]
    if not model.stakeholders:
        out.append("*No stakeholders are recorded yet -- run the `ea-stakeholders` skill.*")
    else:
        rows = []
        for stakeholder in sorted(model.stakeholders.values(), key=lambda s: s.id):
            concern_texts = [
                _md_escape(model.concerns[c].statement)
                for c in stakeholder.concerns
                if c in model.concerns
            ]
            rows.append(
                [
                    f"**{_md_escape(stakeholder.name)}**",
                    _md_escape(stakeholder.description) or "—",
                    "<br>".join(concern_texts) or "—",
                ]
            )
        out += _table(["Stakeholder", "Who they are", "Concerns"], rows)

    # -------------------------------------------------------------------- concerns
    out += ["", "## 2. Concern coverage", ""]
    if not model.concerns:
        out.append("*No concerns are recorded yet.*")
    else:
        held_by: dict[str, list[str]] = {}
        for stakeholder in sorted(model.stakeholders.values(), key=lambda s: s.id):
            for ref in stakeholder.concerns:
                held_by.setdefault(ref, []).append(stakeholder.name)
        framed_in: dict[str, list[str]] = {}
        for view in sorted(model.views.values(), key=lambda v: v.id):
            for ref in view.concerns:
                framed_in.setdefault(ref, []).append(view.name)
        rows = []
        for concern in sorted(model.concerns.values(), key=lambda c: c.id):
            rows.append(
                [
                    _md_escape(concern.statement),
                    ", ".join(held_by.get(concern.id, [])) or "**nobody**",
                    ", ".join(framed_in.get(concern.id, [])) or "**no view**",
                ]
            )
        out += _table(["Concern", "Held by", "Framed in"], rows)

    # ----------------------------------------------------------------------- views
    out += ["", "## 3. Views", ""]
    for view in sorted(model.views.values(), key=lambda v: v.id):
        out.append(f"### {view.name}")
        out.append("")
        meta = []
        if view.viewpoint:
            meta.append(f"**Viewpoint:** {view.viewpoint}")
        concern_texts = [
            _md_escape(model.concerns[c].statement) for c in view.concerns if c in model.concerns
        ]
        if concern_texts:
            meta.append("**Frames:** " + "; ".join(concern_texts))
        if meta:
            out.append(" · ".join(meta))
            out.append("")
        if view.documentation:
            out.append(view.documentation.strip())
            out.append("")
        out.append(f"![{_md_escape(view.name)}](views/{view.id}.svg)")
        out.append("")
        rows = []
        for element_id in sorted(e for e in view.include if e in model.elements):
            element = model.elements[element_id]
            rows.append(
                [
                    _md_escape(element.name),
                    element.type,
                    _md_escape(element.owner) or "—",
                ]
            )
        out += _table(["Element", "Type", "Owner"], rows)
        out.append("")

    # ------------------------------------------------------------------- portfolio
    applications = [
        e
        for e in sorted(model.elements.values(), key=lambda e: e.id)
        if e.type == "ApplicationComponent"
    ]
    out += ["## 4. Application portfolio", ""]
    if not applications:
        out.append("*No application components in the model.*")
    else:
        rows = []
        for app in applications:
            p = app.properties
            rows.append(
                [
                    _md_escape(app.name),
                    p.get("timeDisposition", "—"),
                    p.get("lifecycle", "—"),
                    p.get("functionalFit", "—"),
                    p.get("technicalFit", "—"),
                    p.get("hosting", "—"),
                    _md_escape(app.owner) or "—",
                ]
            )
        out += _table(
            ["Application", "TIME", "Lifecycle", "Functional fit", "Technical fit", "Hosting", "Owner"],
            rows,
        )
        out.append("")
        quadrants: dict[str, list[str]] = {}
        for app in applications:
            quadrants.setdefault(app.properties.get("timeDisposition", "Unclassified"), []).append(app.name)
        # Print recognised quadrants in reading order, then anything left over. The
        # leftover bucket matters: iterating a fixed vocabulary silently dropped
        # applications whose disposition was mistyped, and a portfolio summary that
        # quietly omits systems is worse than one that admits it cannot classify them.
        unrecognised = sorted(set(quadrants) - {*TIME_ORDER, "Unclassified"})
        out.append("**TIME quadrants:** " + " · ".join(
            f"{quadrant}: {', '.join(sorted(quadrants[quadrant]))}"
            for quadrant in (*TIME_ORDER, "Unclassified", *unrecognised)
            if quadrant in quadrants
        ))
        if unrecognised:
            out.append("")
            out.append(
                "> Not a TIME quadrant: "
                + ", ".join(f"`{value}`" for value in unrecognised)
                + f". Expected one of {', '.join(TIME_ORDER)} -- fix the model, "
                "these applications are not portfolio-classified."
            )

    # ------------------------------------------------------------------ capability
    out += ["", "## 5. Capability support", ""]
    capabilities = [
        e for e in sorted(model.elements.values(), key=lambda e: e.id) if e.type == "Capability"
    ]
    if not capabilities:
        out.append("*No capabilities in the model.*")
    else:
        realizers: dict[str, list[str]] = {}
        for relationship in sorted(model.relationships.values(), key=lambda r: r.id):
            if relationship.type != "Realization":
                continue
            source = model.elements.get(relationship.source)
            target = model.elements.get(relationship.target)
            if source is None or target is None or target.type != "Capability":
                continue
            realizers.setdefault(target.id, []).append(source.name)
        rows = []
        for capability in capabilities:
            support = ", ".join(sorted(realizers.get(capability.id, [])))
            rows.append(
                [
                    _md_escape(capability.name),
                    _md_escape(capability.properties.get("assessment", "")) or "—",
                    support or "**nothing realizes this capability**",
                ]
            )
        out += _table(["Capability", "Assessment", "Realized by"], rows)

    # ------------------------------------------------------------------ assumptions
    out += ["", "## 6. Assumptions and open questions", ""]
    assumed = [
        c
        for c in sorted(
            list(model.elements.values()) + list(model.relationships.values()), key=lambda c: c.id
        )
        if c.assumed
    ]
    if not assumed:
        out.append("*No declared assumptions -- every concept is source-evidenced.*")
    else:
        out.append(
            "The following concepts are **declared assumptions** (`assumed: true`), not "
            "source-evidenced facts. Each needs confirmation or removal:"
        )
        out.append("")
        for concept in assumed:
            out.append(f"- **{_md_escape(concept.name or concept.id)}** ({concept.type}): {_md_escape(concept.rationale)}")

    out += [
        "",
        "---",
        "",
        "*Correspondences (ISO 42010 §6.9) and architecture decisions (§6.10) are kept in "
        "the governance log and joined into this description in a later phase.*",
        "",
    ]
    return "\n".join(out)


def generate(root: Path, out: Path | None = None) -> DocsResult:
    """Render all approved views and write the architecture description."""
    model, _documents, _config = dsl.load(root, "approved")
    rendered = render.render_all(root, zone="approved")
    target = out or (root / "docs" / "architecture-description.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_markdown(model), encoding="utf-8", newline="\n")
    return DocsResult(path=target, views_rendered=[view_id for view_id, _path in rendered.views])
