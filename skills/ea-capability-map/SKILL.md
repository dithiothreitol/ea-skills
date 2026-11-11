---
name: ea-capability-map
description: Build or extend the business capability map, the spine of the EA model. Use when starting to model a new enterprise, when asked for a capability map, capability model or business capability assessment, or before any application/technology modelling when no capability layer exists yet. Everything else in the model attaches to capabilities, so this comes first.
allowed-tools:
  - Bash(easkills align *)
  - Bash(easkills readiness *)
  - Bash(easkills validate *)
  - Bash(python -m easkills align *)
  - Bash(python -m easkills readiness *)
  - Bash(python -m easkills validate *)
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
   evidence exist to prevent, and a measured run did exactly that on a single
   twenty-line interview.
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

## Value streams, when the sources describe one

A value stream is the other half of the strategy layer: *how value flows* to a customer,
stage by stage, where the capability map says *what the business can do*. Model one only
when a source walks through it ("an order arrives, we check stock, we confirm the window,
we release it to the warehouse") -- never because the layer looks empty without one.

* Type it `ValueStream`, id `vs-<slug>`, named as the value delivered ("Fulfil Customer
  Order"). Its stages are value streams too, composed into it (`Composition`), in the
  order the source gives, connected by `Flow` or `Triggering`.
* **Capabilities enable stages**: `Capability --Serving--> ValueStream`. That edge is what
  turns two diagrams into one model -- the stage a weak capability serves is where the
  customer feels the weakness.
* `readiness` reports a value stream nothing enables (`RDY011`), walking the stages: a
  stream whose stages are served is enabled through them. The honest fixes are the
  capability that serves it, or a recorded gap -- never a capability invented to close the
  line.

## When is the capability map done

```bash
easkills readiness --root <repo> --zone staging   # the Strategy section
easkills align --root <repo>                      # if a reference model exists
```

`readiness` names every capability that **nothing realizes and nothing has assessed**
(`RDY001`). That list is the map's first product, not its defect list: a capability with
no application support is exactly the finding a portfolio conversation needs. Two honest
ways to close such an item, and one dishonest one:

* attach the realizer that exists and was not modelled -- `ApplicationComponent
  --Realization--> Capability`;
* record the weakness where the next reader will see it (`properties: {assessment:
  weak}`, or a `Gap` element), which closes the checkpoint *because the gap is now
  examined*;
* **never** invent a plausible application to make the line go away. That satisfies the
  report and corrupts the model, and nobody downstream can tell it from a real system.

If a reference model is present, `align` answers the other direction -- reference nodes
your map has no capability for (`ALN004`) -- and `readiness` reports the mirror image as
*information* (`RDY002`): your capabilities the reference does not anchor. Neither is a
defect by itself. A long unanchored list usually means the reference is the wrong one for
this business, not that the business is wrong.

The judgement half, which no report can run:

1. **Grain matches evidence.** Six to twelve is the shape of an enterprise map built on
   enterprise evidence. A single interview supports what it names -- three capabilities
   from a two-page interview is a *correct* map, not a thin one.
2. **Names survive contest.** Read the map aloud to someone who works there. A capability
   they do not recognise is wrong even if the underlying activity is real.
3. **No process wearing a capability's clothes.** Re-read the list for verbs. "Pick
   Orders" is a process that got typed as a capability, and it will pull the whole map
   towards an org chart within two revisions.

Done means: every capability evidenced, every unsupported one either attached or recorded,
and the three questions answered. Not "the map reached six".

## Finish

```bash
easkills validate --root <repo> --zone staging
```

Staging validates as an overlay on `approved`, so attaching new capabilities to
already-approved applications is fine. With the plugin installed the same gate also runs
on its own after staging writes, and its verdict comes back as hook feedback. Fix errors
(three-iteration cap), report the
map with its evidence, the assumptions, and which capabilities have no application
support yet -- that list is the first portfolio insight the map produces.
