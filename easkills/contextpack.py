"""Agent context packs (AD-09): scoped, generated extracts of the approved model
for the coding and requirements agents working in downstream system repositories.

Principles enforced here, not left to convention:

* **Approved-only** (AD-02): a pack never contains staging content.
* **Scope-filtered**: agents get what binds *their* system, never the raw EA repo.
* **Freshness is on the label**: every pack opens with the review state of its
  content. A stale model served as "binding constraints" carries false authority,
  which is worse than no context -- so the warning is not optional.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import dsl, govern


class ContextError(RuntimeError):
    pass


@dataclass
class ContextPack:
    scope: str
    markdown: str


def _age_state(element: dsl.Element, threshold: int, today: date) -> str:
    if not element.last_reviewed:
        return "never reviewed"
    try:
        reviewed = datetime.strptime(element.last_reviewed, "%Y-%m-%d").date()
    except ValueError:
        return "invalid review date"
    age = (today - reviewed).days
    return f"stale ({age} days since review)" if age > threshold else f"reviewed {element.last_reviewed}"


def build(root: Path, scope: str, today: date | None = None) -> ContextPack:
    today = today or date.today()
    model, _documents, config = dsl.load(root, "approved")
    governance = govern.load(root)
    threshold = int(config.get("stalenessDays", 365))

    if scope not in model.elements:
        raise ContextError(f"'{scope}' is not an element in the approved model")

    # A capability scope expands to the elements realizing it.
    focus_ids = [scope]
    if model.elements[scope].type == "Capability":
        focus_ids += sorted(
            r.source
            for r in model.relationships.values()
            if r.type == "Realization" and r.target == scope and r.source in model.elements
        )
    focus = [model.elements[i] for i in focus_ids]
    focus_set = set(focus_ids)

    # Capabilities the focused elements realize widen which motivation bindings apply.
    realized_capabilities = {
        r.target
        for r in model.relationships.values()
        if r.type == "Realization" and r.source in focus_set and r.target in model.elements
        and model.elements[r.target].type == "Capability"
    }
    binding_targets = focus_set | realized_capabilities

    out: list[str] = [f"# EA context: {model.elements[scope].name}", ""]
    out.append(
        f"Scope `{scope}` in **{model.name}**, generated from the approved model only. "
        "Constraints below are binding unless a listed dispensation says otherwise."
    )
    out.append("")

    flagged = [e for e in focus if "stale" in _age_state(e, threshold, today) or not e.last_reviewed]
    if flagged:
        out.append(
            "> **⚠ Freshness warning:** "
            + "; ".join(f"`{e.id}` is {_age_state(e, threshold, today)}" for e in flagged)
            + f" (threshold {threshold} days). Treat this pack as advisory and confirm with the owner "
            "before relying on it."
        )
    else:
        newest = max((e.last_reviewed for e in focus if e.last_reviewed), default="unknown")
        out.append(f"> Content reviewed up to **{newest}** (threshold {threshold} days) -- current.")
    out.append("")

    out.append("## The system")
    out.append("")
    for element in focus:
        out.append(f"### {element.name} (`{element.id}`, {element.type})")
        if element.documentation:
            out.append(element.documentation.strip())
        out.append(f"- Owner: **{element.owner or 'unassigned'}** · {_age_state(element, threshold, today)}")
        for key in sorted(element.properties):
            out.append(f"- {key}: {element.properties[key]}")
        out.append("")

    out.append("## Binding requirements, constraints and principles")
    out.append("")
    bindings = [
        e
        for e in sorted(model.elements.values(), key=lambda e: e.id)
        if e.applies_to and set(e.applies_to) & binding_targets
    ]
    if bindings:
        for binding in bindings:
            bound_via = sorted(set(binding.applies_to) & binding_targets)
            out.append(f"- **{binding.name}** ({binding.type}, `{binding.id}`; binds {', '.join(f'`{b}`' for b in bound_via)})")
            if binding.documentation:
                out.append(f"  {binding.documentation.strip()}")
    else:
        out.append("*None recorded. Absence of a listed constraint is not permission -- ask the EA team.*")
    out.append("")

    out.append("## Standards")
    out.append("")
    any_standard = False
    for element in focus:
        for ref in element.standards:
            any_standard = True
            standard = governance.standards.get(ref)
            if standard is None:
                out.append(f"- `{ref}` -- **unknown standard** (model error; do not build against it)")
                continue
            note = f"**{standard.lifecycle}**"
            if standard.lifecycle in {"deprecated", "retired"}:
                covering = governance.covering(element.id, ref, today)
                if covering:
                    note += f", waived for `{element.id}` by `{covering.id}` until {covering.expires}"
                elif standard.successor:
                    note += f", migrate to `{standard.successor}`"
            out.append(f"- **{standard.name}** (`{ref}`, {standard.type}): {note}")
    if not any_standard:
        out.append("*No standards recorded against this scope.*")
    out.append("")

    out.append("## Integration context")
    out.append("")
    any_relationship = False
    for relationship in sorted(model.relationships.values(), key=lambda r: r.id):
        if relationship.source in focus_set and relationship.target in model.elements and relationship.target not in focus_set:
            other = model.elements[relationship.target]
            out.append(f"- {relationship.type} → **{other.name}** (`{other.id}`, {other.type}; owner {other.owner or '-'})")
            any_relationship = True
        elif relationship.target in focus_set and relationship.source in model.elements and relationship.source not in focus_set:
            other = model.elements[relationship.source]
            out.append(f"- {relationship.type} ← **{other.name}** (`{other.id}`, {other.type}; owner {other.owner or '-'})")
            any_relationship = True
    if not any_relationship:
        out.append("*No relationships beyond this scope.*")
    out.append("")

    decisions = [
        d
        for d in sorted(governance.decisions.values(), key=lambda d: d.id)
        if set(d.related_elements) & binding_targets
    ]
    out.append("## Decisions that apply here")
    out.append("")
    if decisions:
        for decision in decisions:
            out.append(f"- **{decision.title}** (`{decision.id}`, {decision.status}, {decision.date})")
            out.append(f"  {decision.decision.strip()}")
    else:
        out.append("*No recorded decisions name this scope.*")
    out.append("")

    dispensations = [
        d
        for d in sorted(governance.dispensations.values(), key=lambda d: d.id)
        if set(d.applies_to) & focus_set and d.is_open(today)
    ]
    out.append("## Open dispensations")
    out.append("")
    if dispensations:
        for dispensation in dispensations:
            waived = dispensation.waives_standard or dispensation.waives_rule
            out.append(
                f"- `{dispensation.id}` waives `{waived}` until **{dispensation.expires}** "
                f"(granted by {dispensation.granted_by}). After that date the waiver is void."
            )
    else:
        out.append("*None. Deviating from a standard requires filing one first, not deviating quietly.*")
    out.append("")

    out.append(
        "---\n\n*Generated by `python -m easkills context`. If reality no longer matches this pack, "
        "report the drift back to the EA repository (delta ingestion) instead of working around it.*"
    )
    return ContextPack(scope=scope, markdown="\n".join(out) + "\n")
