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

## Security and resilience standards

Web-application security and deployment-architecture expectations are ordinary SIB
entries, not a separate apparatus — which is the point: the same lifecycle, the same
`STD002` teeth, the same dispensation escape valve with an expiry on it.

```yaml
id: std-webapp-security-l2
name: Web application security baseline (ASVS-derived, level 2)
type: organisation            # derived from a licensed/openly-licensed source you hold
lifecycle: active
description: >
  Customer-facing web applications meet the organisation's ASVS-derived level 2
  checklist (authentication, session management, access control, input validation).
  Names the source edition it was derived from, because a baseline nobody can trace
  to an edition cannot be reviewed against the next one.
owner: security@example.test
lastReviewed: 2026-06-30
```

```yaml
id: std-ha-tier1-failover
name: Tier-1 services run active/active with tested failover
type: organisation
lifecycle: active
description: >
  Services supporting tier-1 business functions run in at least two zones with
  automated failover, and the failover is exercised on a schedule. The exercise
  record is the evidence; an untested failover path is a diagram, not a capability.
owner: infrastructure@example.test
lastReviewed: 2026-06-30
```

Three disciplines keep these honest:

* **Derive, do not transcribe.** An ASVS- or CIS-derived organisation standard names
  the edition it was derived from; the licensed or share-alike source itself stays in
  your repository under its own terms (`template/reference/README.md` covers the same
  split for reference packs). Nothing may transcribe a licensed checklist from memory.
* **Declare detection where a manifest can show it** (`detect:` on the SIB entry), and
  `ea-check` will hold product repositories to it — a TLS library floor is detectable,
  "failover is tested" is not. For the undetectable ones the evidence is a compliance
  assessment (`ea-compliance`) or an exercise record, and the standard's description
  should say which.
* **An exception is a dispensation, not a silence.** A tier-1 service that cannot yet
  fail over gets a time-bounded waiver with a named grantor — which the DORA register
  then discloses on its own (`REG003`) if the service is in scope.

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
