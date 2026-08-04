# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions map to the
project's build phases (design log with per-decision rationale:
[BLUEPRINT §8a](docs/BLUEPRINT.md)).

## [0.6.0] — 2026-08-04

### Added — the service layer (Architecture-as-a-Service / on-demand, AD-10)

- Offering catalog `services/` — one record per file; owner, fulfilment path and
  SLA-in-days are schema-mandatory; lifecycle `proposed → active → retired`;
  `selfService` flag.
- Demand ledger `governance-log/requests/` — who asked for which offering, for which
  model elements; evidenced fulfilment, reasoned refusal, SLA hygiene.
- 11 validator rules (`SVC000–002`, `REQ000–008`) in `validate-gov`.
- Demand-weighted maintenance: per-element demand and `neverRequested` in
  `staleness`; Service line (offerings, dispositions, SLA breaches, average
  fulfilment) in `kpi`.
- Skill `ea-service`; catalog-first routing in `ea-run`; service-performance agenda
  item in `ea-board`; demand-ordered review queue in `ea-health`.

### Changed

- Terminal output styled Claude-CLI-style (severity-coded findings, green/red
  verdicts, dimmed paths) via `easkills/ui.py` — display-only, degrades to plain
  text off-TTY, respects `NO_COLOR`/`FORCE_COLOR`.

## [0.5.0] — 2026-08-03

### Added — evaluation harness and comparison (Phase 5)

- `score` command: candidate vs gold repository, precision/recall/F1 per category
  (entities, facts, elements, relationships) with literature-grounded matching and a
  `--min-f1` gate; the candidate's own validation gates run alongside.
- Golden set `eval/golden/` (clinic case; the worked example doubles as the largest
  case) with a documented blind-run evaluation procedure.
- Skills `ea-eval` (regression discipline) and `ea-run` (orchestrator).
- README capability-comparison table vs the five closest neighbours, dated, with a
  monthly re-check obligation.

## [0.4.0] — 2026-08-03

### Added — governance and maintenance (Phase 4)

- Governance records: standards base (SIB) with lifecycle and succession; MADR
  decisions with schema-mandatory rationale (ISO 42010 §6.10); dispensations with
  schema-mandatory expiry that **errors** once passed; compliance assessments with
  TOGAF's six-level verdict. 20 validator rules in the new `validate-gov` gate.
- SIB lifecycle enforced in the model gate (`STD001–004`): retired standards block
  unless an open dispensation covers the element, and the waiver is reported with
  its expiry.
- Maintenance reports: `staleness`, `kpi`, `debt`, `conformance` (ISO 42010 Clause 6
  checklist with §6.9 as an explicit gap), `delta` (fact register vs model).
- Agent context packs (`context`): scoped, approved-only, freshness-labelled
  extracts for downstream coding agents (AD-09).
- Skills: `ea-standards-base`, `ea-dispensation`, `ea-adr`, `ea-compliance`,
  `ea-context`, `ea-delta-ingest`, `ea-health`, `ea-change-triage`, `ea-board`.

## [0.3.0] — 2026-08-03

### Added — views and documentation (Phase 3)

- Stakeholder/concern register in the model DSL; the ISO 42010 loop (stakeholder ↔
  concern ↔ view) enforced by six rules (`ISO001–006`).
- Dependency-free, byte-stable SVG renderer reusing the compiler's deterministic
  layered layout; `appliesTo` bindings drawn dotted.
- Generated architecture description (`docs` command): Clause 6 shape, application
  portfolio with TIME quadrants, capability support, declared assumptions as open
  questions; committed and freshness-checked in CI.
- Skills: `ea-stakeholders`, `ea-views`, `ea-docs`.

## [0.2.0] — 2026-08-01

### Added — modelling pipeline (Phase 2)

- Fact-referencing provenance: `provenance: [{fact: id}]` with transitive quote
  re-verification (`PROV007`).
- Motivation layer with `appliesTo` applicability selectors (`MOT001/002`), AD-09.
- Staging validates as an overlay on approved: proposals reference approved
  elements; same-id means update.
- Gated promotion (`promote`) — the only write path into `approved/`; the gate
  judges the merged result by approved-zone standards; the git commit is the
  approval record.
- Skills: `ea-capability-map`, `ea-approve`.

## [0.1.0] — 2026-08-01

### Added — intake and traceability (Phase 1)

- Fact register (`facts/register/`) with mechanically verified verbatim quotes and
  **no** `assumed` escape hatch; entity/alias table with one-term-one-entity
  enforcement. 12 validator rules in the new `validate-facts` gate.
- Deterministic line-accurate chunker and a sentence-level source-coverage report
  with an opt-in `--min-coverage` gate.
- Skill: `ea-intake`.

## [0.0.1] — 2026-07-30

### Added — the deterministic core (Phase 0)

- YAML authoring DSL with generated JSON Schema; identifiers are stable slugs.
- Three-layer validator (26 rules): schema, integrity + provenance + governance
  metadata, ArchiMate 3.2 semantics from Archi's vendored, hash-pinned relationship
  matrix.
- Compiler to Open Group ArchiMate Model Exchange XML, XSD-validated offline,
  byte-stable, with deterministic layered layout.
- Worked example (clean under `--strict`) and a negative fixture violating every
  rule, proven by parametrized tests.
- Skills: `ea-model`, `ea-validate`.
