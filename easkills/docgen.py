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
from datetime import date as _date
from pathlib import Path

from . import correspond, dsl, genschema, render

# One vocabulary, defined with the schema that enforces it (genschema.TIME_DISPOSITIONS).
TIME_ORDER = genschema.TIME_DISPOSITIONS


@dataclass
class DocsResult:
    path: Path
    views_rendered: list[str] = field(default_factory=list)


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _contested_citations(model: dsl.Model) -> list[tuple[str, str, str]]:
    """(name, type, explanation) for concepts whose evidence is a contested fact.

    Read from the fact register rather than the model: the register is where a
    contradiction is recorded, and a description that quietly presented one side would
    be the single most damaging thing this generator could do.
    """
    from . import facts as facts_mod

    register, _documents, _entities = facts_mod.load(model.root)
    rows: list[tuple[str, str, str]] = []
    for concept in sorted(
        list(model.elements.values()) + list(model.relationships.values()), key=lambda c: c.id
    ):
        for provenance in concept.provenance:
            fact = register.facts.get(provenance.fact) if provenance.fact else None
            if fact is None or fact.confidence != "contested":
                continue
            others = [register.facts.get(ref) for ref in sorted(fact.contests)]
            against = "; ".join(other.statement for other in others if other is not None)
            rows.append(
                (
                    concept.name or concept.id,
                    concept.type,
                    f"modelled on \"{fact.statement}\" -- another source says: {against}"
                    if against
                    else f"modelled on a contested statement: {fact.statement}",
                )
            )
    return rows


def _governance_view(model: dsl.Model) -> tuple[list, list]:
    """(standing decisions, correspondences) for the last two sections.

    Loaded here rather than passed in, so ``build_markdown(model)`` keeps its signature
    and the description stays generated from one argument. The correspondence verdicts
    are evaluated **as of the model's own date**, never the wall clock: a description
    whose bytes changed because a dispensation expired overnight would fail the freshness
    gate on a day nobody touched the repository.
    """
    from . import correspond as correspond_mod, govern as govern_mod

    governance = govern_mod.load(model.root)
    as_of = _as_of(model)
    try:
        today = _date.fromisoformat(as_of)
    except ValueError:
        today = _date.min  # an unreviewed model: nothing has expired yet
    decisions = [
        d
        for d in sorted(governance.decisions.values(), key=lambda d: d.id)
        if d.status in correspond_mod.STANDING_DECISION_STATUSES
    ]
    return decisions, correspond_mod.derive(model, governance, today)


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
    contested = _contested_citations(model)
    if not assumed and not contested:
        out.append("*No declared assumptions -- every concept is source-evidenced.*")
    if assumed:
        out.append(
            "The following concepts are **declared assumptions** (`assumed: true`), not "
            "source-evidenced facts. Each needs confirmation or removal:"
        )
        out.append("")
        for concept in assumed:
            out.append(f"- **{_md_escape(concept.name or concept.id)}** ({concept.type}): {_md_escape(concept.rationale)}")
    if contested:
        # A contradiction between sources is not an assumption -- both sides are quoted --
        # but the model still had to pick one, and that choice belongs in the open where a
        # reader can overturn it.
        out.append("")
        out.append(
            "The sources **disagree** about the following, and this description follows one "
            "side. Each needs confirming with the people who own the systems:"
        )
        out.append("")
        for name, kind, detail in contested:
            out.append(f"- **{_md_escape(name)}** ({kind}): {_md_escape(detail)}")

    # ------------------------------------------------------------------- decisions
    decisions, correspondences = _governance_view(model)
    out += ["", "## 7. Decisions", ""]
    if not decisions:
        out.append("*No decision records -- `governance-log/decisions/` is empty.*")
    else:
        out.append(
            "ISO 42010 §6.10: the decisions this architecture rests on, each with the "
            "rationale the record is required to carry."
        )
        out.append("")
        rows = []
        for decision in decisions:
            rows.append(
                [
                    f"`{decision.id}`",
                    _md_escape(decision.title),
                    decision.status or "—",
                    decision.date or "—",
                    # Never truncated: a clipped rationale is how "because of the audit
                    # finding in" ends up being the recorded reason for a decision.
                    _md_escape(decision.rationale) or "—",
                ]
            )
        out += _table(["Record", "Decision", "Status", "Decided", "Rationale"], rows)

    # -------------------------------------------------------------- correspondences
    out += ["", "## 8. Correspondences", ""]
    out.append(
        "ISO 42010 §6.9: relations between AD elements that no ArchiMate relationship "
        "can express, because they cross out of the model -- into the governance log and "
        "into the fact register. They are derived from what the records already declare, "
        "so this table cannot drift from them, and each is held to a stated rule."
    )
    out.append("")
    if not correspondences:
        out.append("*Nothing relates this model to decisions, standards or evidence yet.*")
    else:
        rows = []
        for rule in correspond.RULES:
            of_kind = [c for c in correspondences if c.kind == rule.kind]
            if not of_kind:
                continue
            violated = [c for c in of_kind if not c.satisfied]
            rows.append(
                [
                    f"`{rule.kind}`",
                    f"{rule.source_kind} → {rule.target_kind}",
                    str(len(of_kind)),
                    f"**{len(violated)}**" if violated else "0",
                    _md_escape(rule.statement),
                ]
            )
        out += _table(["Rule", "Relates", "Count", "Violated", "What must hold"], rows)
        violations = [c for c in correspondences if not c.satisfied]
        if violations:
            out.append("")
            out.append(
                "The following correspondences are **violated**. ISO 42010 §6.8 asks for "
                "known inconsistencies to be recorded, so they are recorded here rather "
                "than left in a report nobody exports:"
            )
            out.append("")
            for violation in violations:
                out.append(
                    f"- **{_md_escape(violation.source)} → {_md_escape(violation.target)}** "
                    f"(`{violation.kind}`, {violation.code}): {_md_escape(violation.detail)}"
                )

    # --------------------------------------------------------------------- roadmap
    out += ["", "## 9. Roadmap", ""]
    plateaus = [e for e in model.elements.values() if e.type == "Plateau"]
    if not plateaus:
        out.append(
            "*No plateaus recorded. This description says what the architecture is, not "
            "where it is going.*"
        )
    else:
        out.append(
            "The Implementation & Migration layer, ordered by `plateauDate`. Plateaus "
            "aggregate what the migration changes; an element carrying a Migrate or "
            "Eliminate disposition that no plateau holds is listed as unscheduled, "
            "because a portfolio decision nothing carries is an intention."
        )
        out.append("")
        membership: dict[str, list[str]] = {}
        plateau_ids = {p.id for p in plateaus}
        for relationship in sorted(model.relationships.values(), key=lambda r: r.id):
            if relationship.source in plateau_ids and relationship.type in {"Aggregation", "Composition"}:
                target = model.elements.get(relationship.target)
                if target is not None:
                    membership.setdefault(relationship.source, []).append(target.name)
        rows = []
        for plateau in sorted(plateaus, key=lambda p: (p.properties.get("plateauDate", "9999"), p.id)):
            rows.append(
                [
                    plateau.properties.get("plateauDate", "**undated**"),
                    _md_escape(plateau.name),
                    ", ".join(sorted(membership.get(plateau.id, []))) or "—",
                    _md_escape(plateau.documentation),
                ]
            )
        out += _table(["Reached", "Plateau", "Holds", "What it is"], rows)

        gaps = [e for e in sorted(model.elements.values(), key=lambda e: e.id) if e.type == "Gap"]
        if gaps:
            out.append("")
            out.append("**Gaps:** " + "; ".join(
                f"**{_md_escape(gap.name)}** — {_md_escape(gap.documentation)}" for gap in gaps
            ))

        scheduled = {
            r.target
            for r in model.relationships.values()
            if r.source in plateau_ids and r.type in {"Aggregation", "Composition"}
        }
        unscheduled = [
            e
            for e in sorted(model.elements.values(), key=lambda e: e.id)
            if e.properties.get("timeDisposition") in {"Migrate", "Eliminate"}
            and e.id not in scheduled
        ]
        if unscheduled:
            out.append("")
            out.append(
                "**Decided but unscheduled:** "
                + ", ".join(
                    f"{_md_escape(e.name)} ({e.properties['timeDisposition']})" for e in unscheduled
                )
                + ". The portfolio decision exists; no plateau carries it."
            )

    out += ["", ""]
    return "\n".join(out)


def generate(root: Path, out: Path | None = None) -> DocsResult:
    """Render all approved views and write the architecture description."""
    model, _documents, _config = dsl.load(root, "approved")
    rendered = render.render_all(root, zone="approved")
    target = out or (root / "docs" / "architecture-description.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_markdown(model), encoding="utf-8", newline="\n")
    return DocsResult(path=target, views_rendered=[view_id for view_id, _path in rendered.views])
