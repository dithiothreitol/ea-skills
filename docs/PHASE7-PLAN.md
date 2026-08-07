# Phase 7 — reference, regulation, proposal: implementation plan

*Authored 2026-08-06, against 0.11.0. This is a plan, not a status page: every count in it
is a target, and the only numbers to trust are the ones the README badge and its tests
carry. Execution instructions for Claude Code are in §5; each increment is written to be
one session's work.*

## 1. What this phase answers

Recorded operator demand (2026-08-06, demand-ledger discipline — build what was asked for,
in the words it was asked in): clear per-layer modelling patterns and a definition of
*done*; completeness judged against reference architectures and industry blueprints;
maturity checkpoints; EA→IT mapping with duplicate-functionality detection; technology-debt
sizing and costing; risk, regulatory-compliance and security-gap analysis against industry
standards; process/service mapping with generated requirement templates covering identified
gaps; and a high-level EA/IT change roadmap.

The phase thesis: **every one of these decomposes into the three species this repository
already runs on** — a vendored, hash-pinned oracle; a deterministic derivation over what is
already recorded; or judgement that skill prose must guide and a gate must bound. Nothing
here requires breaking the architecture; most of it requires refusing to break it.

## 2. Design decisions, settled before any code

- **D1 — A reference model is a third oracle class.** Alongside the ArchiMate matrix and
  the XSDs: `reference/<name>/` in the *consuming repository* holds a hash-pinned taxonomy
  (`model.yaml` + `SHA256SUMS` + `NOTICE.md`) and a human-authored `mappings.yaml`. This
  repository ships the loader, the validator, the reports — and only *open* content.
- **D2 — Licensed content never enters this repository.** BIAN, APQC PCF, eTOM, ACORD are
  licensed; NIST CSF 2.0 is public domain; EU regulation texts are public law. The split is
  mechanism-here / content-at-the-adopter, enforced the same way the API key is: the
  drop-in path documented, the content gitignorable, a NOTICE per pack naming its source
  and licence. Never "helpfully" transcribe a licensed taxonomy into a fixture.
- **D3 — A gap is a first-class, named object.** An unmapped reference node is a finding
  that names the node; out-of-scope is a *recorded decision with a mandatory rationale*,
  never silence. Same rule as `conformance`: nothing passes by being unexamined.
- **D4 — No invented money.** Debt cost = exposure (derived deterministically) × unit
  rates (supplied by the operator in `ea.config.yaml`). No rates configured → exposure
  only, exactly today's output. The tool never prices anything itself.
- **D5 — Maturity is a composite of measured signals** — evidence share, ISO loop closure,
  staleness, reference coverage, governance hygiene — with thresholds written down and
  pinned by tests. No questionnaires, no self-assessment theatre.
- **D6 — Everything generated is a staging proposal.** The gap→requirement generator and
  the roadmap-skeleton generator write `assumed: true` stubs whose rationale names the
  finding that produced them. Promotion stays human. Nothing generated ever overwrites.
- **D7 — Catalogue discipline: at most two new skills** (`ea-align`, `ea-regulatory`).
  Everything else extends existing skills — the `ea-impact` lesson: two skills for one job
  dilutes the catalogue.
- **D8 — Zone semantics follow the impact lesson.** Alignment and readiness default to
  `approved` (they are claims about signed content) and accept `--zone staging` to ask
  what a proposal in flight would change. Under-reporting a gap is the failure mode.

## 3. The increments

### 7.1 Reference overlay + `align` — the keystone

"When is a layer done?" is only answerable against a yardstick. Today the repo has one
(the sources, via `coverage`); this adds the second (a reference model).

**New code**
- `easkills/reference.py` — load and verify a reference pack: `reference/<name>/model.yaml`
  (taxonomy: nodes with `id`, `name`, `kind` capability|control|process|domain, optional
  `parent`, `description`, `externalId`), `SHA256SUMS` (verified on every load, refuse on
  mismatch — the oracle pattern), `NOTICE.md` (source + licence, presence checked).
  Deliberately *not* a model: no relationships, no behaviour. A taxonomy. Resist adding
  edges — that is what `model/` is for.
- `easkills/alignment.py` + CLI `align` — two-way coverage: per reference node
  (covered / partial / **gap** / out-of-scope), unanchored local elements (info, not a
  finding), rollup percentages per taxonomy branch. `--json`, `--as-of`, `--zone`,
  `--reference <name>` (default: every pack present), optional `--min-coverage <pct>` gate.
- `reference/<name>/mappings.yaml` — human-authored:
  `{ref: <node-id>, elements: [<local ids>], status: covered|partial, note}` or
  `{ref: <node-id>, status: out-of-scope, rationale: <mandatory>}`.

**Rule codes (ALN family, owned by `align`, not `validate` — keep `validate` focused)**

| Code | Severity | Meaning |
|---|---|---|
| ALN000 | error | reference or mapping file unparsable |
| ALN001 | error | reference checksum mismatch — refuse to read (oracle discipline) |
| ALN002 | error | mapping targets an unknown reference node |
| ALN003 | error | mapping names an unknown element id |
| ALN004 | warning | reference node unmapped and not declared out-of-scope — **the gap** |
| ALN005 | error | out-of-scope without rationale |
| ALN006 | error | two mapping entries for one reference node |
| ALN007 | warning | coverage claimed by a staging-only element while reading `approved` |
| ALN008 | error | reference pack has no nodes |

**Content shipped**
- `references/` (top level of *this* repo): the open library adopters copy from.
  v1: `references/nist-csf-2.0/` — functions + categories only (public domain; NOTICE
  cites NIST). Used properly by 7.5.
- `eval/example/reference/wholesale-core/` — a ~12-node capability reference authored for
  the worked example (NOTICE says so), with mappings exercising covered, partial and one
  out-of-scope with rationale. **Example stays zero-findings under `align --strict`.**
- `eval/fixtures/broken/reference/` — every ALN rule provoked, parametrized tests.
- `template/reference/README.md` — the drop-in instructions for licensed packs.

**Skill:** `ea-align` (new) — choosing a reference honestly (what the org licensed, not
what looks impressive), mapping as *judgement recorded* (the note says why), out-of-scope
as a decision, and where gaps flow next: `ea-intake` clarification questions or 7.6's
`propose`. Raises the skill count — update the README badge, the stage table and every
count-pinning test in the same commit.

**Docs & schema:** `gen-schema` for both new file kinds; CLI.md (command row **and** flag
table); RULES.md (ALN section); README (comparison-table row "reference-architecture
alignment", repository layout, principles paragraph); GETTING-STARTED §; SKILL-COVERAGE
row (`ea-align`: path test); CHANGELOG; BLUEPRINT §8a entry.

**Definition of done:** example clean under `align --strict`; every ALN rule has a
provoking fixture and a test; byte-stable report; doc tests green; NOTICE present in every
shipped pack; no licensed content anywhere in the diff.

### 7.2 `readiness` — the per-layer definition of done

**New code:** `easkills/readiness.py` + CLI `readiness`. Checkpoints per layer, each a RDY
code, each **naming its items** (the 0.11.0 scorer lesson — a count without names is a
hand-diff waiting to happen). All warning/info; `--strict` gates; `--zone` per D8.

| Code | Layer | Checkpoint |
|---|---|---|
| RDY001 | Strategy | capability with no realizer and no recorded gap/assessment |
| RDY002 | Strategy | capability unmapped to any reference (only when a pack exists) |
| RDY003 | Business | process with no link to a capability or service |
| RDY004 | Business | actor/role attached to nothing |
| RDY005 | Application | component missing `lifecycle` or `timeDisposition` |
| RDY006 | Application | component realizing nothing |
| RDY007 | Application | service with no consumer |
| RDY008 | Technology | node serving/realizing nothing |
| RDY009 | Motivation | requirement/constraint with empty `appliesTo` |
| RDY010 | cross | a layer the fact register mentions (topics) that is empty in the model |

**Skill prose:** `ea-model` and `ea-capability-map` gain a "When is this layer done"
section: the mechanical half points at `readiness`, the judgement half is a short
checklist (grain matches evidence, names survive contest, gaps recorded not painted over).
These are **measured skills** — after editing their prose, run the harness and make the
baseline decision in writing (see §5.4).

**⚖ Forces the open gold question** (0.11.0): three runs produced the same three clinic
capabilities; gold has no Strategy layer; the skills say the capability map is the spine.
Resolve *as part of this increment*, as a recorded gold decision in `eval/golden/README.md`
— either clinic gains its small capability layer (and every count-pinned test moves with
it), or the golden README documents why a two-page interview legitimately stops below the
capability line. Recommendation: add the layer; the runs have independently converged on
its content three times, which is as close to evidence as prose measurement gets.

### 7.3 Overlap and rationalization — extending `debt`

Pure derivation; the model already holds everything needed. New `debt` queries
(report-level, no gate):

- capability realized by **≥2** application components → rationalization candidate,
  printed with each realizer's `lifecycle` / `timeDisposition` / fit properties, so
  "duplicate or deliberate redundancy" is a decision with data in front of it;
- application pairs sharing ≥2 realized capabilities;
- extension of the existing duplicate-name query to services from different components.

The verdict stays human: `ea-change-triage` and `ea-board` prose gains a
"rationalization candidates" paragraph — *deliberate* redundancy (resilience) gets an ADR,
so the next reader can tell it from drift. Tests run on purpose-built tmp fixtures; the
worked example stays overlap-free (its docs regenerate and must stay clean).

### 7.4 Cost model over debt — exposure × the operator's prices

- `ea.config.yaml` gains optional `costModel:` — `currency` plus unit rates keyed by
  exposure type (v1 keys, ⚖ confirm with operator: `staleElementDay`,
  `openDispensationDay`, `eolElement`, `unsupportedCapability`, `duplicateRealization`).
  Schema via `gen-schema`; unknown keys are schema errors, no new rule family.
- `debt` (and its `--json`) gains cost columns and a total **only when configured**;
  absent config → byte-identical to today's output (existing tests must not move).
- All time arithmetic against `--as-of`, never the wall clock.
- Docs carry the framing sentence verbatim: *the tool computes exposure, the operator
  priced it* — that sentence is the feature.

### 7.5 Controls overlay + the DORA Register of Information

Controls reuse the 7.1 mechanism (`kind: control`; the NIST CSF 2.0 pack ships in 7.1).
A control gap is already ALN004. What is new:

- **`dora-register`** CLI — generates the Register of Information (structure per the ESAs
  ITS templates: ICT third-party providers, contracts, criticality, functions supported)
  from the approved model: elements/services carrying `regulatoryScope: dora` (⚖ property
  vs config selector — recommendation: property; explicit and greppable), with
  `provider`, `criticality` (critical|important|standard), `contractRef` properties,
  joined with open dispensations (a waiver on a critical element is a register event).
- **REG family:** REG001 in-scope element missing `criticality` (warning); REG002 critical
  element missing `provider`/`contractRef` (error); REG003 critical function supported by
  an element under an open dispensation (info — exposure, not violation); REG004 register
  section empty while in-scope content exists (warning).
- **The register names its own gaps** — the generated document lists what DORA's template
  wants that the model does not carry, with element ids. That is the feature: the first
  regulatory report whose completeness is *tested*, not asserted.
- **Legal honesty, in the NOTICE and the doc header:** structure follows the ITS template;
  content comes from the model; legal review is a human's job. This is a generator, not an
  attestation.
- **Fixture:** the worked example is a food wholesaler — DORA does not apply, and
  pretending it does would poison the example. Follow the `ea-check` precedent: a dedicated
  small fixture (`eval/fixtures/finco/`) with in-scope elements, clean under the new rules,
  plus broken variants provoking each REG code.
- **Skill:** `ea-regulatory` (new, the second and last) — control mapping workflow,
  register upkeep, the dispensation coupling, and what *not* to claim.

### 7.6 `propose` — gaps become staged requirements and work packages

- `easkills/propose.py` + CLI `propose --from align|readiness|overlap [--reference <name>]`.
- Output: staging stubs — `Requirement`/`Constraint` (motivation) and `WorkPackage`
  (implementation & migration) — with **stable derived ids** (`req-<refnode-slug>`,
  `wp-rationalize-<cap-slug>`), `assumed: true`, rationale naming the generating finding
  and the `--as-of` date, `appliesTo` prefilled where derivable (overlap candidates → the
  realizers). Documentation fields carry explicit `PROPOSED —` placeholders so a
  half-finished stub cannot masquerade as an authored requirement.
- Discipline inherited from the importer: never overwrites, refuses existing ids, output
  byte-stable for identical inputs, promotion blocked by the normal gate until a human
  completes owner/evidence.
- Requirement-prose templates (business outcome, acceptance signal, binding scope) live in
  skill prose (`ea-align` §, `ea-adr` cross-reference), not in the generator — the
  generator makes skeletons, the skill teaches what a good one says.

### 7.7 Maturity checkpoints + roadmap skeleton

- `easkills/maturity.py` + CLI `maturity`: five dimensions — Evidence (evidenced vs
  assumed share), Governance (no DISP003, decision recency), Documentation (ISO clauses,
  freshness), Coverage (source coverage; reference coverage when a pack exists),
  Operations (staleness share, ownership completeness). Each level 1–5 with mechanical
  thresholds **documented in a table and pinned by a test** (the constants-vs-doc pattern
  used for `REARCHITECTING_STAKEHOLDERS`). Output: level per dimension + the named items
  blocking the next level. No composite single number — a single number is how maturity
  becomes theatre.
- Roadmap skeleton: `propose --from time` — plateau stubs for Migrate/Eliminate
  dispositions that PLAT005 already flags as carrying no plateau, ordered
  deterministically (blast radius from `impact`, then id). Staging, human-completed.
- Prose: `ea-health` (maturity reading), `ea-board` (the maturity table as a board
  artifact), `ea-run` routing entries.

## 4. Release plan

| Release | Increments | Name |
|---|---|---|
| 0.12.0 | 7.1 + 7.2 + 7.3 (incl. the gold capability decision) | the alignment release |
| 0.13.0 | 7.4 + 7.5 | the regulatory release |
| 0.14.0 | 7.6 + 7.7 | the proposal release |

Each release: full gate, CHANGELOG section, BLUEPRINT §8a entry, tag, GitHub release.
Harness reruns **only** when measured-skill prose changed (7.2 does; 7.3–7.7 mostly do
not) — and a baseline move gets its reasons written down, comparable categories named.

## 5. Execution instructions for Claude Code

### 5.1 Before any increment (standing orders)

Read first: this plan's increment section; `docs/BLUEPRINT.md` §8a tail (the latest
lessons); `docs/RULES.md`; the relevant existing module (`reports.py` for 7.3/7.4,
`importer.py` before writing any generator — the non-overwrite discipline lives there).

Never: edit `oracle/`; regenerate or "tidy" existing ids; import anything networked into
`easkills/` (the quarantine tests fail, and they are right); state a count in docs that no
test checks; commit licensed reference content; use the wall clock in any artifact
(`--as-of` everywhere); write generated files without `newline="\n"`.

### 5.2 The per-increment checklist (the established pattern, in order)

1. Deterministic module in `easkills/` — no `ui` coupling in data paths.
2. CLI subcommand: exit-code contract, `--json`, `--as-of` where time matters.
3. Rule codes → `docs/RULES.md` rows with severity and rationale.
4. Positive case: `eval/example` stays **zero findings under `--strict`** (7.5 uses a
   dedicated fixture instead — domain honesty beats convention).
5. Negative case: `eval/fixtures/broken/` provokes **every** new rule; parametrized tests.
6. Schemas regenerated in the same commit (`gen-schema`).
7. Docs in the same commit: README (badges/counts/layout/comparison), `docs/CLI.md`
   (command row **and** flag table), GETTING-STARTED, SKILL-COVERAGE, CHANGELOG,
   BLUEPRINT §8a. The doc tests fail on most omissions — treat a doc-test failure as the
   system working.
8. Run the CONTRIBUTING pre-push block (it mirrors ci.yml; a test keeps it honest).
9. Measured-skill prose touched? → `python eval/harness/run.py --all --runs 3`, then a
   written baseline decision (`--from-records` to accept without paying twice).

### 5.3 Session prompts (paste one per session)

- 7.1: *"Zrealizuj przyrost 7.1 z docs/PHASE7-PLAN.md — mechanizm referencji + `align`.
  Trzymaj się D1–D3 i D8; przykład ma być czysty pod `align --strict`; żadnej treści
  licencjonowanej."*
- 7.2: *"Zrealizuj 7.2 (`readiness`) z docs/PHASE7-PLAN.md, łącznie z decyzją o warstwie
  zdolności w gold `clinic` — decyzję zapisz w eval/golden/README.md zanim ruszysz liczby."*
- 7.3: *"Zrealizuj 7.3 — zapytania nakładania się w `debt`, przykład zostaje bez nakładań,
  testy na fixture'ach tymczasowych."* → potem: **release 0.12.0**.
- 7.4: *"Zrealizuj 7.4 — costModel w ea.config.yaml; bez konfiguracji wyjście `debt` ma być
  bajtowo identyczne z dzisiejszym."*
- 7.5: *"Zrealizuj 7.5 — nakładka kontroli + `dora-register` na fixture eval/fixtures/finco;
  NOTICE z uczciwością prawną."* → **release 0.13.0**.
- 7.6: *"Zrealizuj 7.6 — `propose`; dyscyplina importera: stabilne id, zero nadpisań,
  bajtowa stabilność."*
- 7.7: *"Zrealizuj 7.7 — `maturity` z progami przypiętymi testem + `propose --from time`."*
  → **release 0.14.0**.

### 5.4 Verification before each release

Full gate green; example zero-findings (`validate`, `validate-facts`, `validate-gov`,
`coverage 100`, `conformance --strict`, and from 0.12.0 `align --strict`); golden
self-scores 100%; adoption path green; quarantine tests green; doc tests green; if prose
moved — harness run recorded and the baseline decision written in the harness README.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Licensed content leaks into the repo | D2; NOTICE per pack; review the diff for taxonomy text before commit |
| Maturity becomes theatre | D5; no composite number; thresholds pinned by tests |
| Reference schema grows edges/behaviour | D1; taxonomy only; refuse in review |
| DORA register read as legal attestation | NOTICE + doc header wording; REG codes report gaps loudly |
| Count-pinned tests churn (skills 22→24, rules +~20) | update counts and their tests in the same commit as the thing counted |
| Gold `clinic` change destabilizes baselines | the 7.2 decision is recorded first, measured after, baseline moved with reasons — the 0.11.0 protocol |
| Generator output drifts (propose) | byte-stability tests; ids derived from finding ids, never counters |

## 7. Decisions needed from the operator (⚖)

1. Gold `clinic` capability layer — add it (recommended) or record why not (during 7.2).
2. Which licensed reference the organisation will actually use locally (drives what the
   drop-in docs demonstrate; does not change what ships).
3. DORA scope selector: `regulatoryScope: dora` property (recommended) vs config list.
4. Cost-model v1 rate keys — confirm the five proposed in 7.4.
5. Skill names `ea-align`, `ea-regulatory` — confirm before the catalogue grows.
