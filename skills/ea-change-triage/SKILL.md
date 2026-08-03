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

The stakeholder-impact test is the load-bearing one, and the model can answer it:
`python -m easkills context --scope <element>` shows what binds the affected system,
and the stakeholder register shows whose concerns its views frame. Count the
stakeholder groups whose concerns are touched; two or more means re-architecting,
however small the change feels technically.

## Discipline

* **Triage against the approved model**, not against memory of it. If the affected
  area is not modelled, that is itself a finding -- route through intake first.
* **The classification is a recorded judgement.** Write it down where the request
  lives (the issue/CR ticket -- AD-08: issue templates are the change-request form),
  naming the class, the impacted elements and stakeholders, and the route. If the
  change contradicts an accepted decision, say which one (`governance-log/decisions/`)
  -- overturning it is an ADR, not a footnote.
* **Watch for class inflation and deflation.** "Just add a field" that crosses an
  integration contract is incremental, not simplification; "replace the ERP" is
  never incremental no matter how it is phased. When genuinely unsure, classify up.

## Reporting back

The classification, the two-line evidence for it (impacted elements, impacted
stakeholder groups), the route with its concrete next step, and any decision or
standard the change collides with.
