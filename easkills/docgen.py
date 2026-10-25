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

from . import correspond, dsl, genschema, i18n, render

# One vocabulary, defined with the schema that enforces it (genschema.TIME_DISPOSITIONS).
TIME_ORDER = genschema.TIME_DISPOSITIONS


@dataclass
class DocsResult:
    path: Path
    views_rendered: list[str] = field(default_factory=list)


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _contested_citations(model: dsl.Model) -> list[tuple[str, str, str, str]]:
    """(name, type, statement followed, statements against) for concepts whose evidence
    is a contested fact. Formatted by the caller, in the document's language.

    Read from the fact register rather than the model: the register is where a
    contradiction is recorded, and a description that quietly presented one side would
    be the single most damaging thing this generator could do.
    """
    from . import facts as facts_mod

    register, _documents, _entities = facts_mod.load(model.root)
    rows: list[tuple[str, str, str, str]] = []
    for concept in sorted(
        list(model.elements.values()) + list(model.relationships.values()), key=lambda c: c.id
    ):
        for provenance in concept.provenance:
            fact = register.facts.get(provenance.fact) if provenance.fact else None
            if fact is None or fact.confidence != "contested":
                continue
            others = [register.facts.get(ref) for ref in sorted(fact.contests)]
            against = "; ".join(other.statement for other in others if other is not None)
            rows.append((concept.name or concept.id, concept.type, fact.statement, against))
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


def build_markdown(model: dsl.Model, lang: str = i18n.DEFAULT) -> str:
    t = i18n.translator(lang)
    out: list[str] = []
    out.append(t("doc.title", name=model.name))
    out.append("")
    if model.documentation:
        out.append(model.documentation.strip())
        out.append("")
    out.append(
        t(
            "doc.as_of",
            as_of=_as_of(model),
            elements=len(model.elements),
            relationships=len(model.relationships),
            views=len(model.views),
        )
    )
    out.append("")
    out.append(t("doc.generated"))

    # ---------------------------------------------------------------- stakeholders
    out += ["", t("doc.h1"), ""]
    if not model.stakeholders:
        out.append(t("doc.no_stakeholders"))
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
        out += _table([t("doc.col.stakeholder"), t("doc.col.who"), t("doc.col.concerns")], rows)

    # -------------------------------------------------------------------- concerns
    out += ["", t("doc.h2"), ""]
    if not model.concerns:
        out.append(t("doc.no_concerns"))
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
                    ", ".join(held_by.get(concern.id, [])) or t("doc.nobody"),
                    ", ".join(framed_in.get(concern.id, [])) or t("doc.no_view"),
                ]
            )
        out += _table([t("doc.col.concern"), t("doc.col.held_by"), t("doc.col.framed_in")], rows)

    # ----------------------------------------------------------------------- views
    out += ["", t("doc.h3"), ""]
    for view in sorted(model.views.values(), key=lambda v: v.id):
        out.append(f"### {view.name}")
        out.append("")
        meta = []
        if view.viewpoint:
            meta.append(t("doc.viewpoint", value=view.viewpoint))
        concern_texts = [
            _md_escape(model.concerns[c].statement) for c in view.concerns if c in model.concerns
        ]
        if concern_texts:
            meta.append(t("doc.frames") + "; ".join(concern_texts))
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
        out += _table([t("doc.col.element"), t("doc.col.type"), t("doc.col.owner")], rows)
        out.append("")

    # ------------------------------------------------------------------- portfolio
    applications = [
        e
        for e in sorted(model.elements.values(), key=lambda e: e.id)
        if e.type == "ApplicationComponent"
    ]
    out += [t("doc.h4"), ""]
    if not applications:
        out.append(t("doc.no_apps"))
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
            [
                t("doc.col.application"),
                t("doc.col.time"),
                t("doc.col.lifecycle"),
                t("doc.col.functional_fit"),
                t("doc.col.technical_fit"),
                t("doc.col.hosting"),
                t("doc.col.owner"),
            ],
            rows,
        )
        out.append("")
        quadrants: dict[str, list[str]] = {}
        unclassified = t("doc.unclassified")
        for app in applications:
            quadrants.setdefault(app.properties.get("timeDisposition", unclassified), []).append(app.name)
        # Print recognised quadrants in reading order, then anything left over. The
        # leftover bucket matters: iterating a fixed vocabulary silently dropped
        # applications whose disposition was mistyped, and a portfolio summary that
        # quietly omits systems is worse than one that admits it cannot classify them.
        unrecognised = sorted(set(quadrants) - {*TIME_ORDER, unclassified})
        out.append(t("doc.time_quadrants") + " · ".join(
            f"{quadrant}: {', '.join(sorted(quadrants[quadrant]))}"
            for quadrant in (*TIME_ORDER, unclassified, *unrecognised)
            if quadrant in quadrants
        ))
        if unrecognised:
            out.append("")
            out.append(
                t(
                    "doc.not_time",
                    values=", ".join(f"`{value}`" for value in unrecognised),
                    expected=", ".join(TIME_ORDER),
                )
            )

    # ------------------------------------------------------------------ capability
    out += ["", t("doc.h5"), ""]
    capabilities = [
        e for e in sorted(model.elements.values(), key=lambda e: e.id) if e.type == "Capability"
    ]
    if not capabilities:
        out.append(t("doc.no_capabilities"))
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
                    support or t("doc.nothing_realizes"),
                ]
            )
        out += _table([t("doc.col.capability"), t("doc.col.assessment"), t("doc.col.realized_by")], rows)

    # ------------------------------------------------------------------ assumptions
    out += ["", t("doc.h6"), ""]
    assumed = [
        c
        for c in sorted(
            list(model.elements.values()) + list(model.relationships.values()), key=lambda c: c.id
        )
        if c.assumed
    ]
    contested = _contested_citations(model)
    if not assumed and not contested:
        out.append(t("doc.no_assumptions"))
    if assumed:
        out.append(t("doc.assumed_lead"))
        out.append("")
        for concept in assumed:
            out.append(f"- **{_md_escape(concept.name or concept.id)}** ({concept.type}): {_md_escape(concept.rationale)}")
    if contested:
        # A contradiction between sources is not an assumption -- both sides are quoted --
        # but the model still had to pick one, and that choice belongs in the open where a
        # reader can overturn it.
        out.append("")
        out.append(t("doc.contested_lead"))
        out.append("")
        for name, kind, statement, against in contested:
            detail = (
                t("doc.contested_detail", statement=statement, against=against)
                if against
                else t("doc.contested_alone", statement=statement)
            )
            out.append(f"- **{_md_escape(name)}** ({kind}): {_md_escape(detail)}")
    from . import facts as facts_mod  # local, as in _contested_citations

    open_questions = sorted(
        (q for q in facts_mod.load_questions(model.root).values() if q.status == "open"), key=lambda q: q.id
    )
    if open_questions:
        # Questions the sources raised and could not answer. They are not concepts and the
        # model makes no claim about them -- which is exactly why a reader of the
        # description needs to see them: an unanswered question is a known unknown.
        out.append("")
        out.append(t("doc.questions_lead"))
        out.append("")
        for question in open_questions:
            asked = (
                t("doc.asked_of", who=_md_escape(question.addressed_to))
                if question.addressed_to
                else t("doc.nobody_asked")
            )
            where = f"{question.file}" + (t("doc.lines", lines=question.lines) if question.lines else "")
            out.append(
                t(
                    "doc.question_line",
                    question=_md_escape(question.question),
                    quote=_md_escape(question.quote),
                    where=_md_escape(where),
                    raised=question.raised,
                    asked=asked,
                )
            )

    # ------------------------------------------------------------------- decisions
    decisions, correspondences = _governance_view(model)
    out += ["", t("doc.h7"), ""]
    if not decisions:
        out.append(t("doc.no_decisions"))
    else:
        out.append(t("doc.decisions_lead"))
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
        out += _table(
            [t("doc.col.record"), t("doc.col.decision"), t("doc.col.status"), t("doc.col.decided"), t("doc.col.rationale")],
            rows,
        )

    # -------------------------------------------------------------- correspondences
    out += ["", t("doc.h8"), ""]
    out.append(t("doc.corr_lead"))
    out.append("")
    if not correspondences:
        out.append(t("doc.no_correspondences"))
    else:
        rows = []
        for rule in correspond.RULES:
            of_kind = [c for c in correspondences if c.kind == rule.kind]
            if not of_kind:
                continue
            violated = [c for c in of_kind if not c.satisfied]
            # English reads the rule's own text; another language reads the catalogue,
            # which a test holds to the same set of rules.
            relates = f"{rule.source_kind} → {rule.target_kind}" if lang == "en" else t(f"corr.{rule.kind}.relates")
            statement = rule.statement if lang == "en" else t(f"corr.{rule.kind}.statement")
            rows.append(
                [
                    f"`{rule.kind}`",
                    relates,
                    str(len(of_kind)),
                    f"**{len(violated)}**" if violated else "0",
                    _md_escape(statement),
                ]
            )
        out += _table(
            [t("doc.col.rule"), t("doc.col.relates"), t("doc.col.count"), t("doc.col.violated"), t("doc.col.what_must_hold")],
            rows,
        )
        violations = [c for c in correspondences if not c.satisfied]
        if violations:
            out.append("")
            out.append(t("doc.violations_lead"))
            out.append("")
            for violation in violations:
                out.append(
                    f"- **{_md_escape(violation.source)} → {_md_escape(violation.target)}** "
                    f"(`{violation.kind}`, {violation.code}): {_md_escape(violation.detail)}"
                )

    # --------------------------------------------------------------------- roadmap
    out += ["", t("doc.h9"), ""]
    plateaus = [e for e in model.elements.values() if e.type == "Plateau"]
    if not plateaus:
        out.append(t("doc.no_plateaus"))
    else:
        out.append(t("doc.roadmap_lead"))
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
                    plateau.properties.get("plateauDate", t("doc.undated")),
                    _md_escape(plateau.name),
                    ", ".join(sorted(membership.get(plateau.id, []))) or "—",
                    _md_escape(plateau.documentation),
                ]
            )
        out += _table([t("doc.col.reached"), t("doc.col.plateau"), t("doc.col.holds"), t("doc.col.what_it_is")], rows)

        gaps = [e for e in sorted(model.elements.values(), key=lambda e: e.id) if e.type == "Gap"]
        if gaps:
            out.append("")
            out.append(t("doc.gaps") + "; ".join(
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
                t(
                    "doc.unscheduled",
                    items=", ".join(f"{_md_escape(e.name)} ({e.properties['timeDisposition']})" for e in unscheduled),
                )
            )

    out += ["", ""]
    return "\n".join(out)


def generate(root: Path, out: Path | None = None, lang: str = i18n.DEFAULT) -> DocsResult:
    """Render all approved views and write the architecture description in ``lang``.

    The default file name stays the same for English; another language gets its own
    (`architecture-description.pl.md`), so both can be committed side by side and neither
    regeneration overwrites the other.
    """
    model, _documents, _config = dsl.load(root, "approved")
    rendered = render.render_all(root, zone="approved")
    name = "architecture-description.md" if lang == i18n.DEFAULT else f"architecture-description.{lang}.md"
    target = out or (root / "docs" / name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_markdown(model, lang), encoding="utf-8", newline="\n")
    return DocsResult(path=target, views_rendered=[view_id for view_id, _path in rendered.views])
