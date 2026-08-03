---
name: ea-context
description: Generate scoped EA context packs for development and coding agents working in downstream system repositories (AD-09). Use when asked what constraints, standards or decisions apply to a system, when preparing an AGENTS.md/CLAUDE.md governance section for a consuming repo, or before a compliance assessment needs its checklist inputs.
---

# Agent context packs

```bash
python -m easkills context --root <ea-repo> --scope app-erp-core
python -m easkills context --root <ea-repo> --scope cap-order-management   # expands to realizers
python -m easkills context --root <ea-repo> --scope app-erp-core --out pack.md
```

One command produces a scoped extract of the **approved** model for the agents (and
people) working on one system: the binding requirements/constraints (via `appliesTo`,
including those inherited through realized capabilities), standards with lifecycle
and any covering dispensations, the decisions that name the element, and the
integration context -- every relationship crossing the scope boundary, with the
neighbour's owner.

## What the generator guarantees

* **Approved-only, scope-filtered.** Agents never read the raw EA repository, and a
  pack never leaks another system's content beyond the shared boundary.
* **Freshness on the label.** Every pack opens with the review state; stale or
  unreviewed content produces a warning banner telling the consumer to treat the
  pack as advisory. A stale model served as binding constraints carries false
  authority -- the banner is not optional and you must not remove it.
* **Waivers with end dates.** A dispensation shows up with its expiry and the
  explicit note that the waiver is void afterwards.

## How to deploy a pack into a consuming repository

Write it to the consuming repo (e.g. `docs/ea-context.md`) and reference it from
that repo's `AGENTS.md`/`CLAUDE.md`, or paste the relevant sections directly into a
governance section there. Always keep the generated header and freshness line.
Refresh whenever the EA repository's approved zone changes -- a pack is a snapshot,
and its "reviewed up to" line says which one.

## The feedback path (this is the point)

The pack's footer tells the consuming agent: if reality no longer matches, **report
the drift back, do not work around it**. When you are the agent in the consuming
repository and you find the pack wrong or stale:

1. Do not silently violate a constraint -- if you must deviate now, that is a
   dispensation request (`ea-dispensation`), filed before the deviation ships.
2. Report factual drift (a system renamed, an integration added, a standard not
   actually followed) as input to `ea-delta-ingest` -- a note or export dropped into
   the EA repo's `facts/sources/` is enough to start the loop.

## Reporting back

Say which scope, which model state ("reviewed up to" date), where the pack was
written, and anything the pack revealed as missing -- an element with no binding
requirements and no standards is usually an un-modelled area, not a free-for-all.
