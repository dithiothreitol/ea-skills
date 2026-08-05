# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions map to the
project's build phases (design log with per-decision rationale:
[BLUEPRINT §8a](docs/BLUEPRINT.md)).

## [Unreleased]

### Changed — what an end-to-end adoption run found

The four additions above were put through the path they exist for, on a scratch
repository scaffolded from `template/`: a handed-over spreadsheet and an Archi export
in, a promoted slice out. The pipeline held — the gate caught a planted `Serving`
Node→DataObject that the previous tool had allowed — and two things did not.

- **The importer wrote one file, so `promote --file` could not promote a slice.** The
  `ea-import` skill prescribes promoting in slices; the tooling made it impossible
  without hand-splitting the YAML. It now writes the shape this repository authors:
  elements per ArchiMate layer, relationships in `relations.yaml`, views in
  `views.yaml`. That split is **not cosmetic** — an element file has no outbound
  references and promotes on its own, while a naive split filing relationships with
  their source's layer produces slices that can never promote independently, because
  relationships cross layers. (The run hit exactly that wall before the fix.) `--out`
  still collapses everything into one file, and now says that it cannot be sliced.
- **`impact` had no `--zone`.** During adoption, or while triaging a proposed change,
  half the model is a proposal and the approved-only radius is truthfully tiny and
  practically misleading. `docs` refuses staging because a document mixing proposals
  with signed content carries false authority; under-reporting impact is the same
  failure pointed the other way, so `impact` accepts `--zone staging` (default stays
  `approved`). In the run: 1 element against approved, 4 against the proposal.
- Imported YAML now indents sequences under their key, like every hand-authored file
  here. Reviewable diffs are why this DSL is fragmented YAML at all.

### Added — `intake-csv`: a spreadsheet becomes evidence

The most common EA input in the world is a spreadsheet — an application inventory, a
server list, a contract register — and a spreadsheet is not a document a quote can be
located in. Pasting one into markdown by hand breaks the verbatim chain at exactly the
point it is supposed to hold.

- **The conversion is done by code and recorded.** The generated document's header
  carries the original file's SHA-256, its encoding and its delimiter, so a quote
  verified against the table is traceable to the bytes it came from. Byte-stable, so
  the CSV and the converted document can both be committed and CI notices divergence.
- **The delimiter is chosen by consistent column count, not by frequency.** Sniffing
  by frequency picks the comma out of `"Smith, J.";"Sales"` and produces a table whose
  columns shift row by row — authoritative-looking and silently misaligned.
- Excel's realities are handled and reported: a UTF-8 BOM is read rather than pasted
  into the first header, cp1252 falls back cleanly, pipes inside cells are escaped,
  line breaks inside cells are flattened (so a row stays one quotable line) and the
  affected rows are named, and ragged rows are padded rather than dropped.
- **Nothing is interpreted.** No column is mapped to a model field, no value is typed,
  no element is created. A tool that guessed which column meant "owner" would invent
  exactly the claims this pipeline exists to make checkable. `ea-intake` gained the
  step, including what to do with an ambiguous header: ask, do not guess.

### Added — the roadmap is a model, not a slide (`PLAT*`, `roadmap`)

ArchiMate's Implementation & Migration layer was already valid in the DSL — `Plateau`,
`Gap`, `WorkPackage` and `Deliverable` come from the same oracle-generated enumeration
as everything else, and have validated since the schema was first built. Nothing about
planning was *checked*, though, so a target state could be recorded and then quietly
contradict the portfolio decisions next to it.

- **`plateauDate`, constrained by the schema.** The standard carries no date on a
  plateau, and without one a sequence of states is a set of states. It is an
  interpreted key, so it is patterned in the schema — the `timeDisposition` lesson,
  applied on purpose rather than after an incident.
- **Seven rules.** `PLAT001` (no date), `PLAT002` (two plateaus at the same instant —
  not a sequence), `PLAT003` (a date that passes the pattern and is not a calendar
  date, the `DISP008`/`REQ009` trap), `PLAT004` (a `Gap` associated with no plateau),
  `PLAT006` (every plateau in the past — a plan whose horizon has expired), `PLAT007`
  (a `WorkPackage` realizing no `Deliverable`).
- **`PLAT005` is the one worth having**: an element decided `Migrate` or `Eliminate`
  that no plateau includes. The portfolio decision has been taken and nothing carries
  it. Silent when a repository has no plateaus at all — a model that has not started
  planning is not breaking its roadmap.
- **`python -m easkills roadmap`** and a new §9 in the architecture description:
  plateaus in date order with what each holds, the gaps between them, and the decided
  but unscheduled list. Undated plateaus sort last rather than being given an invented
  position.
- The worked example gains a two-plateau migration for the warehouse system, and
  records the contradiction it actually has: a target plateau exists, and the
  constraint says the move has no approved budget.

### Added — `impact`: the deterministic half of change triage

`ea-change-triage` already stated the rule that decides a change's class — *"count the
stakeholder groups whose concerns are touched; two or more means re-architecting"* —
and then asked a human to count by eye. `python -m easkills impact --scope <element-id>`
does the counting.

- **Propagation is declared, never inferred.** The vendored matrix says which
  relationships are *permitted* and nothing about which way a change travels, so the
  direction of each type is a stated table with its reasoning attached:
  `Serving`/`Realization`/`Assignment`/`Triggering`/`Flow` forward,
  `Access`/`Specialization` backward, `Composition`/`Aggregation` both, `Influence`
  forward, plus `appliesTo` as an edge from the bound element to the obligation. A test
  asserts every type the oracle knows has an entry — otherwise a future ArchiMate
  version adds a type through which impact silently stops flowing.
- **`Association` is never traversed.** ArchiMate leaves its meaning to the modeller;
  those neighbours are reported separately as adjacency of unknown direction. Inventing
  one would let the blast radius look thorough while being made up.
- **The radius carries its context**: stakeholder groups reached through views and
  concerns, decisions naming affected elements, obligations binding them, open
  dispensations, the consumer requests that asked about them, the standards they are
  built on, and any element with no owner — nobody to consult about the change.
- **The arithmetic half is the only verdict.** Whether the change invalidates a
  recorded assumption, decision or capability boundary is judgement; the report states
  that it did not evaluate it. Zero stakeholder groups is reported as possibly a gap in
  the views, not as an absence of impact.
- Breadth-first, so `distance` is the shortest path and the reported cause is the
  closest one; `--depth N` bounds it; output is byte-stable.

### Added — brownfield import: the adoption path (`ea-import`)

Everything before this assumed a repository that starts empty, and no organisation
with an existing architecture starts empty. `python -m easkills import --file
<export>.xml` reads an Open Group ArchiMate Model Exchange file — Archi's *Export →
Model To Open Exchange File*, or any conforming tool's — and is `aoef.py` run
backwards, with the repository's rules applied to what comes in:

- **Everything lands in staging**, as one YAML proposal; promotion is still the only
  write path into `approved/` and still runs the gate. An import never overwrites.
- **Everything arrives as a claim, not evidence**: concepts are marked
  `assumed: true` with an import rationale, and a `provenance` property from a
  previous export is kept as information, never trusted as verification. `PROV006`
  lists the whole backlog; the fact register starts from an honest zero.
- **Owner and review metadata are lifted** from exported properties back into DSL
  fields, with `appliesTo` references renamed together with the elements they bind.
- **Nothing is dropped silently**: unsupported vendor types, relationships that lose
  an endpoint, junction mappings, unnamed elements and every identifier rename are in
  the report (`--json` for the full list). Diagram geometry is discarded by design —
  layout is computed at render time.
- **The import never judges the model.** A relationship the previous tool allowed
  and the 3.2 matrix forbids is imported as-is and left for `validate` to report —
  "your old tool never checked this" is the migration's first finding, delivered by
  the same gate as every other finding.
- `--ids names` (default) derives readable slugs from element names; `--ids
  identifiers` keeps the export's own, which makes a compile → import round trip
  structurally lossless (pinned by test against the worked example).
- Skill `ea-import`: the promotion-in-slices discipline — a 400-element import
  promoted wholesale signs off 400 unreviewed claims.

## [0.9.0] — 2026-08-05

### Added — ISO 42010 §6.9: correspondences, derived rather than authored twice

The last labelled `gap` in the conformance checklist closes. The clause asks for the
relations between AD elements to be recorded, for the rules governing them to be stated,
and for violations to be known. The obvious implementation — a `correspondences:` block
authors fill in — was rejected: a decision record already names the elements it decides,
a requirement already names what it binds, an element already names the standards it
follows, a concept already names the facts that evidence it. Restating those would have
bought conformance with duplication, and the two copies would have drifted inside a
quarter. So correspondences are **derived** (`easkills/correspond.py`), and what was
actually missing got built instead.

- **Five correspondence rules, each stated and each enforced.** `realizes`
  (decision → element), `binds` (motivation element → element), `governed-by`
  (element → standard), `assessed-by` (assessment → element), `evidenced-by`
  (concept → fact). Every one crosses a boundary no ArchiMate relationship can reach
  across; inside the model, a relation between two elements is a relationship and the
  oracle already governs it.
- **`CORR001`** (warning): an element still realises a decision whose status is
  `superseded`, `rejected` or `deprecated`. The record itself is in perfect order —
  successor named, rationale present — so no `DEC*` rule could see this. What is stale
  is the *relation*, and superseding was never finished until the elements moved.
- **`CORR002`** (warning): a requirement, constraint, principle or goal whose bound
  elements are **all** TIME `Eliminate` — the seven-year retention requirement nobody
  thinks about until the system holding the records is switched off. One eliminated
  bearer among several is a migration, not a gap, and stays silent.
- **The other three cite the code that already enforces them** (`STD002`, `COMP005`,
  `PROV007`) instead of reporting the same defect twice. A clause is not implemented by
  inventing checks for relations that are already checked.
- **`python -m easkills correspondences`**: every pair, its rule and its verdict.
- **The architecture description records both remaining clauses.** New §7 Decisions
  (with rationale, never truncated) and §8 Correspondences, replacing the footer that
  promised them "in a later phase". Verdicts are evaluated as of the model's own date,
  never the wall clock, so the freshness gate cannot fail on a day nobody touched the
  repository.
- **§6.10 was strengthened the way §6.8 already had been**: a decision record in the
  governance log is a decision somebody can find, not one the *description* records. The
  clause now depends on the generated document naming each standing decision.
- CI gates `conformance --strict` on the worked example, pinned to a date — the
  example's 2027 dispensation expiry belongs to the maintenance rehearsal, not to a CI
  run that happens to be late.

### Added — contradictions are recorded, not resolved silently

The end-to-end run showed what the golden set could not measure: what happens when two
sources disagree. Nothing did — the register had `stated`/`implied` and no way to say
"another document says the opposite", and `assumed: true` is only reported when a
concept has *no* provenance, so "evidenced but contested" could not surface at all. The
honest resolution was buried in prose or, worse, decided by whichever source was read
last.

- **`confidence: contested` + `contests: [fact-id]`** in the fact register. Both sides
  stay, each with its own mechanically verified quote, and each names the other. Three
  rules keep a recorded contradiction followable: `FACT009` (contested without naming
  the other side), `FACT010` (names a fact that does not exist), `FACT011` (the other
  side does not record the disagreement back — a one-sided contradiction reads as if one
  source simply won).
- **`PROV009`** (info): a model concept citing a contested fact. Reported, never
  blocked — choosing between sources is the architect's job; choosing invisibly is not.
- **The architecture description says so.** Contested citations get their own paragraph
  in "Assumptions and open questions", **quoting the side the model did not follow**, so
  a reader can overturn the choice without reading the register.
- **New golden case `eval/golden/contested/`**: a courier's May systems inventory
  records a scheduling system as decommissioned; a July interview records dispatch
  keying weekend runs into it every Friday. Two sources, entity resolution across
  documents, 100% source coverage, and the whole contested mechanism end to end. Gated
  in CI like the other cases.

## [0.8.1] — 2026-08-05

### Changed — the golden-set scorer measures content, not vocabulary

An end-to-end run (2026-08-05) put the pipeline through the documented evaluation
procedure: blind extraction and modelling from the clinic case's source into a scratch
repository, then `score`. The pipeline came out well — every gate passed, and `REL001`
caught a genuine ArchiMate error in the run (`Assignment` from a component to an
interface, which the 3.2 matrix does not permit). The **harness** came out badly: the
candidate recalled 100% of gold's elements and relationships and scored **15%** and
**0%**, purely because it wrote "Electronic Health Record System" where gold wrote
"EHR", and because one unmatched element zeroes every relationship touching it.

- **Names resolve through the entity alias tables** of both repositories before
  comparison. The repository already knew "EHR" and "Electronic Health Record System"
  are one thing; the scorer was ignoring evidence it had.
- **Facts are matched on the source ground they cover** — the spans their verified
  quotes occupy — with statement similarity deciding full or half credit. Splitting one
  gold fact into two atomic ones is now a match, not a miss; quoting the right sentence
  under a statement that says something else is half a match, so statement quality is
  still measured.
- **A type disagreement inside one ArchiMate layer is half a match**
  (`ApplicationInterface` vs `ApplicationService` for one interview sentence), across
  layers it is none. Half credits are reported as `(n half)`, never folded in silently.
- **A label-independent `rel-structural` count** is reported beside the strict one as a
  diagnostic, never gated: when the strict number collapses, this says whether the shape
  was right.
- `eval/golden/README.md` now states what the score **is not**: a regression signal for
  a change in the skills, not an absolute grade.
- The clinic case's `ea.config.yaml` no longer states how many facts and elements gold
  holds. That file is copied into the scratch repository a candidate is produced in — it
  was handing the answer to the run being measured.

Self-scores stay 100%, so `--min-f1 100` remains a valid CI gate. On the run that
prompted this: elements 15% → 77%, relationships 0% → 73%, facts 50% → 75%.

## [0.8.0] — 2026-08-05

### Added — `ea-check`: compliance lint inside consuming repositories (AD-09 decision taken)

The deferred integration decision, resolved the narrow way the blueprint proposed —
and the narrowness is the design.

- `python -m easkills check --root <ea-repo> --repo . --scope <element-id>` runs in a
  *product* repository's CI: it reads `package.json`, `pom.xml` and `requirements.txt`
  and holds the declared dependencies against the standards its EA element claims.
  Retired without a waiver is an error; deprecated warns; a covering dispensation is
  reported **with its expiry**, because that date is a deadline.
- **The consuming repository maintains nothing.** No integration manifest, no mapping
  file: `--scope` is the entire convention, so adoption costs one CI line. Detection is
  declared by each SIB entry (`detect:` naming a dependency per manifest kind), never
  inferred — a standard with no rules is simply not checkable in code and says so.
- Matching is by dependency name; the observed version is reported, never interpreted.
  Range logic would need a semver dependency and would answer questions it cannot
  settle.
- Drift is reported in both directions: a governed dependency the model does not record
  (`CHK006`, intake material) and a claimed standard nothing in the repository evidences
  (`CHK005`).
- 8 rules (`CHK000–CHK007`), a new skill (`ea-check`, 21 total), two consumer fixtures,
  and a CI gate: the clean one must pass under `--strict`, the negative one must fail.
- Also added: a scheduled workflow that opens the monthly comparison-table re-check as
  an issue. The check itself cannot be automated — the reminder can, and an obligation
  nobody is reminded of is the failure mode this project criticises elsewhere.

Still deferred, deliberately: the network facade (MCP/HTTP) over the read-only
commands. `ea-check` needs no service to run, and the demand ledger is the instrument
that should decide whether a facade is wanted — repeated requests are evidence,
speculation is not.

## [0.7.0] — 2026-08-04

A review release: no new features, eleven fixed defects — three of them **false
negatives in the gates**, the class of bug this repository treats as highest severity.
Every finding was reproduced before it was fixed, and the reproduction is now the
regression test. Rules: 91 → 97.

### Upgrading — behaviour that legitimately changes

Repositories that passed on 0.6.0 can fail on 0.7.0. In every case the new verdict is
the correct one; here is what to expect and what to do:

- **`promote` blocks a replacement that would delete referenced content.** The gate now
  validates the post-move result, so promoting a file that omits a still-referenced
  element fails with `REF001` instead of passing and breaking the approved zone. Fix:
  carry the content forward in the staging file, or promote a narrower delta. If your
  repository was promoted on 0.6.0, run `validate --root . --strict` once — a
  previously-passed promotion may have left dangling references behind.
- **`timeDisposition` now has a vocabulary** (`Invest`/`Migrate`/`Tolerate`/
  `Eliminate`). A mistyped value is `SCHEMA001`. Fix the model — it was silently
  missing from the portfolio summary before.
- **Provenance may not point outside the repository** (`PROV008`/`FACT008`), and
  `factsRoot`/`sourcesDir` must resolve inside it (`SCHEMA002`).
- **Impossible-but-well-shaped dates are errors** (`DISP008`, `REQ009`), as is a
  request fulfilled before it was requested (`REQ010`).
- **Malformed `ea.config.yaml` values are reported** rather than silently used
  (`SCHEMA002`), with the documented default applied.
- `compile`/`render --zone staging` now mean the same overlay `validate` means, so they
  succeed on a delta that references approved elements.

### Fixed — one vocabulary for the TIME portfolio (core review, part 3)

- `timeDisposition: tolerate` (a lowercase typo) validated clean, counted as **100%
  TIME-classified** in `kpi`, and **disappeared from the architecture description's
  quadrant line — taking the whole application with it**, because the line iterated a
  fixed vocabulary and dropped anything else. The vocabulary now lives once
  (`genschema.TIME_DISPOSITIONS`): the model schema constrains the key (so the gate
  reports `SCHEMA001`), `kpi` counts only recognised values, and `docs` names
  unrecognised ones instead of hiding them. The rest of the property map stays free-form
  — only keys this tooling *interprets* carry a vocabulary.
- Two new structural tests: every literal the governance checks compare against must
  exist in its schema enum (a renamed enum value would otherwise delete a rule
  silently), and no artifact-generating module may import the terminal-styling module
  (so committed output cannot vary with the console).
- Reviewed clean: `render.py` (no model data reaches an SVG attribute; output stable to
  one decimal), `ui.py`, `genschema.py` (`additionalProperties: false` everywhere the
  "unknown key" claim in RULES.md depends on it).

### Fixed — the write path, the zones, and the reports (core review, part 2)

The most serious defect in the repository so far, plus five more. Every one reproduced
before it was fixed; the reproduction is the regression test.

- **Promotion could leave the approved zone invalid.** `promote` renames
  `staging/x.yaml` onto `approved/x.yaml`, but the gate merged the two files
  *id-by-id* and validated that union — content the move then deleted. Promoting an
  updated `application.yaml` that left out one component passed the gate with **ok**,
  deleted the component, and left dangling references (`REF001`) in the approved
  zone. The gate now validates the post-move result (file shadowing in
  `dsl.load_merged`), so the destructive promotion is blocked; a replacement that
  drops only unreferenced content passes and **names what it deletes** in the report,
  because the commit signs for it.
- **`compile`/`render --zone staging` disagreed with `validate --zone staging`**: the
  first two loaded staging alone and refused a delta with "unresolved endpoint;
  validate before compiling" — right after it had validated cleanly. What a zone means
  now lives in one function (`dsl.load_zone`).
- **An impossible unquoted date crashed every command.** PyYAML resolves
  `lastReviewed: 2026-06-31` to a date while parsing and raises a bare `ValueError`,
  which the loaders did not catch. That one-character typo produced a traceback instead
  of `SCHEMA000`.
- **`REQ010`** (new): a request `fulfilled` *before* it was `requested` passed
  validation and reported **avgFulfilmentDays: -19** in the service line.
- **KPI contradicted itself on an empty repository**: "100% owned; 100%
  stale/unreviewed" — a share of bad things is now 0% when there is nothing to
  measure.
- **ISO 42010 §6.8 could not fail** (hardcoded `pass`) in the one report whose purpose
  is refusing silent conformance. It now checks that the generated architecture
  description actually records every declared assumption.
- **Context packs could call an unreadable review date "current"**: the mandatory
  freshness banner was decided by sniffing for the substring "stale".

### Fixed — gate robustness (a code review of the deterministic core)

Four defects found by reviewing `easkills/`, each reproduced before it was fixed and
each now carrying a regression test. Two were **false negatives in the gates**, which is
the most serious class of bug this repository can have.

- `DISP008` (new): a dispensation whose `expires` matched the schema's date *pattern*
  but no calendar (`2027-13-45`) took the whole record out of the semantic checks — the
  expired-and-open error (`DISP003`), the unknown element (`DISP004`) and the unknown
  standard (`DISP005`) all vanished and `validate-gov` reported **ok**. Unparseable
  dates are now reported and the date-independent checks keep running.
- `REQ009` (new): the same trap in the demand ledger — an impossible `requested` or
  `fulfilled` date silently removed a request from the SLA arithmetic.
- `PROV008` / `FACT008` (new): a provenance `file:` could resolve outside the
  repository (`../../secret.txt`) and a quote "verified" there passed with zero
  errors. That is unreviewable traceability, and in CI on untrusted content it made
  pass/fail a probe of the runner's filesystem. Escaping references are refused.
- `SCHEMA002` (new): a malformed `ea.config.yaml` value (`stalenessDays: soon`,
  `slaDays: ten`) raised out of the check — a gate that crashes reports nothing at
  all. Configuration and record loading are now non-raising; bad values are findings
  with the documented default applied, and `factsRoot`/`sourcesDir` must stay inside
  the repository. Also caught: `quoteMatchThreshold: 90` (a ratio written as a
  percentage), which would have silently accepted fabricated quotes.
- Loaders ignore directories named like YAML files instead of crashing on them.

### Fixed — documentation claims turned into checked claims

- The oracle pins are now verified by **every** command that consumes oracle data
  (`compile`, `render`, `docs`, `gen-schema`, alongside `validate`/`oracle-info`),
  `--skip-validation` included: a tampered relationship matrix can no longer reach a
  compiled artifact or a generated schema. Previously only `validate` and
  `oracle-info` checked, while the security policy claimed every run did.
- Schema freshness now covers all nine generated schemas (one registry drives
  `gen-schema` and the test); it previously covered three, so a change to the
  standard, compliance, service or request schema could ship stale.
- `docs/CLI.md` documents per-command flag availability, machine-checked against the
  parser — the old "common flags" line implied flags on commands that exit 2 for them.
- `CONTRIBUTING.md`'s pre-push gate is now an exact mirror of CI (six steps were
  missing), and a test fails if the two drift again.
- The gold convention is stated identically in CONTRIBUTING, the PR template and the
  README, with the generated `eval/example/docs/` carve-out spelled out — the three
  wordings previously contradicted each other for any renderer or docgen change.
- Corrected rule counts in the changelog and the design log (0.0.1: 29 not 26;
  0.4.0: 25 not 20; 0.6.0: 12 not 11), and replaced hand-maintained test counts with
  a rule-count badge the suite verifies against `docs/RULES.md`.
- The Phase-H change-request issue form moved to `template/.github/ISSUE_TEMPLATE/`,
  where the `model/approved/`, `standards/` and `governance-log/decisions/` ids it
  asks for actually exist; scaffolded repositories now get it.
- The getting-started tutorial's step-4 view no longer references an element the
  tutorial never authors (it now models the `Realization` the prose describes).
- Packaging metadata reflects reality: build backend declared, PEP 639 licence form,
  and the PyPI-only claims (long description with repo-relative links, platform
  classifiers, an untested console script) removed — the oracle and schemas are
  repository data, so ea-skills is used from a clone.
- CI runs the suite on Python 3.11/3.12/3.13 across Linux and Windows, so
  `requires-python` and the Windows line-ending sensitivity of the pinned oracle are
  actually exercised.
- `SECURITY.md` scope note points at `skills/*/SKILL.md` (the old `skills/*.md`
  matched nothing), and paths named there are now checked to exist.

## [0.6.0] — 2026-08-04

### Added — the service layer (Architecture-as-a-Service / on-demand, AD-10)

- Offering catalog `services/` — one record per file; owner, fulfilment path and
  SLA-in-days are schema-mandatory; lifecycle `proposed → active → retired`;
  `selfService` flag.
- Demand ledger `governance-log/requests/` — who asked for which offering, for which
  model elements; evidenced fulfilment, reasoned refusal, SLA hygiene.
- 12 validator rules (`SVC000–002`, `REQ000–008`) in `validate-gov`.
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
  TOGAF's six-level verdict. 25 validator rules in the new `validate-gov` gate.
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
- Three-layer validator (29 rules): schema, integrity + provenance + governance
  metadata, ArchiMate 3.2 semantics from Archi's vendored, hash-pinned relationship
  matrix.
- Compiler to Open Group ArchiMate Model Exchange XML, XSD-validated offline,
  byte-stable, with deterministic layered layout.
- Worked example (clean under `--strict`) and a negative fixture violating every
  rule, proven by parametrized tests.
- Skills: `ea-model`, `ea-validate`.
