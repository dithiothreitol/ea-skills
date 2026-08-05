---
name: ea-change-triage
description: Classify an incoming architecture change request (TOGAF Phase H) and route it - simplification, incremental, or re-architecting. Use when a change request, new demand or drift report arrives and someone asks what to do with it, or whether a change "needs architecture".
---

# Change triage (Phase H)

Every change request gets classified before anyone models anything. The three
classes, and what each routes to:

| Class | Test | Route |
|---|---|---|
| **Simplification** | Reduces or removes something; no new capability; stakeholders unaffected or relieved | Maintenance: `ea-delta-ingest` proposes the model update; promote; done |
| **Incremental** | Extends within the current architecture's assumptions; ≤1 stakeholder group materially impacted | Maintenance with governance: delta ingest + compliance assessment of the implementing project; a dispensation if it bends a standard |
| **Re-architecting** | Invalidates an assumption, decision or capability boundary; **≥2 stakeholder groups impacted** | Re-enter the pipeline properly: intake on the new drivers, stakeholder/concern update, modelling, views, decision records -- not a quick patch |

The stakeholder-impact test is the load-bearing one, and **the tooling counts it for
you** -- do not eyeball it:

```bash
python -m easkills impact --root <repo> --scope <element-id>
```

The report gives the blast radius (transitive, nearest-first, with the relationship
each hop travelled), the stakeholder groups reached through views and concerns, and
the decisions, obligations, waivers and consumer requests inside the radius. Two or
more stakeholder groups means re-architecting, however small the change feels
technically.

Impact travels along declared directions, not along whichever way a relationship was
written: `Serving`/`Realization`/`Assignment`/`Triggering`/`Flow` carry it forward,
`Access`/`Specialization` backward, `Composition`/`Aggregation` both ways.
**`Association` is never traversed** -- ArchiMate leaves its meaning to the modeller,
so those neighbours are listed separately as adjacency of unknown direction. If one of
them matters for this change, that is a modelling finding: replace the association
with the relationship that was meant.

Use `--scope` on the element the change actually touches, and `--depth 1` first if the
radius is large; the unbounded run is the honest one for a re-architecting call.

## Discipline

* **Triage against the approved model**, not against memory of it. If the affected
  area is not modelled, that is itself a finding -- route through intake first.
* **The count is arithmetic; the class is not.** `impact` evaluates one of the three
  tests. Whether the change invalidates a recorded assumption, decision or capability
  boundary is judgement, and the report says so rather than pretending otherwise --
  read the decisions it lists and answer that half yourself.
* **Zero stakeholder groups is not proof of no impact.** It can equally mean the
  affected elements appear on no view, which is a gap in the documentation apparatus
  (`ISO003`/`ISO005`) and worth reporting as one.
* **The classification is a recorded judgement.** Write it down where the request
  lives (the issue/CR ticket -- AD-08: issue templates are the change-request form),
  naming the class, the impacted elements and stakeholders, and the route. If the
  change contradicts an accepted decision, say which one (`governance-log/decisions/`)
  -- overturning it is an ADR, not a footnote.
* **Watch for class inflation and deflation.** "Just add a field" that crosses an
  integration contract is incremental, not simplification; "replace the ERP" is
  never incremental no matter how it is phased. When genuinely unsure, classify up.

## Reporting back

The classification, the two-line evidence for it (impacted elements and stakeholder
groups, quoted from `impact`), the route with its concrete next step, and any decision
or standard the change collides with. If the radius contained unowned elements, name
them: a change nobody owns is a change nobody can confirm.
