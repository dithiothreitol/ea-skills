# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions map to the
project's build phases (design log with per-decision rationale:
[BLUEPRINT §8a](docs/BLUEPRINT.md)).

## [0.15.0] — 2026-08-08 — the AI governance release

### Added — `ai-act-register`: the second register, and the AIR family

`python -m easkills ai-act-register` generates the EU AI Act **system inventory** from
the approved model, on the `dora-register` pattern it copies deliberately: scope is
`regulatoryScope: ai-act` on the element (declared, never inferred from a type or an
AI-sounding name), the generated document says **it is not a compliance record** in its
own header, its last section names every field the model could not carry with element
ids, and with nothing in scope no document is produced at all. New element properties
`aiRiskClass` (the Act's own classes, `prohibited` included), `aiRole` (the Art. 3
operators) and `aiOversight` (Art. 14) are closed vocabularies in the generated schema,
for the same under-inclusion reason `regulatoryScope` always was.

Five rules, each with a provoking fixture (`eval/fixtures/aico`, `aico-broken` — the
`finco` convention): `AIR001` unclassified in-scope system (warning), `AIR002` high-risk
with no role or no oversight (error), `AIR003` open dispensation on a high- or
limited-risk system (info — accepted AI risk to disclose, and the mandatory expiry on a
dispensation fits model-risk acceptance exactly), `AIR004` empty section with content in
scope (warning; the provider section is only owed once some in-scope system was made by
someone else), `AIR005` an approved element classified as an Art. 5 **prohibited
practice** (error — not a row to file, a decision the board must see). 146 rules total.

### Changed — `regulatoryScope` admits multi-scope combinations, and `dora-register` reads membership

A bought credit-scoring service is DORA's ICT third-party risk *and* the AI Act's
high-risk system at once. The single-valued enum would have forced a choice, and
whichever register lost would have lost silently — the exact under-inclusion the closed
vocabulary exists to prevent. `regulatoryScope` is now a closed enum of each scope alone
plus every space-joined combination in alphabetical order (`ai-act dora`); a reordered
or misspelled value is still a schema error, never a silent row-drop. Both registers
read membership through one shared splitter, which also fixes a latent equality test in
`dora-register` that would have dropped a multi-scope element; a test pins the
dual-scope element into both registers.

### Added — two reference packs: NIST AI RMF 1.0 and KNF Rekomendacja D (2013)

Both ship in `references/` under the library's licence gate — the AI RMF as public
domain (NIST AI 100-1), Rekomendacja D as public law (an official document of a Polish
public authority, art. 4 of the Polish Copyright Act). The AI RMF pack carries the four
Functions and nineteen Categories with each category's outcome statement **verbatim**,
because the RMF publishes no short names; the KNF pack carries the four areas and
twenty-two recommendations, each node named with the document's own section heading and
carrying the recommendation's statement verbatim in Polish. **Both are labelled
`structure not yet verified`**, and both were then cross-checked mechanically against
their primary sources: the AI RMF pack against the PDF of NIST AI 100-1 (all four
Functions and nineteen Categories matched), the KNF pack against the document body, which
turned the one thing the pack had *inferred* — which heading belongs to which numbered
recommendation — into something read off the source (all twenty-two matched). Neither
`model.yaml` needed a correction, and neither label changed: this repository defines a
verified pack as one **a human** has read the primary source for, and a machine
confirming that two strings agree is not that. The NOTICEs now say both halves, so the
reading that remains is short and its scope is written down. The tests that keep the
caveat in both the NOTICE and the library table cover these packs from day one.

### Added — `ea-ai-governance`, and security architecture written into the existing skills

The 25th skill owns the AI Act inventory, the AI RMF alignment, and the discipline
around both (risk classes are facts about the system, gaps are disclosed rather than
edited closed, an AI system is not a new element type — the evidence around an ordinary
element is what is AI-specific). `ea-regulatory` gains the routing to it and a
**"Security architecture, in the existing layers"** section: posture measured by control
packs, principles in the motivation layer, concrete standards in the SIB, accepted risk
as dispensations — no parallel structure, because ArchiMate has no security layer on
purpose. `ea-standards-base` gains the security-and-resilience standards pattern
(ASVS-derived web-application baselines, HA/failover tiers), including the
derive-don't-transcribe rule for licensed checklists and the line between manifest-
detectable standards (`ea-check`) and exercise-record ones (`ea-compliance`).

### Changed — the NIST CSF 2.0 pack is verified

The pack shipped in 0.13.0 labelled **structure not yet verified** — written from working
knowledge rather than read off the source, and stated as such because nothing mechanical
can tell the two apart. The maintainer has now walked the six Functions and twenty-two
Categories against the Function and Category tables of NIST CSWP 29 (February 2024) and
confirmed them as transcribed; **no correction was needed**. What was checked is named
narrowly — identifiers, names and parentage, the whole of what the pack carries. What each
Category *requires* is still the Framework's own text to say.

The NOTICE's caveat became a **dated** statement rather than being deleted, and
[`references/README.md`](references/README.md) carries the same date. A verification with
no date says nothing about which edition it was against, so a later CSF edition would turn
a true claim false with no edit anywhere; a new test therefore requires the date in both
places, alongside the existing test that keeps the two files agreeing. The pack is
re-pinned.

## [0.14.0] — 2026-08-07 — the proposal release

Phase 7.6 + 7.7, and the last of Phase 7: findings become staged work, and the practice
gets a measured level. **Phases 0–7 are complete.**

### Added — `maturity`: five dimensions, no composite (Phase 7.7)

`python -m easkills maturity` scores Evidence, Governance, Documentation, Coverage and
Operations at **level 1–5 each**, against twenty thresholds written down in
[`docs/CLI.md`](docs/CLI.md) and pinned by a test against `maturity.DIMENSIONS` — the
constants-versus-doc pattern `impact` uses for `REARCHITECTING_STAKEHOLDERS`. Output is a
level per dimension plus **the named items blocking the next one**; the list is the
deliverable, the level is the headline.

**There is no composite number, and the absence is tested.** A single "we are a 3.4" can
be moved by the cheapest dimension and hides which one moved — which is how a maturity
programme ends up optimising the number instead of the practice.

Two properties keep the levels honest:

- **Level 1 is "measured", not "bad".** Gates start at level 2, so a young repository
  scores 1 and is failing nothing. Nothing here is an error and it never gates.
- **Unmeasurable is not satisfied — and this was a defect before it was a feature.** The
  first version told an *empty* repository it was `sustained` on Evidence and Operations,
  because a share over nothing is 1.0 and a count of problems over nothing is 0. Every
  metric now carries its population; an empty one is `None`, the gate stays shut, and the
  blocker names the apparatus that does not exist yet. That is the vacuous-100% trap
  arriving in the one report whose number leaves the repository.

Every signal is read from the report that already owns it — `kpi`, `conformance`,
`staleness`, `coverage`, `align`, the governance log — so a level cannot rise without
something else agreeing it improved. Prose: `ea-health` gains "Reading maturity",
`ea-board` the maturity table as a board artifact, `ea-run` a routing row.

### Added — `propose --from time` (Phase 7.7)

The fourth source: one `WorkPackage` per Migrate/Eliminate disposition no plateau carries
(`PLAT005`), **ordered by blast radius then id** — the one piece of judgement a tool can
supply here is which change reaches furthest.

**A `WorkPackage`, not a `Plateau`, against the phase plan — and caught before shipping
this time.** `PLAT001` makes a plateau without a `plateauDate` an error, so a generated
plateau stub would fail the gate this command promises its output passes; supplying the
date is worse, because a plateau date is a claim about when a target state is reached.
The generator produces the *work of scheduling*; the human creates the plateau.

### Fixed — the generic id sort discarded a source's ordering

`propose` sorted every candidate by id before writing, which silently threw away
`--from time`'s blast-radius ordering. Source order is preserved now; every source
enumerates deterministically, so byte stability is unaffected.

### Added — `propose`: findings become staged skeletons (Phase 7.6)

`python -m easkills propose --from align|readiness|overlap --as-of <date>` turns one
report's findings into the *shape* of the work and stops there. A reference gap becomes a
`Requirement` (a `Constraint` for a `kind: control` node), an open readiness checkpoint a
`Constraint` bound to its element via `appliesTo`, a rationalization candidate a
`WorkPackage` *naming* its realizers in `properties.rationalizes`. Output goes to
`model/staging/proposed-*.yaml`.

Only `appliesTo` differs between the three, and the reason is a rule doing its job:
`appliesTo` is the **Motivation layer's** applicability selector, so `MOT002` makes it an
error on an Implementation & Migration element. The phase plan asked for it on the
`WorkPackage`; that produced a staging file failing the very gate this command promises
its output passes. The rule is right on substance too — *which* relationship a work
package has to a component is the decision the package exists to take.

Only **warning-severity** readiness checkpoints propose. An open checkpoint is what
`readiness --strict` gates on, and that counts warnings; `RDY002` is info, because a
capability no reference anchors is usually the business doing something its industry
blueprint never heard of.

**The generator supplies ids, types and bindings. It supplies no prose.** Every
documentation field opens with a loud, greppable `PROPOSED --` naming what the author has
to write, and the templates for writing it live in skill prose (`ea-align` gained "Turning
a gap into a requirement": business outcome, acceptance signal, binding scope) rather than
in the generator. Text that reads as authored and is not is the same failure as a
fabricated quote one layer up.

The importer's discipline, borrowed whole:

- **Never overwrites** — an existing target file is a refusal, not a merge.
- **Ids are derived, never counted** (`req-<pack>-<node>`, `con-<element>-<code>`,
  `wp-rationalize-<capability>`), so a re-run after fixing three of ten findings proposes
  the same seven ids and the diff is the news. An id already in either zone is skipped
  **by name**: somebody acted on that finding, which beats both silence and failing the
  whole run over it.
- **Byte-stable** for identical inputs.
- **Promotion still blocks.** Stubs validate in `staging` and cannot leave it without an
  owner and a review date — generation is cheap, vouching is not, and the gate is where
  that asymmetry lives. A test asserts both halves, per source.
- **It refuses rather than guessing.** A source report carrying errors (an unreadable
  `mappings.yaml` makes every leaf look like a gap, and `align` exits 1 on exactly that),
  an id that would break the schema's pattern or 80-character limit, or two findings
  deriving one id — each is a refusal naming the finding. Emitting any of them would
  hand over a staging file the gate rejects and a re-run reproduces byte for byte, which
  the operator cannot fix by editing.
- **`--from align` selects on `ALN004`, not on `status == gap`.** `align` marks a node a
  gap and then suppresses `ALN004` when `ALN003`/`ALN005`/`ALN007` already named *why*.
  Those need the named problem fixed, not a requirement filed on top — and a stub citing
  an `ALN004` that was never raised carries a rationale that is simply false.

Two smaller decisions worth reading: `--as-of` is **required here and nowhere else**,
because this is the one command that writes a date into a file you commit — a wall-clock
stamp would make an unchanged repository produce a different file tomorrow. And `RDY010`
generates nothing: it names a layer, not an element, and a constraint bound to nothing is
what `MOT001` exists to stop.

`ea-adr` gained the two cases that arrive from generated proposals — a "keep both" answer
to a rationalization work package, and a requirement that overturns an accepted decision.

## [0.13.0] — 2026-08-07 — the alignment and regulatory release

Phase 7.1–7.5: the second yardstick, the per-layer definition of done, overlap detection,
a cost model over debt, and the first regulatory output.

> **There is no 0.12.0 tag, and that is deliberate.** The plan grouped 7.1–7.3 as 0.12.0
> and 7.4–7.5 as 0.13.0, but all five increments landed in one commit — the doc-count tests
> make the intermediate states red, because rules go 137 → 141 and skills 23 → 24 only at
> the end. No repository state ever held 7.1–7.3 without 7.4–7.5, so a `v0.12.0` tag would
> point at a commit containing `dora-register` and claim otherwise. The plan's grouping is
> preserved in the sections below; the version numbers are not stretched to match it.

**Harness rerun and baseline decision** (owed since 7.2, recorded in
[`eval/harness/README.md`](eval/harness/README.md)): 6/6 runs green, no category regressed,
baseline moved to the third one. `clinic`'s element (+13) and relationship (+12) rises are
**the instrument, not the skill** — gold's denominators changed when the capability layer
was added, and this was predicted in writing before the numbers existed. The comparable
categories are flat to within noise, which is the trustworthy half of the result.

### Added — `dora-register` and the controls overlay (Phase 7.5)

`python -m easkills dora-register` generates the DORA **Register of Information** from
the approved model: ICT third-party providers, contractual arrangements, the services in
scope with their criticality, the business functions depending on them, and every open
dispensation covering any of it. Four rules, `REG001`–`REG004`. New skill:
[`ea-regulatory`](skills/ea-regulatory/SKILL.md) — the second and last of Phase 7, taking
the catalogue to **24**.

**A generator, not an attestation, and the document says so above its own tables.** The
structure follows the shape the ESAs' implementing technical standards ask for; the
content comes from the model and nowhere else; no legal review has happened and no
completeness against the official templates is claimed.

What makes it worth generating is the last section: **the register names its own gaps** —
every field the template wants that the model does not carry, with the element ids
missing it. A register that quietly omitted what it could not fill would be
indistinguishable from a complete one, and the person filing it would learn the
difference from a supervisor. This is the first regulatory output here whose completeness
is *tested* rather than asserted.

Three decisions worth reading:

- **Nothing in scope produces no document at all** — not an empty one. The worked example
  is a food wholesaler DORA does not apply to, and it reports exactly that. An empty page
  that looks like a filing is the worst artifact this command could emit, so `--out`
  refuses to write one.
- **Scope is a property on the element** (`regulatoryScope: dora`), not a list in config:
  it lives next to what it describes, moves with it, and shows up in the diff of the
  commit that changed it. It is a **closed enum**, because the failure mode of a
  regulatory report is *under-inclusion* — `DORA` as free text would drop the element
  silently and nothing downstream would ever say so.
- **`REG003` is info.** An open waiver on a critical service is exposure to disclose, not
  a violation to fix. As a warning it would push people to close dispensations to clear a
  report, destroying the record of the very thing the register exists to show. The clean
  fixture carries one on purpose and still passes `--strict`.

Controls need no new mechanism: a control framework is a taxonomy, so it rides the 7.1
reference overlay (`kind: control`) and an unmapped control is `ALN004`. NIST CSF 2.0 has
shipped in [`references/`](references/) since 7.1.

Fixtures follow the `ea-check` precedent — domain honesty over convention:
`eval/fixtures/finco/` (a fictional e-money institution, clean under `--strict`) and
`eval/fixtures/finco-broken/`, one element per REG failure mode. Both are in CI, positive
and negative.

### Added — a cost model over the debt register (Phase 7.4)

**The tool computes the exposure, the operator priced it.** That sentence is the feature,
and the report prints it above every total. Debt is measurable — element-days past the
staleness threshold, dispensation-days open since granted, elements on deprecated or
retired standards, capabilities nothing realizes, realizers beyond the first on one
capability. What any of that is *worth* is not measurable here, so nothing guesses:
`ea.config.yaml` gains an optional `costModel` with a `currency` and five unit rates the
operator writes down and can defend.

**With no `costModel`, `debt` output is byte-identical** — no section, no key in the
`--json`, not one character. A test asserts it, because the alternative makes every
existing report diff unreadable for a feature nobody switched on.

The total says what it left out, on the lines directly beneath it:

- **Not priced** — an exposure with a real quantity and no configured rate. A partial
  total that looks complete is worse than no total, because it is the number that reaches
  a slide.
- **Not measurable** — elements with no review date carry no element-days, and are named
  rather than counted as zero. "We cannot tell" and "it costs nothing" are different
  answers, and only one of them is honest.

Amounts use `Decimal`, not float. Every quantity is measured against `--as-of`, so a
figure pasted into a board pack reproduces a month later.

`ea.config.yaml` gains a generated schema (`schema/ea-config.schema.json`, the twelfth),
and with it a **closed key vocabulary** — a misspelled rate key or top-level key is
`SCHEMA002`, not a silent zero. This is deliberately stricter than an element's open
`properties` map: a model's own property keys are the organisation's business, but a
*tooling* key the tooling does not read is always a typo, and `stalenessDay` leaves the
365-day default in place while the repository looks fresh. Where the schema and the older
hand-written range checks overlap, one typo still produces one finding.

`ea-health` gains a "Reading the cost section" guide whose first instruction is to read
the total as a floor, and whose last is never to set a rate to make a number look right.

### Added — overlap and rationalization queries in `debt` (Phase 7.3)

The operator demand said "EA→IT mapping with duplicate-functionality detection". The model
already held the answer; nothing was reading it. `debt` gains three queries — no new rule
codes, no gate, no new command:

- **`rationalization-candidate`** — a `Capability` realized by two or more application
  components, printed with each realizer's `timeDisposition`, `lifecycle` and every other
  property the portfolio records against it.
- **`overlapping-applications`** — an application pair realizing **two or more** of the
  same capabilities. One shared capability is already a candidate above; the *pair* is
  only a merge conversation once the overlap repeats.
- **`duplicate-service`** — one service name (whitespace- and case-insensitive) offered by
  **disjoint** providers, across service types, which the older `duplicate-name` query
  compares type-first and therefore cannot see.

**The register never says "duplicate".** Redundancy is as often bought on purpose —
resilience, data residency, a strangler running beside what it replaces — as it is drift,
and nothing in a model distinguishes the two. So the queries report the *data a decision
needs* and route the decision to a human: `ea-health` reads them, `ea-change-triage`
classifies the change that lands on one (undecided overlap is a re-architecting trigger,
not an incremental change), `ea-board` takes it as a standing agenda item, and deliberate
redundancy ends in an **ADR** — without one, the next reader cannot tell design from decay
and the same finding is re-litigated every quarter.

Three exclusions are the difference between a query and noise, and each is pinned by its
own test: a **business role** realizing a capability alongside a component is division of
labour, not duplication (the golden set's Appointment Booking is exactly that shape); a
service **realizing an identically named service** one layer up is idiomatic ArchiMate; and
two same-named services from the **same** provider are a naming slip for `duplicate-name`,
not portfolio duplication. Byte stability is tested across two pinned `PYTHONHASHSEED`
values in subprocesses — the only way an id-set ordering bug can actually fail.

The worked example and the golden set stay overlap-free, and a test says so: a wholesaler
running two order systems, or a two-doctor clinic running two EHRs, would teach the wrong
shape. The queries are exercised on fixtures built per test instead.

### Added — `readiness`: the per-layer definition of done (Phase 7.2)

"Is the application layer finished?" was answerable only by an architect's feeling.
`python -m easkills readiness` is the mechanical half: one checkpoint list per ArchiMate
layer (Strategy, Business, Application, Technology, Motivation), ten codes `RDY001`–`RDY010`,
each finding **naming the elements** that fail it — the 0.11.0 scorer lesson, where a count
without names turned three investigations into hand-diffs of two YAML trees.

**Nothing in the family is an error, by design.** An unfinished layer is not a wrong model,
and a report that blocked a commit for incompleteness would be switched off within a week —
after which it measures nothing while still looking like coverage. `--strict` is how a
repository that *claims* completeness opts into the gate. An empty layer is printed as
`empty` rather than flagged: not having started a layer is not breaking it, the same rule
that keeps `PLAT005` silent when there are no plateaus.

Three decisions worth reading before using the report:

- **A part contributes through its whole.** `RDY006`/`RDY007`/`RDY008` are satisfied when
  the element *or anything that composes it* serves or realizes something. Writing the
  checklist without that reported the worked example's `PostgreSQL 16` — composed into the
  server that serves the ERP — as unfinished technology. Correct, idiomatic ArchiMate, and
  the first thing the report got wrong; a checkpoint that flags idiomatic modelling teaches
  people to ignore the report.
- **`RDY001` asks the narrower question: unsupported *and unexamined*.** A capability whose
  weakness the model records — `properties: {assessment: weak}`, the idiom
  `ea-capability-map` teaches, or an associated `Gap` — is examined, and closes the
  checkpoint. `debt` still lists every unsupported capability as a smell. The honest way to
  close a readiness item is to record the gap, never to invent a plausible realizer.
- **`RDY002` is *info*, not warning** — a deliberate refinement of the plan. It is the same
  observation `align` reports as information (a local capability no reference anchors), and
  as a warning it would fail `readiness --strict` for a business doing something its
  industry blueprint never heard of, which is the failure mode 7.1 designed the unanchored
  list against. One observation, one severity, whichever report it appears in.

`ea-model` and `ea-capability-map` gain a **"When is this layer done"** section: the
mechanical half points at `readiness`, the judgement half is three questions no report can
ask — does the grain match the evidence, do the names survive contest, are the gaps recorded
rather than painted over.

### Changed — gold: `clinic` gains its capability layer

Recorded in full in [`eval/golden/README.md`](eval/golden/README.md), because it is the
second gold change and the one most easily mistaken for the forbidden move.

`ea-capability-map` states that the capability map is **the spine**, comes **first**, and is
what everything attaches to. Gold's `clinic` had no Strategy layer at all — so a run that
followed the method produced three elements gold could not match, and lost precision for
obeying the skill it was being measured on. `readiness --root eval/golden/clinic` prints
`Strategy  empty` beside a complete Business and Application layer: the contradiction,
stated mechanically.

The three capabilities were derived from the register the way the skill prescribes — noun
phrases, each citing the fact that evidences it, three because the interview supports three
("the 6–12 range is a shape, not a target"). They were **not** copied from any run's output
and the entity table was **not** given aliases to make matching easier: three measured runs
*exposed* the problem and are not the authority for the fix. The same distinction that made
the 2026-08-06 atomicity correction legitimate.

**The `clinic` element and relationship baselines are therefore not comparable across this
change**, and `eval/harness/README.md` now says so at the point where someone would read the
numbers. `facts` and `entities` are untouched. A harness rerun is owed for that and for the
prose change above.

Four count-pinned score tests moved with gold and were rewritten against
`category.gold` rather than literals, so the next legitimate change to a golden case moves
the arithmetic instead of the claim.

### Added — reference-architecture alignment: the second yardstick (Phase 7.1)

"Is this layer done?" had no mechanical answer. `coverage` answers *did we model what we
were told* — complete against one conversation, and silent about the invoicing capability
nobody mentioned. `python -m easkills align` adds the other half: *did we model what a
business like this has*, measured against a **reference architecture**.

- **`easkills/reference.py`** — reference packs as a *third class of hash-pinned oracle
  data*, living in the consuming repository: `reference/<name>/model.yaml` (a taxonomy of
  nodes with `id`/`name`/`kind`/`parent`, and deliberately no relationships — edges
  between architecture elements belong in `model/`, where the ArchiMate oracle governs
  them), `NOTICE.md`, and `SHA256SUMS` over both. A pack whose pins do not verify — or
  that has none, or does not pin its NOTICE — is **refused rather than read**: coverage
  measured against an edited taxonomy is not a lower number, it is not a measurement.
  `mappings.yaml` is deliberately *not* pinned, because it is the one file an architect
  edits and pinning it would make re-pinning a reflex.
- **`easkills/alignment.py` + `align`** — per node `covered` / `partial` / **gap** /
  `out-of-scope`, per branch a rolled-up percentage, plus the local elements the
  reference does not anchor as *information, never findings* (a business does things its
  blueprint never heard of). `--zone`, `--reference` (repeatable), `--strict`, `--json`,
  `--min-coverage`.
- **Nine rule codes, `ALN000`–`ALN008`**, owned by `align` rather than `validate`: a
  repository with no reference pack is not an invalid repository, and the model gate stays
  about the model. The flagship is `ALN005` — `out-of-scope` without a rationale is an
  *error*, and the node keeps reporting as a gap, so a silent exclusion excludes nothing.
- **`pin-reference`** — writes a pack's `SHA256SUMS`; the drop-in step after copying a
  reference model in, and the upgrade step after a reviewed change. Carries `pin-oracle`'s
  warning, for the same reason.
- **The open library, `references/`** — NIST CSF 2.0 (Functions and Categories; public
  domain, NOTICE citing NIST CSWP 29). Structure only: no normative wording is paraphrased,
  because a paraphrase in a YAML file gets quoted back as if it were the standard. It ships
  **labelled as an unverified draft yardstick** — see below.
- **Skill `ea-align`** (23 skills now) — choosing a reference honestly (what the
  organisation licensed and argues in, not what looks impressive), mapping as *judgement
  recorded*, out-of-scope as a decision with three parts, and where a gap goes next:
  `ea-intake` clarification question, modelling work, ADR, or the board agenda.

**Three design calls worth reading before the first mapping.**

*Only leaf nodes are scored, and `partial` counts half.* A branch is a heading, not
something an application realizes; branches carry their subtree's percentage instead.
Half credit for `partial` is the arithmetic the golden-set scorer already uses for a
derived relationship — found the connection, contested the grain.

*`out-of-scope` inherits down a branch; coverage never does.* Excluding an area is one
decision about one area, so one recorded rationale can account for a whole domain — much
better than nine copies of it. Claiming a branch covered would be a claim about every leaf
under it, and those are earned one at a time.

*Everything fails closed.* An exclusion with no rationale does not exclude (`ALN005`); a
claim resting on an element the zone does not hold does not cover (`ALN003`, `ALN007`).
Under-reporting a gap is the failure mode that matters, so every ambiguity resolves
towards *gap*. `--min-coverage` refuses to pass when nothing is in scope, rather than
reporting 100% of an empty set — the defect this repository has already paid for once.

### Added — the licensed-content boundary, stated where it can be enforced

BIAN, APQC PCF, eTOM and ACORD are the reference models organisations actually own, and
none may be redistributed here. The split is **mechanism here, content at the adopter**:
`template/reference/README.md` is the drop-in procedure, every shipped pack carries a
NOTICE naming its source and open status, and a test refuses a pack in `references/` whose
NOTICE does not state that status. `ea-align` says the rest out loud: an agent asked to
"add the BIAN service domains" from memory commits a licence breach and a fabrication at
once, and nobody downstream can tell an accurate transcription from a plausible one.

### Added — a verification status per shipped pack, because nothing can check it

The reference layer has no mechanical provenance check. One layer down every element's
quote is located in a real file; here, a Category name that is subtly wrong looks identical
to a correct one to `align` and to every adopter. The NIST pack was written from working
knowledge of CSF 2.0 rather than read off CSWP 29 node by node, so it ships saying so: its
NOTICE carries a **verification status** telling readers not to cite its nodes as evidence
of what NIST requires, and `references/README.md` repeats it in the table adopters read
first. A test asserts the two agree, because an unverified pack quietly losing its caveat is
how a draft yardstick becomes an authority.

The obligation and how to discharge it are written next to the pack: read the source, correct
or confirm `model.yaml`, drop the status section, re-pin, and say in the commit message that
the reading happened.

The worked example therefore ships `wholesale-core`, a small capability reference
**authored for it** and labelled as such — clean under `align --strict`, which means every
node of it is either answered by the model or excluded by a recorded decision. Two `partial`
mappings and one exclusion carry the notes that make them readable; a whole domain is
excluded by one decision its children inherit. `eval/fixtures/broken/reference/` holds five
packs, one per failure mode, each with valid pins of its own so the pack under test is the
one the rule is about.

### Changed

- `gen-schema` writes twelve schemas (`reference`, `reference-mappings` and `ea-config`
  added); the freshness test covers them by construction, from the same registry, and a
  doc test now pins the written count against it — "eleven" had gone stale silently once.
- CI and the CONTRIBUTING pre-push block gain `align --strict` on the worked example and
  the negative-fixture counterpart. `align` deliberately has **no `--as-of`**: nothing in
  reference alignment depends on a date, and a flag that only decorated the report header
  would be the decorative conformance the 0.11.0 review removed elsewhere.
- The negative fixture gains `model/staging/proposal.yaml`, without which `ALN007` had no
  provoking case.

## [0.11.0] — 2026-08-06 — the measurement release

The mechanism was complete; the product was under-measured. Six weaknesses were listed
rather than hedged, verified mechanically before anything was planned — which changed one
verdict, and found a seventh nobody had noticed.

### Added — ArchiMate's derivation rules (DR1–DR8)

`easkills/derive.py` implements Appendix B.2 of the specification: the eight derivations
that are *valid in any model where they apply*, with the structural strength order
(Realization weakest → Composition strongest), the B.4 restriction on deriving through a
third domain, and every derived edge filtered through the vendored relationship matrix.
The potential rules of B.3 stay out, by their own description: the specification calls them
uncertain, and a deterministic core does not guess.

This closes the measurement limit the first baseline reported. A run whose every element
matched still scored **0%** on relationships, because it routed `SchedPro → Dispatch`
through a process it invented — and gold's edge is *derivable* from the candidate's two by
DR4, a rule the standard states in one sentence. The scorer now gives such an edge **half a
match** (found the connection, contested the grain) and credits the candidate edges carrying
the derivation the same way. `docs/RULES.md` narrows its "not yet implemented" entry to B.3
and B.4 accordingly.

### Added — the score names what it did not match

Every category now carries `unmatchedGold`, `unmatchedCandidate`, `partialGold` and
`partialCandidate`: identifiers for facts and entities, `type name` for elements, and
`type source -> target` for relationships, with the derivation rule and the abstracted-away
element cited where half credit was given. The terminal prints the first eight per line;
`--json` carries all of them. Three separate investigations of a fallen category were
hand-diffs of two YAML trees before this existed, and each cost more than the run that
produced the number.

### Added — three more skills measured, and an honest coverage page

- **The harness reads five skills instead of two**, declared in `MEASURED_SKILLS` and pinned
  to its README by a test: `ea-intake`; `ea-model` + `ea-capability-map`; and a new
  *apparatus* phase reading `ea-stakeholders` + `ea-views`.
- **The apparatus phase is judged by contract, not by similarity.** Gold holds no
  stakeholders, concerns or views, and inventing them would make the number a similarity to
  one author's documentation taste. What is checkable is whether ISO 42010's loop closes, so
  the measurement is the `conformance` checklist the core computes — reported, never gated.
- **`eval/harness/contracts.py`** measures the governance skills the same way: a scenario
  plus `ea-adr` or `ea-dispensation`, then deterministic properties on the record produced —
  MADR fields, rejected options with pros *and* cons, a bounded expiry, a real standard
  waived, tight scope, and the three-move supersession that leaves no element realising a
  withdrawn decision (`CORR001`). `tests/test_contract_harness.py` proves each contract is
  satisfiable by a hand-written reference answer and that it fails on the specific mutation
  it exists to catch — an unsatisfiable contract looks exactly like a bad skill, forever.
- **`docs/SKILL-COVERAGE.md`** classifies all 22 skills by instrument — scored, contract,
  deterministic path test, or *manual only* — with the two `manual only` rows (`ea-run`,
  `ea-eval`) printed rather than quietly rounded up.

### Added — the adoption path as a deterministic test

`tests/test_adoption_path.py` walks the whole brownfield path on committed fixtures
(`eval/fixtures/adoption/`): scaffold from `template/`, a handed-over spreadsheet through
`intake-csv`, a foreign tool's export through `import`, the gate refusing the
`Serving`-from-a-Node-to-a-DataObject the previous tool allowed, the 2026-08-05 run's human
decisions recorded as code, one vouched-for slice promoted, `impact` in both zones, and an
architecture description generated. No network, no model.

Two end-to-end runs had found defects no unit test could see, both of the same kind —
output that is correct and *unusable*. That class now has a regression test.

### Changed — the regression gate reads the spread it measured

A median that falls **below the baseline's own minimum** is a regression and exits 1. A
median that falls but stays inside the measured spread is printed as a *movement*. With
three runs at API default temperature a three-point median move says nothing, and the first
comparison duly flagged one such beside a real one; a gate that cries wolf gets ignored.

### Fixed — the harness could report a previous run's numbers as this run's

The work directory is reused across invocations, and both report files (`*-score.json`,
`conformance.json`) were read back after the command that writes them. A scoring step that
failed while last week's file sat there would have been scored as a result. Both are now
removed before the command runs, and a test asserts that every file the harness reads back
is deleted first — the one failure mode a measurement harness must not have is a failure
that looks like a result.

### Fixed — a converted spreadsheet no longer loses a cell

`intake-csv` truncated any row wider than its header (a semicolon inside an unquoted cell is
enough) while the document politely said "truncated". Wide rows now widen the table under
generated column names, short rows are still padded, and the ragged rows are still reported:
a converted document is quoted from, so a dropped cell is evidence that cannot be cited.
Found by building the adoption fixture.

### Changed — the second baseline, and what it is and is not comparable to

Re-measured after all of the above (claude-sonnet-5, 3 runs per case, all six green on
their own gates): `clinic` facts 74% → **87%**, entities 67%, elements 43%, relationships
20%; `contested` facts 67%, entities 71%, elements **56%**, relationships 0% → **11%**;
apparatus 2–3 stakeholders, 3 concerns, 2–3 views with 7 ISO clauses passing per run.

Two of those moves are comparable to the old baseline and explained: `clinic/facts` gained
exactly the nine half credits the compound gold statements were costing, and `contested`
relationships came off zero because a gold edge the candidate reaches in two hops is now
recognised. The element-driven numbers are **not** comparable: adding `ea-capability-map` to
the measured phase changed the prose the runs read, and they duly produced a capability
layer against a `clinic` gold model that has none. The baseline was moved because the
instrument changed, with the reasoning written into `eval/harness/README.md` — and the
question that leaves (three runs, three identical capabilities, gold has no Strategy layer,
`ea-model` says the capability map is the spine) is recorded there and deliberately not
answered in the release that measured it.

The governance contracts held on every run, including the three-move supersession, for
≈25k input / 8k output tokens over six runs.

**Across tiers** (`clinic`, 3 runs each, informational — the baseline stays defined for the
default model): haiku-4.5 79/60/55/9, sonnet-5 87/67/43/20, opus-5 77/57/44/30
(facts/entities/elements/relationships). No tier dominates, so the prose is not tuned to
one; relationships improve monotonically with tier; and elements score *highest* on the
weakest model because two of its three runs produced no capability layer — the same
granularity effect, from the other side. A weaker model spends its budget on repairs: haiku
used 2.5× the input tokens for two-thirds of the output, which is what the three-iteration
cap exists to bound.

Two harness reporting fixes came out of reading those runs: the final gate verdict of each
phase is now recorded rather than inferred from the repair count (exhausting the cap and
converging on the last attempt produced the same number), and `baseline.json` is written
with LF newlines so its bytes do not depend on the author's operating system.

### Changed — gold's compound facts, split

`eval/golden/clinic` carried two compound statements — *"…through the online booking portal
**or by calling the front desk**"* and *"…inside the EHR**; we do not run a separate billing
system**"* — where `ea-intake` defines a fact as **one atomic statement**. Three measured
runs split both and were charged half credit nine times over for following the skill more
closely than the golden case did. The register is now nine atomic facts, the model's
provenance follows, and `eval/golden/README.md` gains the rule this establishes: a golden
case may be corrected against the skills' own stated rules, never against a run's output.

### Changed — the first skill fixes the harness paid for

Three prose defects, found by measurement rather than by reading, and re-measured after
the fix. Elements **doubled** on both golden cases; relationships came off the floor.

- **`ea-intake` named the kinds of thing that get an entity.** The step said "one entry
  per real-world thing" and every example around it was an application — so the runs
  produced entities for applications and nothing else, missing the actor, the
  integration and the server the same source named. Entity F1 44% → 71% on `clinic`.
- **`ea-model` gained a *Granularity* rule.** "Build the capability map first" plus a
  layer-by-layer list reads as a set of boxes to fill, and the runs filled them: 19–23
  elements from a seven-fact source, including a Current/Target state pair from a source
  describing no plan. The rule states the measured failure and forbids the specific
  move — inserting intermediate behaviour between two things a source connects directly.
  Elements 25% → 50% (`clinic`), 39% → 50% (`contested`); relationships 0% → 25%.
- **`ea-capability-map`'s "six to twelve capabilities" is now a shape, not a target.** A
  single interview supports the capabilities it names; reaching six by inventing four is
  what the skill's own rules of evidence exist to prevent.

The gate flagged two falls, and both were investigated rather than accepted or explained
away. `contested/entities` 83% → 80% is noise against a 67–86 spread. `clinic/facts`
83% → 74% is systematic: the candidate now writes ten facts where gold has seven,
splitting gold's *compound* statements — and `ea-intake` says a fact is one atomic
statement, so the run is arguably following the skill more closely than the golden case
does. Recorded as an open question about **gold**, not patched away in the scorer, and
the baseline was moved deliberately with that trade-off written down.

### Added — the golden-set harness: skill prose, measured

The core has 399 tests. The skills — which are the product — had none, because they are
prose an agent follows and pytest cannot execute them. `eval/harness/run.py` closes
that: it builds a scratch repository holding **only** a golden case's sources and
config, runs the skills blind through the pipeline they describe (chunk → intake →
evidence gate → model → model gate → promote), with the three-repair cap the skills
prescribe, and scores the result against gold.

- **`--runs 3` by default, reporting min/median/max per category.** Runs use the API
  default temperature; a single run says little about the skills and a lot about that
  sample. The spread is the honest part.
- **`baseline.json` makes it a gate.** A plain run compares medians against the
  committed baseline and exits 1 on a regression. Rewriting the baseline is a decision,
  taken with `--baseline`, never a side effect.
- **The core stays offline.** This is the first code in the repository that calls a
  network API, so the separation is structural rather than conventional:
  `tests/test_harness_quarantine.py` fails if any `easkills/` module imports an HTTP
  client or the SDK, if the core imports the harness, or if the SDK reaches
  `requirements.txt` — the same shape as the rule keeping `ui` out of artifact
  generators. `.env` is gitignored and a test asserts no secrets file is tracked.
- **Blindness is asserted on the harness's own source**: it may copy `facts/sources/`
  and `ea.config.yaml` out of a golden case and nothing else. A harness that leaked
  gold's register would report a perfect number forever, and the failure would look
  exactly like success.
- Not in the push gate, by design: it costs tokens and is non-deterministic. A separate
  `workflow_dispatch` workflow runs it on demand and uploads the records rather than
  committing them.

## [0.10.0] — 2026-08-05

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
