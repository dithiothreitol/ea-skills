---
name: ea-capability-map
description: Build or extend the business capability map, the spine of the EA model. Use when starting to model a new enterprise, when asked for a capability map, capability model or business capability assessment, or before any application/technology modelling when no capability layer exists yet. Everything else in the model attaches to capabilities, so this comes first.
---

# Building the capability map

The capability map is the spine: the single most-used EA artifact in practice, and the
thing every application, process and investment decision attaches to. Model it before
anything else. Once applications realize capabilities, portfolio views -- redundancy,
heat maps, investment quadrants -- are *derivable*; without the map they each need
separate modelling.

## What a capability is (and is not)

A capability is **what** the business can do, stable over years: "Order Management",
"Customer Service", "Demand Planning". It is not:

* a **process** (how, in what order -- that is a BusinessProcess),
* an **org unit** (who -- that is a BusinessActor; reorganisations must not rewrite the map),
* a **system** ("SAP" is not a capability; invoicing is).

Name capabilities as noun phrases. If the name only works as a verb ("Pick Orders"),
you are looking at a process.

## Method

1. **Extract from the fact register first.** `facts/register/` is the evidence base;
   capability candidates are what the sources say the business does. Cite facts
   directly (`provenance: [{fact: fact-...}]`) -- the validator resolves the fact and
   re-verifies its quotes. Only fall back to raw file+quote citations when no register
   exists.
2. **Start with one level, six to twelve capabilities.** A level-1 map that fits on a
   page and survives argument is worth more than a three-level taxonomy nobody
   confirmed. Decompose (via `Composition` from parent to child) only where the
   sources actually differentiate.

   That range is for an enterprise-wide map built on enterprise-wide evidence. **It is
   a shape, not a target**: a single interview supports the capabilities it names and
   no more. Reaching six by inventing four is the failure this skill's rules of
   evidence exist to prevent, and a measured run did exactly that on a source with
   seven facts in it.
3. **Type them `Capability`** (Strategy layer), ids `cap-<slug>`, write to
   `model/staging/strategy.yaml` (or the file the repository already uses).
4. **Attach the rest of the model.** The load-bearing relationship is
   `ApplicationComponent --Realization--> Capability`. Business processes that
   deliver a capability: `BusinessProcess --Realization--> Capability`.
5. **Mark the gaps.** A capability the sources call weak is still a capability --
   record the weakness as a property (`assessment: weak`) with the quote as evidence,
   not as a missing element.

```yaml
elements:
  - id: cap-customer-service
    type: Capability
    name: Customer Service
    owner: ea@example.test
    lastReviewed: 2026-08-01
    properties:
      assessment: weak
    provenance:
      - fact: fact-customer-service-gap
```

## Rules of evidence

Same as all modelling here: every capability is either evidenced (fact reference or
verbatim quote) or explicitly `assumed: true` with a rationale. A tidy-looking map
full of invented capabilities is worse than a lopsided map the sources support --
the lopsidedness *is information* about where interviewing should go next; list it
in your report as clarification questions.

## Finish

```bash
python -m easkills validate --root <repo> --zone staging
```

Staging validates as an overlay on `approved`, so attaching new capabilities to
already-approved applications is fine. Fix errors (three-iteration cap), report the
map with its evidence, the assumptions, and which capabilities have no application
support yet -- that list is the first portfolio insight the map produces.
