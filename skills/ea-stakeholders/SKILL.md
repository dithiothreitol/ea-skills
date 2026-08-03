---
name: ea-stakeholders
description: Identify stakeholders and their concerns from the fact register and plan which views will frame them (ISO 42010). Use when asked who the architecture is for, when starting documentation work, when views exist without declared concerns, or when ISO001-ISO006 findings need resolving. Produces the stakeholder/concern register and a view plan.
---

# Stakeholders, concerns and the view plan

ISO 42010's core discipline is a closed loop: every stakeholder holds concerns, every
concern is framed by at least one view, every view exists to frame someone's concern.
The validator enforces the loop (`ISO001`-`ISO006`); your job is to fill it with real
people and real questions.

## Where they come from

**The fact register, not your imagination.** Interview participants, named owners in
inventories, roles the sources mention (auditors, service desk, infrastructure team)
-- these are stakeholder candidates with evidence behind them. The `owner` fields
already in the model tell you who is accountable for what.

A concern is **a question the stakeholder needs the architecture to answer**, phrased
so a view either answers it or visibly fails to:

* good: "How exposed is order capture to a single point of failure?"
* bad: "availability" (not a question), "the CIO cares about IT" (not answerable).

## The register

Stakeholders and concerns live in the model DSL (typically
`model/<zone>/stakeholders.yaml`) and ride the same staging -> approved flow as
everything else:

```yaml
stakeholders:
  - id: stakeholder-cio
    name: CIO
    description: Owns the application portfolio and its budget.
    concerns: [concern-portfolio-rationalisation]

concerns:
  - id: concern-portfolio-rationalisation
    statement: Which applications support which capability, and where is investment or retirement due?
```

Keep it small and true: three stakeholders with confirmed concerns beat ten with
guessed ones. If you are inferring a concern the sources never voice, that is a
clarification question for the stakeholder, not an entry.

## The view plan

For each concern, decide which view frames it and record the mapping on the view:

```yaml
views:
  - id: capability-realization
    concerns: [concern-portfolio-rationalisation]
```

Match concerns to ArchiMate viewpoint styles rather than inventing formats: portfolio
questions -> Capability Map; availability/integration questions -> Layered or
Application Cooperation; obligation questions -> Motivation (requirements with their
`appliesTo` bindings). One view may frame several concerns; a concern may need a new
view -- propose it with an `include` list and hand the modelling to `ea-views`.

## Closing the loop

```bash
python -m easkills validate --root <repo> --zone staging
```

Work the ISO findings honestly: `ISO006` (concern nobody holds) means find the person
or drop the concern; `ISO003` (concern no view frames) means plan a view or record it
as an accepted gap in your report; `ISO005` (view framing nothing) means either the
view earns its place by naming a concern or it is decoration. Do not silence findings
by inventing stakeholders -- an invented stakeholder makes the whole description
untrustworthy.

## Reporting back

List the loop: who -> what they ask -> which view answers it. Then the gaps: concerns
awaiting a view, questions for stakeholders you could not confirm, and views that
still frame nothing and why.
