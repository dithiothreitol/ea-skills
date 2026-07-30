---
name: ea-model
description: Author or extend the ArchiMate model in this repository's YAML DSL. Use when adding elements, relationships or views to an EA model repo, when modelling a business/application/technology landscape from notes or interviews, or when asked to "model", "add to the architecture model", or "put this in ArchiMate". Enforces evidence-backed modelling and defers all semantic judgement to the validator.
---

# Authoring the enterprise architecture model

You are adding to a model that is validated by code. Your job is judgement -- which
concepts exist, what they are called, what depends on what. The tooling decides whether
your ArchiMate is legal. Never argue with the validator; it reads the specification's
relationship matrix and you are recalling it.

## Non-negotiables

**1. Nothing enters the model without evidence.** Every element and relationship gets
either:

```yaml
provenance:
  - file: facts/sources/interview-operations-2026-07-15.md
    quote: The ERP core holds the master order records and does the invoicing
```

or an explicit assumption:

```yaml
assumed: true
rationale: >
  Inferred from the described outage impact; no stakeholder stated this. Confirm at the
  next architecture board.
```

The quote must be **verbatim** from the file -- the validator locates it and fails the
build if it cannot (`PROV003`). Do not paraphrase, do not tidy the grammar, do not
reconstruct a sentence from memory of the document. Copy it. If the evidence for
something is genuinely absent, mark it `assumed` and say so; that is a legitimate,
supported state. Silently inventing a plausible element is the one unrecoverable
mistake, because a reader cannot tell it from a real one.

**2. Write to `model/staging/` unless told otherwise.** `approved/` is human-signed
content. Proposing into `staging/` and letting a person promote it is the workflow; do
not write directly to `approved/` on your own initiative.

**3. Run the validator before you claim to be finished.**

```bash
python -m easkills validate --root <repo> --zone staging
```

Fix errors, re-run. **Cap yourself at three repair iterations.** If violations survive
three passes, stop and report what is unresolved and why -- past that point further
attempts stop converging and start hallucinating fixes. Escalate; do not grind.

## Where things go

`model/<zone>/` holds fragmented YAML, split by layer or segment (`business.yaml`,
`application.yaml`, `relations.yaml`, `views.yaml`). Keep files small enough that a diff
is readable. Follow the existing split in the repository you are working in rather than
imposing a new one.

## Identifiers

Lower-case slugs, stable forever, chosen for meaning: `app-erp-core`,
`process-order-fulfilment`, `cap-order-management`. Prefix by kind (`app-`, `cap-`,
`process-`, `service-`, `data-`, `node-`, `actor-`, `rel-`) because it makes relations
files readable. **Never renumber, regenerate or "tidy" an existing id** -- ids are what
make re-runs produce diffs instead of rewrites, and they are referenced from views,
governance records and documentation.

## Modelling order

Build the **capability map first** and treat it as the spine. It is the most durable and
most used artifact in practice, and once applications, processes and data attach to
capabilities, portfolio views (redundancy, investment, heat maps) become derivable
instead of needing separate modelling.

Then work outward: business actors and processes, application components and services,
data objects, technology nodes. Add a relationship only when a source supports it; an
unevidenced dependency is a guess, and guesses are what make a model untrustworthy.

## Element metadata

`owner` and `lastReviewed` are mandatory in `approved` and expected in `staging`.
Unowned content is precisely how EA repositories go stale, so supply a real team or role
address, not a placeholder.

For applications, populate portfolio attributes as you go -- they cost nothing now and
save re-modelling later:

```yaml
properties:
  lifecycle: active          # plan | phase-in | active | phase-out | end-of-life
  timeDisposition: Tolerate  # Tolerate | Invest | Migrate | Eliminate
  functionalFit: adequate
  technicalFit: poor
  hosting: on-premise
```

Only record what the sources actually support. A `technicalFit` you made up is worse
than a missing one.

## Relationships

Direction matters and is the most common mistake. `ApplicationComponent --Realization-->
Capability` is legal; the reverse is not. `ApplicationService --Serving-->
BusinessProcess` is legal; `BusinessProcess --Realization--> ApplicationComponent` is
not. When `REL001` fires it lists what is permitted between those two types and tells you
explicitly if your endpoints are simply swapped -- read the message rather than guessing
again.

Do not model deployment as `Node --Assignment--> ApplicationComponent`; the matrix
rejects it. Use serving or realization, or introduce an Artifact.

Composition and aggregation must form a hierarchy. A cycle is an error (`REL002`), not a
style preference.

## Views

Views list content; the compiler computes layout.

```yaml
views:
  - id: capability-realization
    name: Capability Realization
    viewpoint: Capability Map
    documentation: >
      Which application supports which capability. Frames the portfolio-rationalisation
      concern for the CIO.
    include: [cap-order-management, app-erp-core, app-wms]
```

Never write x/y coordinates. Give each view a `documentation` line naming the *concern*
it frames and for whom -- a view that exists for no stated conversation is a view nobody
reads.

## Reporting back

Say what you added, what evidence backs it, and what you had to assume. List assumptions
explicitly as open questions -- they are the agenda for the next review, and burying them
in a wall of YAML is how they get accepted by default. Report validator output honestly,
including warnings you chose not to fix and why.
