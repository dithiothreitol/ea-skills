---
name: ea-context
description: Generate scoped EA context packs for development and coding agents working in downstream system repositories (AD-09), query the approved model, or serve it read-only over MCP. Use when asked what constraints, standards or decisions apply to a system, when preparing an AGENTS.md/CLAUDE.md governance section for a consuming repo, before a compliance assessment needs its checklist inputs, for an ad-hoc question about the model, or to give another agent or MCP host access to the architecture.
argument-hint: "[element-id]"
allowed-tools:
  - Bash(easkills *)
  - Bash(python -m easkills *)
---

# Agent context packs

```bash
easkills context --root <ea-repo> --scope app-erp-core
easkills context --root <ea-repo> --scope cap-order-management   # expands to realizers
easkills context --root <ea-repo> --scope app-erp-core --out pack.md
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

## Questions no report answers: `query`

```bash
easkills query --root <ea-repo> --type ApplicationComponent --where lifecycle=active --show owner
easkills query --root <ea-repo> --where regulatoryScope~dora --show provider
easkills query --root <ea-repo> --from app-erp-core --hops 2 --rel Serving --json q.json
```

Use it instead of reading YAML by hand: the answer is computed from the same loaded
model every report reads, so it cannot disagree with them. `~` is membership in a
space-joined value -- the only correct way to ask about `regulatoryScope` -- and `key=`
finds elements missing a property. Quote the command with the answer, so the reader can
re-run it.

## The model over MCP: `serve`

With the plugin enabled, the approved model is already an MCP server (`easkills`): the
reports are tools (`kpi`, `query`, `impact`, `context`, `diff_plateaus`, the registers
and more) and the architecture description and context packs are resources. Point a
downstream agent at it instead of copying packs around when it can reach the server;
anywhere else, `easkills serve --root <ea-repo>` runs the same server for any MCP host.
It is read-only and approved-only by construction -- there is no tool that writes, and a
request to change the model through it is answered by the repository's own path:
staging, then `promote`.

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
