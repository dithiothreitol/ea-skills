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
running the model gate.

## Shared flags, and exactly where they apply

Flags are per-command — passing one where it does not exist is an argparse usage error
(exit 2), so this table is the map. A test
(`test_documented_flag_availability_matches_the_parser`) fails if it drifts from the
parser; `python -m easkills <command> --help` is the same information, per command.

| Flag | What it does | Commands |
|---|---|---|
| `--root <path>` | Repository root (default: cwd) | all except `gen-schema`, `pin-oracle`, `oracle-info` |
| `--zone approved\|staging` | Which zone to read; governance metadata is mandatory in `approved` | `validate`, `compile`, `render` |
| `--strict` | Warnings fail too (on `conformance`: any failed clause fails) | `validate`, `validate-facts`, `validate-gov`, `conformance` |
| `--as-of YYYY-MM-DD` | Evaluate date-dependent checks against a fixed date, for reproducibility | `validate-gov`, `staleness`, `kpi`, `debt`, `conformance`, `context` |
| `--json <file>` | Write the machine-readable report alongside the rendered one. On `chunk` it takes **no argument** and prints JSON to stdout instead | `validate`, `validate-facts`, `validate-gov`, `staleness`, `kpi`, `debt`, `conformance`, `delta`, `coverage`, `score`, `chunk` |
| `--out <path>` | Output file (or directory, for `render`) instead of the default location | `compile`, `render`, `docs`, `context` |
| `--skip-validation` | Build from a model with validation errors (not recommended) | `compile`, `docs` |

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
| `compile [--zone] [--out] [--skip-validation]` | DSL → ArchiMate Open Exchange XML (`build/model.xml`), XSD-validated offline, byte-stable. Refuses a model with errors. |
| `promote [--file <staging-file>]... [--dry-run]` | **The only write path into `approved/`.** Validates the *post-move* result by approved-zone standards — a staging file replaces the approved file of the same name, so the gate sees exactly what the move produces; on a clean gate moves the files, naming any approved concepts the replacement removes. Partial promotion supported. The git commit is the approval record. |
| `render [--zone] [--out]` | Views → deterministic SVG (`docs/views/`), no external toolchain. |

`--zone staging` means the same overlay everywhere (`validate`, `compile`, `render`): a
delta is read against the approved model it proposes to change.
| `docs [--out] [--skip-validation]` | Renders views and generates the architecture description (ISO 42010 Clause 6 shape, TIME portfolio, capability support, open assumptions) from `approved/` only. Deterministic; commit the output — CI checks freshness. |

## Intake

| Command | Does |
|---|---|
| `chunk [--file <source>] [--max-chars N] [--json]` | Splits sources into deterministic extraction chunks with exact line ranges and stable ids. |
| `coverage [--min-coverage PCT] [--json]` | Which substantive source statements no fact cites, with line numbers — candidate clarification questions. Advisory unless the threshold gate is used. |

## Maintenance & reporting

| Command | Does |
|---|---|
| `staleness [--as-of] [--json]` | Review-age per element, with per-element consumer **demand** and a `neverRequested` count; the queue orders by demand. |
| `kpi [--as-of] [--json]` | One screen: size, evidence share, governance health, TIME portfolio and obsolescence exposure, capability support, ISO loop state, and the service line (offerings, dispositions, SLA breaches, average fulfilment). |
| `debt [--as-of] [--json]` | EA-debt register from deterministic smell queries: isolated elements, hubs, unsupported capabilities, duplicate names, stale content, dead-standard references. |
| `conformance [--strict] [--as-of] [--json]` | ISO/IEC/IEEE 42010:2022 Clause 6 checklist — `pass`/`fail` where checkable, explicit `gap` where not (never silent conformance). `--strict` exits 1 on any fail. |
| `delta [--json]` | Continuous-ingestion input: entities with no model counterpart, facts no concept cites. Candidates, not defects. |
| `context --scope <element-id> [--out] [--as-of]` | Agent context pack (AD-09): binding requirements via `appliesTo`, standards with waivers, applicable decisions, integration neighbours — approved-only, scope-filtered, opened by a mandatory freshness label. A Capability scope expands to its realizers. |

## Evaluation

| Command | Does |
|---|---|
| `score --gold <repo> [--min-f1 PCT] [--json]` | Candidate vs golden repository: precision/recall/F1 for entities, facts, elements and relationships, plus the candidate's own gates — matching gold while failing provenance verification counts as failure. |

## Housekeeping

| Command | Does |
|---|---|
| `gen-schema` | Regenerates every JSON Schema under `schema/` — all nine, from one registry, each freshness-tested against its committed copy (the model schema derives from the oracle, so a stale one would accept what the validator rejects). |
| `oracle-info` | Oracle version, concept coverage, checksum pin status. |
| `pin-oracle` | Rewrites the SHA-256 pins — only for deliberate, reviewed oracle upgrades; never to silence `ORACLE001`. |

## Exit-code contract, in one table

| Code | Meaning |
|---|---|
| 0 | Gate passed (warnings allowed unless `--strict`). |
| 1 | Error-severity findings; a threshold gate breached (`--min-coverage`, `--min-f1`, `--strict` on `conformance`); a refusal (`compile`/`docs` on an invalid model, `promote` blocked); an unknown scope/path. |
| 2 | CLI usage error (argparse). |
