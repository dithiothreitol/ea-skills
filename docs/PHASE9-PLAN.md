# Phase 9 — enforcement, signature, adoption, evidence, views, validity: implementation plan

*Authored 2026-11-10, against 0.21.0, from a review of the repository verified against its
own code the same day, two measurements taken during it (a synthetic scale probe and a
profile of `validate`), and the host's hook reference read the same day. Revised the same
day to carry **the whole scope in the fewest sessions and releases: three sessions, two
releases** — one release that builds, one that measures. Nothing was cut to get there;
what was removed is ceremony (§5). This is a plan, not a status page: every count in it
is a target or a dated measurement, and the only numbers to trust are the ones the README
badge and its tests carry. It is a draft until the operator decisions in §8 are taken.*

**Closed 2026-11-11 with 0.23.0**, in the three sessions and two releases planned, with
exit criteria 2–8 met and criterion 1 not -- four of seven host-eval cases passed in three
of three runs, and the causes of the other three are on
[the coverage page](SKILL-COVERAGE.md), recorded for a later release as D14 requires.
That later release was 0.23.1, the same day (§10's small release): five of seven cases
passed in three of three runs. 0.23.2 closed the other two and what its own run found:
every case has passed three of three on its build -- six in one full run, the seventh in
six runs after a one-line fix; its confirming run passed six of seven. 0.23.3 put the
one-command rule into every skill that runs commands, and **every case passed three of
three in one run: criterion 1 is met.**

## 1. What this phase answers

The review found the deterministic core sound, and found that three of the README's
central promises hold in this repository and not yet where an adopter works. Verified
against the code, not against the documentation:

- **The gates are prose, and the one measurement of that prose says it does not hold.** The
  first host eval (`docs/SKILL-COVERAGE.md`, 2026-10-25) passed one case of four; no run
  called `validate-facts` or `validate --zone staging`. `hooks/hooks.json` holds one
  `PreToolUse` hook, guarding `approved/`. D2 of Phase 8 — *a rule that must hold every
  time is a hook, not a sentence* — was applied to the zone and not to the gates.
- **"Human-signed" is enforced by nothing.** All 26 skills declare
  `allowed-tools: Bash(easkills *)`, which pre-approves `easkills promote` whenever any
  skill is active; the guard lets `promote` through by design; `promote` asks for no
  confirmation. `disable-model-invocation` on `ea-approve` withholds the skill, not the
  command. `owner` and `lastReviewed` are strings the agent itself writes in staging.
- **An adopter gets a sentence where this repository has a pipeline.** `template/` ships
  one issue form and no workflow, no `CODEOWNERS`, no schedule; a plugin user has no clone
  to copy `template/` from at all. The date-dependent rules (`DISP003`, `GOV004`,
  `REQ006`) fire only when somebody runs a command, so "expires loudly" is true here and
  silent there. Nothing records which tooling version a repository was written against.
- **A quote proves the text exists, not that it supports the claim.** `PROV003` locates
  the quote; the schema asks for eight characters. A harness run that is "gates green"
  says nothing about how many located quotes sit under a claim they do not make.
- **ArchiMate 4 is not mentioned anywhere.** The Open Group announced it in April 2026;
  the oracle, the generated schemas, the importer, the derivation rules and the scorer
  are pinned to 3.2, and no decision about that is on record.
- **Sources are an instruction surface and a privacy surface, and neither is handled.**
  SECURITY.md says the skills treat repository content as data; `ea-intake` does not say
  so, and no eval case tests it. Interviews are committed verbatim with no guidance on
  consent, redaction or the permanence of git history.
- **Scale is unmeasured, and the first measurement is superlinear.** 300 elements / 600
  relationships: `validate` 1.9 s. 3000 / 6000: `validate` 66.9 s, `compile` 70.5 s,
  `docs` 64.6 s (2026-11-10, Python 3.14, Windows). Profile: 46.7 of 69.7 s re-normalizing
  the same source file for each of 9042 quotes; 10.8 s in the pure-Python YAML loader. A
  300-element view renders as a 1035×5279 px six-column grid; import discards all layout.
- **The product is measured on 113 lines.** Five source files across three cases, English,
  fictional, clean markdown, authored by the author of the skills. Baseline medians:
  elements 0.48 / 0.56, relationships 0.25 / 0.13. No eval runs without a hand.
- **Prose counts drifted again.** The README says "Five of the 24 skills" beside 26 skills
  and "Phase 8 is under way" above a table that says done.

**The phase thesis is depth before breadth.** Phases 7 and 8 widened the surface — three
registers, a security vocabulary, cost, maturity, a facade — while the core loop (a host
runs the pipeline; extraction agrees with gold) stayed where the bullets above put it.
Phase 9 adds no skill, no register and no reference pack. Every item is the enforcement
or the measurement of a claim the README already makes. Phase 7's thesis stands
underneath it: an oracle, a deterministic derivation, or judgement a gate bounds.

## 2. Design decisions, settled before any code

- **D1 — A gate the skills prescribe is run by the host, not remembered by the model.** A
  `PostToolUse` hook runs the owning gate after a write into a governed directory and
  returns the findings; a `Stop` hook covers what a path-matcher cannot see (shell
  writes). The property: *no session ends on governed changes whose gate result the model
  has not seen.*
- **D2 — The hook reports, the model repairs, the cap still caps.** The property is not
  "no session ends with findings": that would turn the three-repair cap into a grind. The
  `Stop` hook blocks once and passes when `stop_hook_active` is set.
- **D3 — Promotion needs a human at the moment of the command.** The guard answers
  `promote` (without `--dry-run`) with `permissionDecision: "ask"`; where nobody can
  answer, the host denies. No skill but `ea-approve` pre-approves it.
- **D4 — The approved zone is sealed, the way the oracle is pinned.** `promote` writes an
  approval record carrying the digests of what it moved; approved content no record
  covers is a finding of the *gate* — on any host, in any editor, in CI. The hook prevents
  the accident; the seal detects the rest.
- **D5 — The human signs what they can read.** A review sheet puts every staged claim
  beside its evidence, weakest first. The entailment check a rule cannot make is made
  cheap for the person who has to make it.
- **D6 — An adopter's repository gets the mechanism.** `init`, a composite action, a
  workflow with a schedule, `CODEOWNERS`, and a declared tooling version — shipped, not
  described.
- **D7 — Dates fire without a push.** The scheduled run evaluates the wall clock and opens
  an issue; a failing nightly job nobody is notified of is the silent expiry again.
- **D8 — Content is data, said where content is read.** One sentence in every skill that
  reads sources or imports, pinned by a test, measured by a poisoned case.
- **D9 — The same text in another encoding is the same text.** One folding table (NFKC,
  typographic quotes and dashes, soft hyphens) read by the matcher and by the coverage
  segmenter. A changed *word* stays `PROV004`. The record keeps the quote as authored.
- **D10 — Anchoring is measured before it is a rule.** "The quote names the thing the
  claim is about" is checkable through the alias table and will misfire on pronouns. It
  runs as a report over gold first; the false-positive count decides the severity.
- **D11 — Entailment is measured outside the core.** A judge in `eval/harness/`, proven
  on labelled pairs before its number is reported, never a gate, never in `easkills/`.
- **D12 — Layout takes hints, never coordinates.** Grouping, order, column count and
  nesting are content-shaped and diff as content. Pixels stay computed.
- **D13 — The language version is a recorded, pinned property (AD-11).** 3.2 stays until a
  machine-readable ArchiMate 4 relationship table exists under terms that allow
  vendoring. The position is written down; a file this tooling cannot read is refused by
  name rather than misread.
- **D14 — Two releases: one that builds, one that measures.** Everything deterministic
  lands in one release, built across two sessions; the paid measurement is the second,
  taken once against the final prose — Phase 8's rule, kept. Sessions and releases are
  overhead, not scope: the count is the fewest the work fits in, and no item is dropped
  to lower it. A third release exists only if the measurement contradicts the build,
  because a finding is recorded in the release that measured it and acted on in a later
  one.
- **D15 — Graders assert the property, not the mechanism.** "A Bash call matching
  `easkills validate-facts`" becomes "the gate result is in the transcript and the final
  state passes the gate" — or D1 would fail its own eval by working.

## 3. The sessions (in execution order)

### 9.1 The plugin and the gate — session 1, no release, no API key

What the host does, and what the evidence gate accepts. Lands on `main` under the
CHANGELOG's `Unreleased`, with every gate green.

- **First task, before any design is built on it:** on the pinned host, confirm that a
  hook's `ask` prevails over a skill's pre-approval, and that plugin hooks are active
  under `claude plugin eval` (it withholds MCP servers). A few cents; §8.2 covers it.
  *The specification says what a client may do; only the client says what it does.*
- **The matcher, once:** the normalized form of a source file is computed once per run,
  not once per quote (`validate.check_provenance`, `facts.py`); `CSafeLoader` when
  present, with a test proving identical documents on every fixture; the folding table
  (D9), one definition read by the matcher and the coverage segmenter. End-of-line
  hyphenation is *not* folded — it would join words hyphenated on purpose — and RULES.md
  says so. `tools/synth_repo.py` committed and deterministic; the scale test asserts
  operation counts, never seconds; the missing-quote path measured on a 1 MB source and
  bounded.
- **Anchors (D10):** facts whose listed entities no quote names through the alias table;
  elements citing facts none of whose entities resolves to the element. Run as a report
  over the three gold repositories and the committed run records, false positives counted
  and written down, *then* `FACT012` / `PROV010` at the severity the count supports. The
  `RDY008` lesson, applied before the incident.
- **Two golden cases**, authored by the skills' stated rules, in their own commit, never
  against a run: one whose sources are in Polish (it is what exercises the folding
  table), and one long document that enters through `intake-doc` (tables, boilerplate,
  several speakers, a page with no text layer). `eval/golden/README.md` records both.
- `hooks/run_gate.py`, `PostToolUse` on `Write|Edit|MultiEdit`: `facts/register/`,
  `facts/entities.yaml`, `facts/questions/` → `validate-facts`; `model/staging/` →
  `validate --zone staging`; `standards/`, `governance-log/`, `services/` →
  `validate-gov`. Errors return `decision: "block"` with the findings (capped, with the
  total); a clean gate returns one line of `additionalContext`. A gate that could not run
  — no interpreter, a missing dependency, the time budget exceeded — says so by name. The
  guard's scoping rules apply unchanged: only under a root holding `ea.config.yaml`,
  never inside this checkout.
- `hooks/gate_on_stop.py`, `Stop`: stateless. If the working tree differs from `HEAD`
  under a governed path, run the owning gates; errors block once with the reason;
  `stop_hook_active` passes.
- The guard: `promote` without `--dry-run` → `ask`. The promote-then-delete chain stays a
  refusal.
- **Least privilege in `allowed-tools`.** Each skill pre-approves exactly the subcommands
  its own prose prescribes; a test derives that set from the skill body, and `promote`
  appears in `ea-approve` alone. Replaces `test_every_skill_pre_approves_the_cli_and_nothing_else`.
- Prose: the gate-running skills say the result also arrives as hook feedback; D8's
  sentence lands in `ea-intake`, `ea-delta-ingest`, `ea-import`, `ea-model`,
  `ea-compliance`, `ea-check`. SECURITY.md describes what is now a mechanism.
- `evals/`: graders rewritten per D15; three new cases — the gate result seen before
  "done", a promotion that must ask, a source carrying an instruction (`approved/`
  untouched, no `promote` call, the sentence at most a fact or a question). Each grader
  is proved to fail the mutation it targets.
- Truth-up: the README's measured-skill and phase-status sentences corrected and put
  under test; AD-11 recorded (§4, step T0).
- Tests: every hook fed the payloads it will receive, as the guard is today — a staging
  write carrying `REL001` blocks naming `REL001`; outside an architecture repository,
  silence; garbage in, fail open with a notice.

### 9.2 The repository — session 2, release 0.22.0, no API key

What an architecture repository carries and shows: the signature, the scaffold, the
views. Ends in the one build release.

- **The seal.** `governance-log/approvals/` (fifteenth schema): one record per promotion
  — `approvedBy`, date, each file with its SHA-256, concepts added / changed / removed,
  the `PROV006` assumptions accepted. `promote --approved-by <who> --as-of <date>`, both
  required: the record is a committed artifact, so no wall clock, for `propose`'s reason.
  `APR001` approved content no record covers (changed outside `promote`); `APR002` a
  record unreadable or schema-invalid; `APR003` a record naming a file or digest that
  never existed. `info` while a repository holds no approval record, `error` once it
  holds one — the `ISO003` shape, so the ramp needs no second release.
  `promote --seal-existing` writes the initial record and names itself as that. The
  worked example and the golden cases gain their seals; the negative fixture provokes
  every `APR` code.
- `review [--file] [--out]` (D5): per staged concept, what it claims, the quote with file
  and line (and through which fact), `assumed` / `implied` / `contested` first, and what
  the promotion replaces or drops. Deterministic markdown. `ea-approve` step 2 reads it;
  `ea-import`'s slices are reviewed with it. `ea-approve` and GETTING-STARTED say
  honestly what `owner` and `lastReviewed` assert, and that the seal and the review are
  what stand behind them.
- **The scaffold.** `init <dir>` writes it from the tooling's own `template/`, so a
  plugin user can start, with the workflow pinned to the running version. `action.yml`
  at the repository root (composite) installs from `constraints.txt` — exact versions
  and hashes, also used by CI and the template workflow, while `pyproject.toml` keeps
  ranges — and runs one `easkills` command.
  `template/.github/workflows/ea-gates.yml`: on push and pull request, the three gates
  and documentation freshness, `diff --ref` of the base branch into the job summary;
  nightly, `validate-gov` and `staleness` against the wall clock, opening or updating
  one issue on failure (D7). `template/.github/CODEOWNERS` for `model/approved/`,
  `governance-log/approvals/` and `standards/`, with a README section on required
  code-owner review. *In a team the pull request is the signature; solo, the host's
  prompt is.*
- `toolingVersion` in `ea.config.yaml` (closed key, minimum version): an older tool
  refuses by name; a newer one points at the CHANGELOG's "Upgrading" sections.
- `doctor`: interpreter, dependencies against the constraints, oracle pins, git, hooks
  present, the repository's `toolingVersion`, seal state. Exit-code contract.
- **Sources.** A GETTING-STARTED section and `ea-intake` step 0 on consent,
  classification and the permanence of git history; `intake-redact --map` applies a
  human-authored replacement map and records the original's digest and the replacement
  count — not the map — in the header, like every converter; the template ignores
  `facts/sources-private/`.
- **Views.** Nesting: a part drawn inside its whole (`Composition`, `Aggregation`) when
  both are in the view — in the SVG and as nested nodes in the exchange file. Hints
  (D12): `layout: {groupBy, columns, order}`, closed by the schema; `VIEW001` a hint
  naming an element the view does not include; `VIEW002` (info) a view past a size
  nobody reads, with the split it suggests. Edges routed through row gutters rather than
  across boxes. The importer keeps what is content-shaped — nesting, reading order as
  `order` — and still drops coordinates; check whether the and/or junction distinction
  survives the round trip, and if not, carry it as a closed property and re-emit it.
  Prose: `ea-views`.
- The eval workflows gain a monthly schedule under the existing cost cap (§8.2).
- Tests: `test_adoption_path` starts from `init`; every `easkills` invocation in the
  template workflow exists in the argparse tree (the CONTRIBUTING-block test, reused).
- The release: one "Upgrading" section covering the `ask`, the narrowed pre-approvals,
  the seal and the `promote` flags.

### 9.3 Validity — session 3, release 0.23.0, API key required

One paid run against the final text, and the first evidence this author did not write.

- Host eval: every case, three runs per arm, graded on properties.
- Harness: every case including the two new ones; a new baseline that says which
  categories are comparable and why.
- The entailment judge (D11): gold pairs as supported, shuffled pairs as unsupported; the
  judge clears a stated accuracy bar or its number is not reported. Then the
  unsupported-claim rate per run, an ungated diagnostic.
- An external corpus, zero tokens: EAModelSet (licence checked first, fetched at a pinned
  commit, never committed) through `import` → `validate` — crashes, finding distribution,
  timings.
- The overdue quarterly comparison re-check: the neighbours re-read, the table corrected,
  both dates moved. Here because it is research, independent of the build, and this is
  the lightest session.
- SKILL-COVERAGE: rows move on measured results and on nothing else. What the run
  contradicts is recorded here and acted on in a later release (D14).

Outside the session count: **one real engagement** (§8.4), whenever the operator has one.
It is the only instrument here for absolute quality, and its findings open the next phase
rather than extend this one.

### If a session runs out

Work moves to the next session; nothing is dropped and no release is added. The order in
which it moves: from 9.1, the anchors and the golden cases go to 9.2; from 9.2, the
views and `doctor` go to an extra session. Whatever moves lands **before 9.3** — the
measurement reads skill prose and gold, and both must be final when it runs.

## 4. The ArchiMate 4 track (trigger-based, not scheduled)

What is known on 2026-11-10: The Open Group's announcement of the ArchiMate 4
Specification (April 2026). From vendor write-ups, **not yet read off the specification**:
behaviour elements generalized across layers, the interaction elements dropped,
`Constraint`, `Contract`, `Gap` and `Representation` removed, `Composition` reported
removed, relationship multiplicity added. No Archi release supporting it was found.

- **T0 — in 9.1.** AD-11 written. The changes verified against the primary text. The
  licence question answered: may a version 4 relationship table be vendored? An impact
  table of what here reads a concept version 4 is said to remove — `Gap` (`PLAT004`,
  `roadmap`, `RDY001`), `Constraint` (`propose --from readiness`, the worked example),
  `Composition` (the readiness containment walk, 9.2's nesting). The importer refuses a
  version 4 exchange file by name. The watch joins the quarterly re-check.
- **T1 — when a machine-readable, vendorable table exists.** `oracle/<version>/` side by
  side; `archimateVersion` in `ea.config.yaml` (closed, default 3.2); schemas per version.
- **T2.** `migrate --to 4` writes *staging proposals* — never a rewrite of `approved/` —
  and every mapping of a removed concept is a recorded decision.
- **T3.** The default moves when the worked example and gold are clean on version 4.

No version 4 code is written before T1, and T1–T3 are outside this phase's count. An
oracle typed from blog posts is the thing this repository exists not to be.

## 5. Release plan

| Session | Increment | Release | Name |
|---|---|---|---|
| 1 | 9.1 the plugin and the gate | — (lands under `Unreleased`) | |
| 2 | 9.2 the repository | 0.22.0 | the enforcement release |
| 3 | 9.3 validity | 0.23.0 | the validity release |

The scope is the first draft's seven increments, unchanged. What the consolidation
removes is what each extra session and release costs without producing anything:

- **Five release ceremonies** — the version in three files, the CHANGELOG heading, the
  BLUEPRINT entry, the tag, the published release, and the count-pinned documents moved
  each time.
- **Four context reloads** — a session starts by re-reading the plan, the conventions
  and the code it is about to touch.
- **One paid run** — the early host-eval checkpoint. With the build sessions back to
  back, the full run in 9.3 arrives soon enough; the cost is learning that a hook did
  not help one session later.

Why it cannot be fewer:

- **Two releases, not one.** The measurement must follow the last prose change, and what
  it finds is acted on in a later release. A build that also carried its own baseline
  would be measuring a text it was still free to edit.
- **Three sessions, not two.** The build is six Phase 8 increments' worth of work; two
  sessions of three each is the aggressive reading, and merging them into one buys no
  saving — a session that long reloads its own context anyway. They share one release
  because nothing between them needs to ship: the seal's ramp is state-based, and the
  `ask` and the template are designed together.
- **What can still add to the count.** A session that runs out adds a session before
  9.3, never a release. A measurement that contradicts the build adds a release — small,
  and by standing convention.

## 6. Exit criteria for the phase

1. Every host-eval case at or above the threshold with the plugin, in three of three runs.
2. No route from a model to `approved/` without a human prompt; denied where nobody can
   answer; approved content changed by any other route is an `APR001`.
3. A repository made by `init` is green in CI on its first push, and a dispensation that
   expired yesterday opens an issue on the next scheduled run.
4. `validate` on the 3000-element probe an order of magnitude under the 2026-11-10
   measurement, held by a count-based test.
5. Five golden cases, one not in English and one not in markdown; an unsupported-claim
   rate on record; one corpus this author did not write.
6. AD-11 on record with its trigger.
7. No sentence in the README carries a number no test checks.
8. A part is drawn inside its whole, a view takes its grouping and order from hints, and
   an imported view keeps its nesting and reading order.

Criteria 2–4 and 6–8 are met at 0.22.0; 1 and 5 are what 0.23.0 reports. A criterion the
measurement fails is a finding, not a reason to hold the release.

## 7. Standing orders

Phase 7's and 8's, unchanged (module → command with exit-code contract → RULES.md →
positive fixture clean under `--strict` → negative fixture → schemas → docs in the same
commit; never edit `oracle/`, regenerate ids, import networked code into `easkills/`,
state an unchecked count, use the wall clock in an artifact). Added for this phase:

- **Depth before breadth.** No new skill, register, reference pack or report until §6.1
  holds. A request for one is recorded in the demand ledger and waits.
- **A session ends green; a release ends the build.** One thematic work commit per block
  (matcher, anchors, gold, hooks, permissions, evals, seal, scaffold, sources, views),
  each passing the full gate, so a large release is still bisectable. Session 1 leaves
  `main` consistent under `Unreleased`; the version moves once, in the release commit.
- **Fewer sessions is never a reason to drop an item.** Work that does not fit moves; a
  change of scope is the operator's decision and is asked for by name.
- **A hook is specified by its property.** Each is tested on payloads, scoped like the
  guard, and fails open *with a notice* — a silent non-run is the failure this phase
  exists to remove.
- **Verify on the host.** Anything resting on host behaviour is confirmed on the pinned
  version before it is designed around.
- **Paid runs are decisions.** None without the operator's approval, each with a cost cap.

## 8. Operator decisions to take

1. **The approved-zone seal (D4).** It is a stricter gate for every adopter. *Recommended:*
   yes, with the state-based `info` → `error` ramp and the "Upgrading" section.
2. **An `ANTHROPIC_API_KEY` repository secret, and the budget.** A few cents of host
   verification in 9.1, one full run in 9.3, and a monthly schedule afterwards; without
   the secret no eval runs unprompted. *Recommended:* yes. **Decided 2026-11-11: no** --
   the key is used locally only; the paid instruments run on the maintainer's machine.
3. **The ArchiMate 4 position (AD-11).** *Recommended:* stay on 3.2 with the T1 trigger;
   decide nothing further until the primary text and the licence terms have been read.
4. **A real engagement**, and what may be published from it.
5. **The feature freeze** in §7. *Recommended:* yes, for the length of the phase.
6. **Whether session 1 ships on its own.** If the hooks should reach plugin users before
   the scaffold is done, 9.1 ends in 0.22.0 and the phase has three releases.
   *Recommended:* no — the two sessions are meant to run back to back.
7. **`intake-redact`:** the command, or guidance only. *Recommended:* the command — the
   converter pattern already fits it.
8. **Layout hints (D12)** as the permanent boundary, pixels never. *Recommended:* yes.
9. **A second reader for the two new golden cases.** Every case so far has one author,
   who also wrote the skills. *Recommended:* yes, if anyone is available.
10. **CI for hosts other than GitHub:** maintained templates, or one documented shell
    block. *Recommended:* the shell block.
11. **OCR.** *Recommended:* stay out; `intake-doc` already names the pages it could not
    read. Revisit on the first real engagement that hits a scan.

## 9. Deliberately not in this phase

- **Connectors to a CMDB, a cloud inventory or infrastructure-as-code.** The largest
  functional gap against the incumbents, and the reason staleness detection still depends
  on people. It stays behind the AD-09 boundary until the demand ledger or the real
  engagement asks for it — named here as a gap, not as a non-goal.
- The HTTP transport for `serve`; a PyPI package; hand-placed diagram geometry; a language
  model anywhere in `easkills/`.
- Any new register, reference pack or skill (§7).

## 10. Risks

| Risk | Mitigation |
|---|---|
| A hook's `ask` does not prevail over a skill's pre-approval | checked first in 9.1; least-privilege `allowed-tools` removes the pre-approval regardless |
| Plugin hooks do not run under `claude plugin eval` | checked first in 9.1; otherwise the cases are run by the manual procedure and the gap is printed in SKILL-COVERAGE |
| The gate hook makes every write slow | the matcher fix lands first in the same session; a time budget; a named non-run instead of a hang |
| The `Stop` hook fights the three-repair cap | it blocks once and reports; D2 is the tested property |
| Two build sessions each carry three increments | thematic work commits, each green; the "if a session runs out" order; an extra session costs less than a rushed block |
| One release carries the hooks, the seal, the scaffold and the views | one "Upgrading" section; the seal is `info` until a repository holds a record; every block bisectable |
| The measurement contradicts the build | recorded in 0.23.0, fixed in a small 0.23.1 — the only way the phase grows a third release |
| The hooks did not help, and that is learned only in 9.3 | accepted as the price of dropping the checkpoint; the host verification in 9.1 removes the two known unknowns first |
| The seal breaks existing repositories | `info` until a repository holds a record; `--seal-existing`; the "Upgrading" section |
| The folding table accepts a quote that differs in substance | it folds encodings, never words; `PROV004` keeps its meaning and its tests |
| `FACT012` / `PROV010` misfire on pronouns | report first, severity from a counted false-positive rate |
| Nesting and hints change the committed example views | regenerated in the same commit, as every generator change is; byte-stability tested per hint |
| The entailment judge is itself wrong | proven on labelled pairs before any number is reported; never a gate |
| ArchiMate 4 facts here are second-hand | labelled as such; T0 replaces them with the primary text before anything is built |
| New graders pass by being weaker | each is proved to fail the mutation it targets, as the contracts are |
