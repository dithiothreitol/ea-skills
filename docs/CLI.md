# CLI reference

```
python -m easkills <command> [flags]
```

Every command is deterministic given the repository state (and, where relevant, an
`--as-of` date). **Exit code 0** = gate passed; **1** = error-severity findings (or a
threshold breached); gates behave identically in a terminal and in CI. Output is
colorized only on interactive terminals (`NO_COLOR`/`FORCE_COLOR` respected); `--json`
outputs are always plain.

Commands that read the oracle (`validate`, `compile`, `render`, `docs`, `gen-schema`,
`oracle-info`) verify its SHA-256 pins first: drift is `ORACLE001` and the command
refuses, `--skip-validation` included. `promote` and `score` inherit the check by
running the model gate. `align` applies the same discipline to the *second* class of
pinned data — a reference pack whose `SHA256SUMS` do not verify is refused rather than
read (`ALN001`).

## Shared flags, and exactly where they apply

Flags are per-command — passing one where it does not exist is an argparse usage error
(exit 2), so this table is the map. A test
(`test_documented_flag_availability_matches_the_parser`) fails if it drifts from the
parser; `python -m easkills <command> --help` is the same information, per command.

| Flag | What it does | Commands |
|---|---|---|
| `--root <path>` | Repository root (default: cwd) | all except `gen-schema`, `pin-oracle`, `oracle-info` |
| `--zone approved\|staging` | Which zone to read; governance metadata is mandatory in `approved` | `validate`, `compile`, `render`, `impact`, `align`, `readiness` |
| `--strict` | Warnings fail too (on `conformance`: any failed clause fails; on `align`: gaps fail; on `readiness`: any open checkpoint fails) | `validate`, `validate-facts`, `validate-gov`, `conformance`, `check`, `align`, `readiness`, `dora-register` |
| `--as-of YYYY-MM-DD` | Evaluate date-dependent checks against a fixed date, for reproducibility | `validate-gov`, `staleness`, `kpi`, `debt`, `conformance`, `correspondences`, `roadmap`, `context`, `check`, `impact`, `dora-register`, `propose` (**required** there) |
| `--json <file>` | Write the machine-readable report alongside the rendered one. On `chunk` it takes **no argument** and prints JSON to stdout instead | `validate`, `validate-facts`, `validate-gov`, `staleness`, `kpi`, `debt`, `conformance`, `correspondences`, `delta`, `roadmap`, `coverage`, `score`, `chunk`, `check`, `import`, `impact`, `intake-csv`, `align`, `readiness`, `dora-register`, `propose` |
| `--out <path>` | Output file (or directory, for `render`) instead of the default location | `compile`, `render`, `docs`, `context`, `import`, `intake-csv`, `dora-register`, `propose` |
| `--skip-validation` | Build from a model with validation errors (not recommended) | `compile`, `docs` |
| `--scope <element-id>` | The element the command is about | `context`, `check`, `impact` |
| `--repo <path>` | The *consuming* repository being checked (`--root` stays the EA repository) | `check` |
| `--reference <name>` | The reference pack under `reference/` (repeatable on `align` and `propose --from align`, where the default is every pack present; required on `pin-reference`) | `align`, `pin-reference`, `propose` |

`align` and `readiness` have **no `--as-of`**: nothing in either depends on a date, and a
flag that only decorated the report header would be exactly the decorative conformance the
0.11.0 review removed elsewhere.

## Validation gates

| Command | Checks | Rules |
|---|---|---|
| `validate [--zone approved\|staging] [--strict] [--json]` | The model: schema, identifiers, references, provenance (quotes located in sources; fact references re-verified), governance metadata, ArchiMate 3.2 relationship matrix, structural cycles, motivation bindings, standards lifecycle, ISO 42010 loop, naming, smells. `staging` validates as an overlay on `approved`. | `ORACLE* SCHEMA* ID* REF* PROV* GOV* REL* MOT* STD* ISO* NAME* SMELL*` |
| `validate-facts [--strict] [--json]` | The fact register: schema, duplicate ids/statements, quotes located in sources, entity references and alias uniqueness, uncited sources. | `FACT* ENT* SRC*` |
| `validate-gov [--strict] [--as-of] [--json]` | Standards base, decisions, dispensations (expiry is loud), compliance assessments, service catalog and demand ledger (SLA hygiene). | `SIB* DEC* DISP* COMP* SVC* REQ*` |

Full catalogue with severities and rationale: [RULES.md](RULES.md).

## Build & publish

| Command | Does |
|---|---|
| `import --file <export>.xml [--out] [--ids names\|identifiers] [--json]` | ArchiMate Open Exchange XML → staging YAML proposals, written the way this repository authors models: elements per ArchiMate layer, relationships in `relations.yaml`, views in `views.yaml`. That split is what makes a slice promotable on its own — `--out` collapses it to one file, which cannot be. (Brownfield adoption.) Everything arrives `assumed` (claims, not evidence), owner/review metadata is lifted from exported properties, geometry is discarded, every rename/skip/mapping is in the report, and an existing file is never overwritten. The import does not judge the model — matrix-illegal content is left for `validate` to report. |
| `compile [--zone] [--out] [--skip-validation]` | DSL → ArchiMate Open Exchange XML (`build/model.xml`), XSD-validated offline, byte-stable. Refuses a model with errors. |
| `promote [--file <staging-file>]... [--dry-run]` | **The only write path into `approved/`.** Validates the *post-move* result by approved-zone standards — a staging file replaces the approved file of the same name, so the gate sees exactly what the move produces; on a clean gate moves the files, naming any approved concepts the replacement removes. Partial promotion supported. The git commit is the approval record. |
| `render [--zone] [--out]` | Views → deterministic SVG (`docs/views/`), no external toolchain. |
| `docs [--out] [--skip-validation]` | Renders views and generates the architecture description (ISO 42010 Clause 6 shape, TIME portfolio, capability support, open assumptions) from `approved/` only. Deterministic; commit the output — CI checks freshness. |

`--zone staging` means the same overlay everywhere (`validate`, `compile`, `render`): a
delta is read against the approved model it proposes to change.

## Intake

| Command | Does |
|---|---|
| `intake-csv --file <export>.csv [--out] [--overwrite] [--json]` | Converts a tabular export (CSV, and therefore Excel) into a citable source document in `facts/sources/`: a markdown table whose header records the original file's SHA-256, encoding and delimiter, so a verified quote stays traceable to the bytes it came from. Delimiter is chosen by consistent column count, not frequency; cells keep their pipes (escaped) and lose their line breaks (reported); ragged rows are padded and named. Nothing is interpreted — no column is mapped to a model field. |
| `chunk [--file <source>] [--max-chars N] [--json]` | Splits sources into deterministic extraction chunks with exact line ranges and stable ids. |
| `coverage [--min-coverage PCT] [--json]` | Which substantive source statements no fact cites, with line numbers — candidate clarification questions. Advisory unless the threshold gate is used. |

## Is it done?

| Command | Does |
|---|---|
| `readiness [--zone] [--strict] [--json]` | The per-layer definition of done: one checkpoint list per ArchiMate layer (Strategy, Business, Application, Technology, Motivation), each finding **naming the elements** that fail it — unsupported *and unexamined* capabilities, processes attached to neither a capability nor a service, components with no `lifecycle`/`timeDisposition`, services with no consumer, infrastructure serving nothing, obligations binding nothing, and layers the fact register covers while the model does not. **Nothing here is an error**: an unfinished layer is not a wrong model, and an empty layer is shown rather than flagged. `--strict` is how a repository that claims completeness gates on it. Rules: `RDY*`. |

## Reference alignment

| Command | Does |
|---|---|
| `align [--reference NAME]... [--zone] [--strict] [--min-coverage PCT] [--json]` | Two-way coverage against the reference architectures in `reference/<name>/` — a hash-pinned taxonomy plus a human-authored `mappings.yaml`. Per node: `covered`, `partial`, **gap**, or `out-of-scope` *with a recorded rationale*; per branch: a rolled-up percentage; plus the local elements the reference does not anchor, as information rather than findings. Only leaf nodes are scored (`partial` counts ½), an out-of-scope decision inherits down the tree while a coverage claim does not, and every ambiguity resolves towards *gap*. A pack whose pins do not verify is **refused, not read** (`ALN001`). Rules: `ALN*`. |
| `pin-reference (--reference NAME \| --dir PATH)` | Rewrites one pack's `SHA256SUMS` over `model.yaml` and `NOTICE.md` — the drop-in step after copying a reference model in, and the upgrade step after a reviewed change to one. Never a way to silence `ALN001`. `--dir` is for a pack that does not sit under a repository's `reference/`, such as the open library in [`references/`](../references/). |

## Maintenance & reporting

| Command | Does |
|---|---|
| `staleness [--as-of] [--json]` | Review-age per element, with per-element consumer **demand** and a `neverRequested` count; the queue orders by demand. |
| `kpi [--as-of] [--json]` | One screen: size, evidence share, governance health, TIME portfolio and obsolescence exposure, capability support, ISO loop state, and the service line (offerings, dispositions, SLA breaches, average fulfilment). |
| `debt [--as-of] [--json]` | EA-debt register from deterministic smell queries: isolated elements, hubs, unsupported capabilities, duplicate names, stale content, dead-standard references — plus the three overlap queries below. |
| `conformance [--strict] [--as-of] [--json]` | ISO/IEC/IEEE 42010:2022 Clause 6 checklist — `pass`/`fail` where checkable, explicit `gap` where not (never silent conformance). `--strict` exits 1 on any fail. |
| `correspondences [--as-of] [--json]` | ISO 42010 §6.9: every relation that crosses out of the model — into the governance log, into the fact register — with the rule it is held to and the code that enforces it. Derived from the records that already declare them, so the table cannot drift from the records. |
| `roadmap [--as-of] [--json]` | The Implementation & Migration layer read as a plan: plateaus in `plateauDate` order with what each holds, the gaps between them, and every Migrate/Eliminate disposition no plateau carries — a portfolio decision nothing schedules. |
| `delta [--json]` | Continuous-ingestion input: entities with no model counterpart, facts no concept cites. Candidates, not defects. |
| `impact --scope <element-id> [--zone] [--depth N] [--as-of] [--json]` | Blast radius of a change: transitive affected elements (nearest first, each with the relationship it travelled), the stakeholder groups reached through views and concerns, plus decisions, obligations, waivers, consumer requests and unowned elements inside it. Propagation direction is declared per relationship type; `Association` is reported as adjacency and never traversed. Computes the arithmetic half of the TOGAF Phase H test — the classification stays a recorded judgement. Unlike `docs`, it accepts `--zone staging`: the dangerous error here is a radius that looks *small*. |
| `context --scope <element-id> [--out] [--as-of]` | Agent context pack (AD-09): binding requirements via `appliesTo`, standards with waivers, applicable decisions, integration neighbours — approved-only, scope-filtered, opened by a mandatory freshness label. A Capability scope expands to its realizers. |

### Overlap and rationalization (`debt`)

Three queries answer "does this portfolio do one job twice?". They report; they never
conclude — redundancy is as often bought on purpose (resilience, data residency, a
strangler running beside what it replaces) as it is drift, and nothing in the model
distinguishes the two. What the register can do is print the data the decision needs.

| Item kind | Fires when | Extra JSON fields |
|---|---|---|
| `rationalization-candidate` | A `Capability` is realized by ≥2 **application components**. A business role realizing the same capability is division of labour, not duplication, and is not counted. | `realizers[]` — id, name and the full property map of each, rendered as `timeDisposition` and `lifecycle` first (stated as `not recorded` when unset) then every other property the operator keeps. |
| `overlapping-applications` | Two application components realize **≥2** of the same capabilities. One shared capability is already a candidate above; the *pair* is only a merge conversation once the overlap repeats. | `pair` (id-ordered, reported once) and `shared`. |
| `duplicate-service` | Two services share a name (whitespace- and case-insensitive) and are offered by **disjoint** providers. Unlike `duplicate-name` this crosses service types. Excluded: pairs already joined by a relationship — an application service realizing the identically named business service is idiomatic layering — and same-provider pairs, which are a naming slip, not portfolio duplication. | `duplicateOf`, `providers`, `otherProviders`. |

No new rule codes and no gate: these are report items, not findings, because "two systems
realize this" is a question for a human and a gate that answered it would be wrong half
the time. Routing lives in skill prose — `ea-health` for reading them, `ea-change-triage`
for classifying the change that lands on one, `ea-board` for the decision, and `ea-adr`
for the record that makes deliberate redundancy legible to the next reader.

### Costing the exposure (`costModel` in `ea.config.yaml`)

**The tool computes the exposure, the operator priced it.** That sentence is the feature.
Nothing in this repository knows what a stale element or an open waiver is worth, and
nothing here will guess: exposure is derived from the model and the governance log, and
turning it into money requires unit rates the operator writes down and can defend.

```yaml
costModel:
  currency: EUR            # required — an unlabelled amount is read in whatever
                           # currency the reader assumes
  staleElementDay: 1.5     # per element, per day past `stalenessDays`
  openDispensationDay: 12  # per open dispensation, per day since it was granted
  eolElement: 4000         # per element on a deprecated or retired standard
  unsupportedCapability: 8000   # per capability nothing realizes
  duplicateRealization: 15000   # per realizer beyond the first on one capability
```

Every rate is optional; the block as a whole is optional. **With no `costModel`, `debt`
output is byte-identical to a release without this feature** — no section, no key in the
`--json`, not one character. Amounts use decimal arithmetic, and every quantity is
measured against `--as-of`, never the wall clock, so a figure pasted into a board pack
reproduces a month later.

The section states what it left out, next to the total, because a partial total that
looks complete is the number that reaches a slide:

- **Not priced** — an exposure with a real quantity and no configured rate. Set the rate
  or read the total as a floor.
- **Not measurable** — elements with no review date contribute no element-days. They are
  named rather than counted as zero: "we cannot tell" and "it costs nothing" are
  different answers.

Rate keys are a closed vocabulary in `ea-config.schema.json`; a misspelled one is
`SCHEMA002`, not a silent zero. Unknown *top-level* config keys are errors too — unlike
an element's deliberately open `properties` map, a tooling key this tooling does not read
is always a typo, and `stalenessDay` leaves the 365-day default in place while the
repository looks fresh.

## Findings into proposals

| Command | Does |
|---|---|
| `propose --from align\|readiness\|overlap --as-of <date> [--reference NAME] [--out] [--json] [--dry-run]` | Turns one report's findings into **staging skeletons**: a reference gap becomes a `Requirement` (a `Constraint` for a `kind: control` node), an open readiness checkpoint (warning severity — what `readiness --strict` gates on) becomes a `Constraint` bound to its element via `appliesTo`, a rationalization candidate becomes a `WorkPackage` *naming* its realizers. Writes `model/staging/proposed-*.yaml`. |

Everything it writes is `assumed: true` with a rationale naming the finding and the date
it came from, and **every documentation field opens with `PROPOSED --`** — a loud,
greppable marker so a half-finished stub cannot pass for something an architect wrote.
The generator supplies ids, types and bindings; it supplies **no prose**, because text
that reads as authored and is not is the same failure as a fabricated quote one layer up.
What a good requirement says lives in [`ea-align`](../skills/ea-align/SKILL.md).

The importer's discipline, borrowed whole:

- **Never overwrites.** An existing target file is a refusal, not a merge.
- **Ids are derived, never counted** — `req-<pack>-<node>`, `con-<element>-<code>`,
  `wp-rationalize-<capability>`. Re-running after fixing three of ten findings proposes
  the same seven ids, so the diff is the news. An id already in either zone is skipped
  **by name**: somebody already acted on that finding, and saying so beats both silence
  and failing the whole run.
- **Output is byte-stable** for identical inputs, which is what makes re-run-and-diff a
  safe habit.
- **Promotion still blocks.** A stub validates in `staging` and cannot leave it: an owner
  and a review date are a human's to supply. Generation is cheap, vouching is not, and
  the gate is where that asymmetry is enforced.
- **It refuses rather than guessing.** A source report with errors (an unreadable
  `mappings.yaml` makes every leaf look like a gap), an id that would break the schema,
  or two findings deriving one id — each is a refusal naming the finding, never a staging
  file the gate would reject and a re-run would reproduce.

Only the `WorkPackage` differs on binding, and the reason is worth knowing: `appliesTo`
is the **Motivation layer's** applicability selector, so `MOT002` makes it an error on an
Implementation & Migration element. The realizers go in `properties.rationalizes` and in
the placeholder instead. The rule is also right on the substance — *which* relationship a
work package has to a component is the decision the package exists to take, and a
generator picking one would be answering the question it was asked to raise.

`--as-of` is **required here and nowhere else**. Every other command *reports* a date;
this one writes it into a file that gets committed, and a wall-clock stamp would make the
same repository produce a different file tomorrow.

## Regulatory reporting

| Command | Does |
|---|---|
| `dora-register [--as-of] [--out] [--json] [--strict]` | Generates the DORA **Register of Information** from the approved model: ICT third-party providers, contractual arrangements, the services in scope with their criticality, the business functions depending on them, and the open dispensations covering any of it. Scope is `properties.regulatoryScope: dora` on the element — declared, never inferred from a type. Rules: `REG*`. |

**A generator, not an attestation.** The document's structure follows the shape the ESAs'
implementing technical standards ask for; its content comes from the model and nowhere
else; no legal review has happened and no completeness against the official templates is
claimed. The generated file carries that paragraph in its own header, *above* the tables.

Its last section is the reason it is safe to hand over: **the register names its own
gaps** — every field the template wants that the model does not carry, with the element
ids missing it. A register that quietly omitted what it could not fill would be
indistinguishable from a complete one.

With **nothing in scope, no document is produced at all** and the command reports why.
That is the right answer for an organisation the regulation does not apply to (the worked
example is a food wholesaler, and is deliberately left out of scope) and the wrong one for
an organisation that has simply not tagged its ICT services yet — the message says which
question you are looking at. `--out` refuses rather than writing an empty page.

Control-framework gaps are not part of this command. A control framework is a taxonomy,
so it rides the reference mechanism: a pack with `kind: control` nodes, and an unmapped
control is `ALN004`. See [`ea-regulatory`](../skills/ea-regulatory/SKILL.md).

## Consuming repositories

| Command | Does |
|---|---|
| `check --scope <element-id> [--repo <path>] [--strict] [--as-of] [--json]` | Runs in a *product* repository's CI: reads its dependency manifests (`package.json`, `pom.xml`, `requirements.txt`) and reports them against the standards its EA element claims — retired without a waiver is an error, deprecated warns, a covering dispensation is reported with its expiry, and a governed dependency the model does not record comes back as drift. Detection is declared by each SIB entry (`detect:`), never inferred, and the consuming repository maintains no integration manifest: `--scope` is the whole convention. |

## Evaluation

| Command | Does |
|---|---|
| `score --gold <repo> [--min-f1 PCT] [--json]` | Candidate vs golden repository: precision/recall/F1 for entities, facts, elements and relationships, plus the candidate's own gates — matching gold while failing provenance verification counts as failure. Names resolve through both entity alias tables, facts are matched on the source ground they cover, a type disagreement inside one layer is half a match, an edge the candidate does not draw but its model *implies* under ArchiMate's derivation rules (DR1–DR8) is half a match, and a label-independent relationship count is reported as an ungated diagnostic. Every category also **names its items**: what gold had and the candidate missed, what the candidate has and gold does not support, and which credits were half (with the derivation rule cited) — eight per line in the terminal, all of them under `--json`. It measures **agreement with one gold repository** — a regression signal, not an absolute grade ([what that means](../eval/golden/README.md)). |

## Housekeeping

| Command | Does |
|---|---|
| `gen-schema` | Regenerates every JSON Schema under `schema/` — all twelve, from one registry, each freshness-tested against its committed copy (the model schema derives from the oracle, so a stale one would accept what the validator rejects). |
| `oracle-info` | Oracle version, concept coverage, checksum pin status. |
| `pin-oracle` | Rewrites the SHA-256 pins — only for deliberate, reviewed oracle upgrades; never to silence `ORACLE001`. |

## Exit-code contract, in one table

| Code | Meaning |
|---|---|
| 0 | Gate passed (warnings allowed unless `--strict`). |
| 1 | Error-severity findings; a threshold gate breached (`--min-coverage`, `--min-f1`, `--strict` on `conformance`); a refusal (`compile`/`docs` on an invalid model, `promote` blocked); an unknown scope/path. |
| 2 | CLI usage error (argparse). |
