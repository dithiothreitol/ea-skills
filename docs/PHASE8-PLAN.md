# Phase 8 — host, analyst, security, registers, time, measurement: implementation plan

*Authored 2026-10-25, against 0.15.0, from an audit of the repository verified against its
own code the same day. This is a plan, not a status page: every count in it is a target,
and the only numbers to trust are the ones the README badge and its tests carry. Each
increment is one session's work and ends in a release.*

## 1. What this phase answers

The 2026-10-25 audit found the deterministic core sound and keeping its promises — 716
tests green, every gate on the worked example clean as of that date — and found the gaps
everywhere *around* it. Verified against the code, not against the documentation:

- **The skills cannot reach a host on their own.** `skills/` at the repository root is not
  a location Claude Code discovers; there is no plugin manifest, no marketplace file, no
  hook. Every `SKILL.md` carries `name` and `description` and nothing else, so the one
  skill that must never run unprompted (`ea-approve`) is as auto-loadable as the rest, and
  AD-02's single write path is a sentence in prose rather than a mechanism.
- **The prose is measured by a script, not by a host.** Five of 25 skills are scored; two
  are "manual only". AD-03(f) — multi-candidate voting on high-stakes steps — is
  implemented nowhere. The harness has no structured output and no prompt caching, and its
  baseline is a model generation old.
- **The analyst has no inputs and no artifacts.** Sources are `.md` and `.txt` only
  (`facts.SOURCE_SUFFIXES`); clarification questions — "a first-class output of intake" —
  have no record type; there is no traceability matrix, no glossary, and value streams and
  outcomes exist in the oracle and almost nowhere else.
- **Security architecture has a principle and no vocabulary.** "No security layer, use the
  existing homes" is right; the homes are empty. No data classification, no trust zone, no
  exposure, no rule that can ask whether restricted data leaves through a public element,
  no SBOM input, no open control catalogue beyond CSF's categories.
- **The registers are skeletons.** The DORA register is six markdown sections with no ITS
  template identifiers and no structured export; the AI Act inventory knows nothing of
  general-purpose AI models or fundamental-rights impact assessments; there is no GDPR
  Art. 30 record. Generated documents are English only.
- **The architect has no time axis and no query.** `roadmap` lists plateaus but never
  compares them; `ea-health` tells people to keep KPI snapshots that no command writes;
  there is no diff between two states, no ad-hoc query, no heat map, no export beyond Open
  Exchange, and no read surface for consuming tools.

The phase thesis is Phase 7's, unchanged: **every item decomposes into a hash-pinned
oracle, a deterministic derivation over what is recorded, or judgement that prose guides
and a gate bounds.** Nothing here adds an element type, a network call to the core, or a
generator that writes prose for the architect.

## 2. Design decisions, settled before any code

- **D1 — The repository root is the plugin root.** `skills/` already has the plugin
  layout; `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` make it
  installable in one command without moving a file. The manifest version is the package
  version, and a test keeps them equal.
- **D2 — A rule that must hold every time is a hook, not a sentence.** Writing under
  `model/approved/` by any path other than `promote` is refused by a `PreToolUse` hook.
  The skill keeps the explanation; the hook keeps the rule.
- **D3 — Two instruments, never confused.** `claude plugin eval` measures *host behaviour*
  with and without the plugin; `eval/harness/` measures *prose* against gold. Neither is
  in the default gate; the logic of both is.
- **D4 — Converters interpret nothing.** `intake-doc` turns PDF, DOCX, PPTX and XLSX into
  a citable markdown source with the original's SHA-256 in its header, exactly as
  `intake-csv` does for CSV. Their libraries are an optional extras group, imported
  lazily; the core stays at three runtime dependencies and a test proves it runs without
  the extras.
- **D5 — Questions are records.** `facts/questions/*.yaml`, schema-validated, quote
  located mechanically, answered by pointing at the fact the answer produced. A question
  nobody can follow is a hint, not a question.
- **D6 — Security lives in the existing homes.** Closed, *prefixed* property vocabularies
  (the `criticality` lesson: never close a generic word); rules in `validate`; threats as
  a `propose` source producing `Assessment` skeletons; exposure as a report reusing
  `impact.PROPAGATION`. No element type, no layer.
- **D7 — A register is a pattern, not a feature.** A new register is a scope value, a
  module, a rule family with a provoking fixture, a gap section and a header refusing to
  pass as an attestation. Formats follow from the pattern (`--format`), never replace it.
- **D8 — Localization is a catalogue, and artifacts stay byte-stable.** `--lang en|pl` on
  generated documents; English stays the default; every key exists in both languages or
  a test fails. Terminal output and rule messages stay English.
- **D9 — Time and query are read-only derivations.** Snapshots are committed records;
  `diff` reads git history and never writes it; `query` cannot mutate; `serve` exposes the
  approved zone only, read-only, over stdio.
- **D10 — The harness measures a contract, not a parser.** Tool-use output, a cached
  system prompt, and optional majority voting over k candidates — off by default, so cost
  and comparability are a choice somebody makes.

## 3. The increments (in execution order)

### 8.1 Host and distribution — release 0.16.0, no API key

- `.claude-plugin/plugin.json` (name, version, description, author, repository, licence,
  keywords) and `.claude-plugin/marketplace.json` with the repository root as the source.
- Every skill: `allowed-tools` pre-approving `python -m easkills` invocations;
  `argument-hint` where the skill takes a scope or a date; `ea-approve` gains
  `disable-model-invocation: true`; `ea-intake` and `ea-import` gain `context: fork`.
- `hooks/hooks.json` + `hooks/guard_approved.py`: a `PreToolUse` hook refusing writes and
  edits under `model/approved/`, naming `promote` as the path. Standard library only,
  tested by feeding it the hook payloads it will receive.
- `evals/` for `claude plugin eval`: intake on the clinic source, an unprompted promotion
  request that must leave `approved/` untouched, `propose` output carrying `PROPOSED --`,
  and `ea-run` routing. A dispatch-only workflow runs it with `--no-publish` and a cost cap.
- Housekeeping: `.gitignore` covers local Claude settings; `eval.yml` on the action
  versions `ci.yml` uses; the comparison re-check moves to a quarterly cadence.
- Tests: manifest parses and its version equals `pyproject.toml`; every skill carries the
  keys its role needs; the hook refuses and allows what it should; every eval case has a
  prompt and at least one grader.

### 8.2 The analyst — release 0.17.0, no API key

- `intake-doc` (D4), extras group `[intake]` in `pyproject.toml` and `requirements-intake.txt`.
- `facts/questions/` (D5): thirteenth schema; `QST001` unreadable or schema-invalid,
  `QST002` quote not located in its source, `QST003` answered without a fact or with an
  unknown one, `QST004` duplicate id. Open-question age is a `kpi` line, not a gate.
- `propose --from coverage`: uncited source spans become question skeletons with derived
  ids, written to `facts/questions/`, never prose.
- `rtm` (requirement → bound elements → evidencing facts → sources → decisions) and
  `glossary` (the entity table with aliases and where each entity is used), both
  derivations with `--json`.
- Value streams: `RDY011` a `ValueStream` with no stage and no realizer, `RDY012` an
  `Outcome` nothing realizes. The checkpoints stay warnings, the family stays non-gating.
- Prose: `ea-intake`, `ea-capability-map`, `ea-stakeholders`, `ea-delta-ingest`.

### 8.3 Security architecture in the existing homes — release 0.18.0, no API key

- Closed vocabularies on elements (D6): `dataClassification`
  (public|internal|confidential|restricted), `personalData` (none|personal|special-category),
  `secConfidentiality`/`secIntegrity`/`secAvailability` (low|moderate|high, the FIPS 199
  scale the SP 800-53 baselines are selected by), `exposure` (internal|partner|public),
  and `trustZone` as a free label — rules compare zones for equality only.
- `SEC001` confidential or restricted data on a publicly exposed element with no binding
  security requirement; `SEC002` a `Flow`/`Access`/`Serving` crossing trust zones with no
  requirement bound to either end; `SEC003` personal data on an element outside the GDPR
  scope; `SEC004` a high-rated element no `kind: control` reference node anchors (silent
  without a control pack).
- `propose --from threats`: one `Assessment` skeleton per zone-crossing relationship, the
  STRIDE category left for a human.
- `exposure`: the reach from every publicly exposed element along `impact.PROPAGATION`,
  naming the restricted data, the high-rated elements and the obligations inside it.
- `check --sbom` (CycloneDX and SPDX JSON, matched by purl) and `pyproject.toml` as a
  fourth manifest (stdlib `tomllib`).
- Reference packs: `nist-sp-800-53-r5` (families and base controls, generated from NIST's
  public OSCAL catalogue by a script in `tools/`) and `nist-sp-800-207` (the zero-trust
  tenets); both labelled *structure not yet verified*, both mechanically cross-checked.
- New skill `ea-security`; `ea-regulatory`, `ea-model` and `ea-run` route to it.

### 8.4 Registers and language — release 0.19.0, no API key

- `dora-register --format its-csv`: one CSV per ESA template the model can feed, and a
  gap section that names template fields the model does not carry.
- `gdpr-register` (Art. 30 record of processing activities) on the D7 pattern:
  `regulatoryScope: gdpr`, `gdprPurpose`, `gdprLawfulBasis` (the six Art. 6 bases),
  `gdprDataSubjects`, `gdprRetention`, `gdprRecipients`, `gdprTransfer`; `GDR001`–`GDR004`
  on the `REG` pattern; `finco` gains personal data and stays clean.
- AI Act: `aiRole` gains `gpai-provider`; `propose --from ai-act` produces a
  fundamental-rights impact assessment skeleton (Art. 27) for every high-risk system a
  deployer runs with no associated `Assessment`.
- `--lang en|pl` on `docs`, `dora-register`, `ai-act-register`, `gdpr-register` (D8).

### 8.5 The architect: time, query, visualisation, surface — release 0.20.0, no API key

- `kpi --snapshot` writes `governance-log/metrics/<date>.json` (fourteenth schema);
  `trend` reads the series.
- `diff --plateau A B` (set difference of what two plateaus hold) and `diff --ref <git-ref>`
  (elements and relationships added, removed and changed since a commit, read via
  `git show`, never written).
- `query`: type, property filters, relationship hops; table or JSON.
- `export --format plantuml|mermaid`; `render --heatmap <property>` on any view, with
  names wrapped onto two lines instead of truncated.
- `serve`: a read-only MCP server over stdio (standard library only) exposing the reports
  as tools and context packs as resources, registered in the plugin's `.mcp.json`. This
  reverses the deferral recorded under AD-10 (operator decision, §6).

### 8.6 Measurement — release 0.21.0, API key required

- Harness: tool-use output contract, cached system prompt, default model moved to the 5.5
  family, `--candidates k` majority voting in the modelling phase (k=1 by default).
- One full run (`--all --runs 3`) plus the governance contracts, and a new baseline whose
  README section says what moved: model generation, the prose of measured skills since
  8.2, and the output contract — **no category is comparable across this baseline**.
- One `claude plugin eval` run in CI; its first numbers go into `docs/SKILL-COVERAGE.md`.

## 4. Release plan

| Release | Increment | Name |
|---|---|---|
| 0.16.0 | 8.1 | the host release |
| 0.17.0 | 8.2 | the analyst release |
| 0.18.0 | 8.3 | the security release |
| 0.19.0 | 8.4 | the register release |
| 0.20.0 | 8.5 | the time release |
| 0.21.0 | 8.6 | the measurement release |

8.6 runs last on purpose: every prose change to a measured skill lands before the one paid
run, so the baseline is taken once against the final text.

## 5. Standing orders (unchanged from Phase 7)

Per increment, in order: deterministic module; CLI subcommand with its exit-code contract;
rule codes in `docs/RULES.md`; positive case clean under `--strict` (or a dedicated fixture
where domain honesty requires one); negative case provoking every new rule; schemas
regenerated; docs in the same commit (README counts, `docs/CLI.md` command row **and**
flag table, GETTING-STARTED, SKILL-COVERAGE, CHANGELOG, BLUEPRINT §8a); the CONTRIBUTING
pre-push block. Never: edit `oracle/`; regenerate ids; import anything networked into
`easkills/`; state a count no test checks; commit licensed content; use the wall clock in
an artifact; write a generated file without `newline="\n"`.

## 6. Operator decisions (taken 2026-10-25)

1. **`--lang`:** English (default) and Polish.
2. **Comparison re-check:** moves to a quarterly cadence; the September issue is closed as
   superseded and the October one stays open as the current quarter's check.
3. **Network facade:** the AD-10 deferral is reversed — a read-only `serve` ships in 8.5.
   Demand cannot appear for a surface that does not exist, and reading the approved zone
   breaks nothing AD-09 protects.
4. **MITRE ATT&CK:** not shipped. The library admits public-domain and public-law content
   only; ATT&CK is under MITRE's own terms, and admitting it would change the library's
   licence gate, which is a separate decision.
5. **Human readings of the AI RMF and KNF packs:** remain open; only a person can
   discharge them, and nothing in this phase pretends otherwise.
6. **8.6 budget:** approved — one harness run with contracts, one plugin-eval run.

## 7. Risks

| Risk | Mitigation |
|---|---|
| `claude plugin eval` does not accept the root layout | the manifest exists from 8.1; the per-case `plugins` override is the fallback; first run in CI on Linux |
| Optional intake libraries leak into the core | lazy imports; a test runs the core with the extras absent |
| Security rules fire on idiomatic models | every SEC rule is silent until the repository uses the vocabulary it reads |
| A localized artifact drifts from its English twin | one catalogue, both languages required by a test, byte-stability per language |
| `serve` becomes a write path | no mutating tool exists; a test asserts the tool list against an allowlist |
| Count-pinned tests churn across six releases | counts move in the same commit as the thing counted, every time |
