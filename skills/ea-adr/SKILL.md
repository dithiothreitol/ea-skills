---
name: ea-adr
description: Record an architecture decision (MADR-shaped) in the governance log. Use when a decision has been made or needs framing, when asked to "write an ADR" or "document this decision", when superseding an earlier decision, or when the ISO 42010 conformance check reports no decisions with rationale.
---

# Architecture decision records

One decision per file under `governance-log/decisions/`, MADR-shaped, YAML so it is
machine-checkable (ISO 42010 6.10 wants decisions *with rationale*; here the schema
makes rationale mandatory rather than polite):

```yaml
id: decision-order-api-single-integration
title: The order API stays the only integration between portal and ERP
status: accepted        # proposed | accepted | rejected | deprecated | superseded
date: 2026-07-20
context: >
  The forces: what question was open, and why it had to be answered now.
decision: >
  What was decided, in one falsifiable statement.
rationale: >
  Why this option over the others -- including the risk being accepted.
consequences: >
  What becomes easier, what becomes harder, what must now be done.
options:
  - option: Single order API (chosen)
    pros: One contract, one failure mode.
    cons: Concentration risk.
  - option: Point-to-point integrations
    pros: Independent failure domains.
    cons: Hidden coupling; three contracts to govern.
relatedElements: [service-order-api, app-order-portal]
```

## What makes an ADR worth having

* **The decision is falsifiable.** "We will be API-first" is a poster; "new data
  needs extend the order API, they do not add parallel channels" can be violated and
  therefore governed.
* **The rationale names the rejected option and the accepted risk.** A rationale
  that only praises the winner is advertising. The record exists for the person in
  two years asking "did they consider X?" -- show them X in `options`.
* **`relatedElements` are real model ids** (`DEC005` checks). This link is what
  makes decisions appear in `ea-context` packs -- an ADR bound to no element governs
  nothing.
* **Status transitions are records, not edits.** Superseding means: new decision
  file, old one gets `status: superseded` + `supersededBy:` (checked by
  `DEC003`/`DEC004`). Never rewrite an accepted decision's content -- amend history
  through new records.

## Judgement calls

Record decisions at the level someone will contest later: technology selections,
integration topologies, standard adoptions, deliberate rule deviations. Do not ADR
routine modelling ("we added an element"). If the "decision" is really a waiver from
a standard, that is `ea-dispensation`; if it is a new norm going forward, it likely
needs both an ADR (why) and a SIB entry (what).

Validate with `python -m easkills validate-gov`, report the decision in one sentence
plus who should confirm `status: accepted` if you filed it as `proposed`.
