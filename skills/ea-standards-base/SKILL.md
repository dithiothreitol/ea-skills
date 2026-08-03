---
name: ea-standards-base
description: Maintain the standards information base (SIB) - technology and architecture standards with type and lifecycle. Use when asked to record, adopt, deprecate or retire a standard, when STD001-STD004 or SIB003/SIB004 findings appear, or when someone asks "what is our standard for X".
---

# The standards information base

One standard per file under `standards/`, so its git history is its lifecycle record:

```yaml
id: std-postgresql-16
name: PostgreSQL 16 for relational storage
type: organisation            # legal | industry | organisation
lifecycle: active             # proposed | trial | active | deprecated | retired
description: Why this exists and what it covers.
owner: infrastructure@example.test
lastReviewed: 2026-06-30
```

Elements declare what they follow with `standards: [std-...]` in the model, and the
validator enforces lifecycle: **deprecated warns (`STD003`), retired blocks
(`STD002`)** -- unless an open dispensation covers that element (`STD004`, info).
`validate-gov` checks the SIB itself.

## Lifecycle discipline

* Move standards **forward only**: proposed → trial → active → deprecated → retired.
  Reviving a retired standard is a new record with a new id and a decision explaining
  why.
* **Deprecating or retiring requires a successor** (`successor: std-...`) or `SIB004`
  warns -- teams being moved off a standard need to know what to move to. If there
  genuinely is no successor ("we stop doing this entirely"), say so in the
  description and accept the warning consciously.
* Retiring a standard that elements still reference is *supposed to hurt*: the next
  validation fails with `STD002` for each of them. That failure is the migration
  backlog. The honest responses are migration, or a time-bounded dispensation per
  system (`ea-dispensation`) -- never deleting the `standards:` reference to make the
  error go away, which converts governed debt into invisible debt.

## Evidence and judgement

A standard's *existence* is a governance act, not a source-extraction -- it needs an
owner and a decision, not a quote. But *which systems follow it* is factual: set
`standards:` on an element only when the sources or the owner confirm it. When a
CMDB export or interview reveals actual usage, that arrives through `ea-intake` and
`ea-delta-ingest` like any other fact.

## Reporting back

List what changed in the SIB, which elements are now exposed (`STD002`/`STD003`
findings, also visible in `python -m easkills kpi` as obsolescence exposure), and
which dispensations or migrations that implies. A retirement with no impact analysis
is not finished work.
