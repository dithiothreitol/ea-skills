# ea-skills

Claude Code skills for the whole enterprise-architecture lifecycle -- **define,
document, govern, maintain** -- turning unstructured input into a validated ArchiMate
3.2 model, generated views and standards-shaped documentation, in git.

The design principle is narrow and load-bearing:

> **The model supplies judgement. The tooling supplies proof.**
> Anything a language model asserts about ArchiMate semantics, or about what a source
> document says, is checked by code against vendored primary-source data before it can
> enter the repository.

That inverts the usual arrangement, and it is deliberate: relationship semantics is the
weakest measured capability of language models on modelling tasks, and fabricated source
citations are a documented failure mode. Both are exactly the kind of thing a validator
catches for free and a reviewer catches at 3pm on a Friday, if at all.

**Status: all planned phases complete, plus the service layer.** The deterministic
core (DSL, three-layer validator, Open Exchange compiler), intake (fact register,
chunker, coverage), modelling (fact-referencing provenance, motivation layer, overlay
staging, gated promotion), documentation (stakeholder/concern register, SVG
rendering, ISO 42010-shaped description), governance (standards base with lifecycle
enforcement, dispensations that expire loudly, decision and compliance records,
health reports, agent context packs), the golden-set evaluation harness and the
Architecture-as-a-Service layer (offering catalog with SLAs, demand ledger,
demand-weighted maintenance) all work and are tested; twenty skills drive them (see
[Roadmap](#roadmap)).

## What exists today

```bash
python -m pip install -r requirements.txt

# Split raw sources into deterministic extraction chunks (exact line numbers)
python -m easkills chunk --root eval/example

# Validate the fact register: every quote located in its source (exit 1 on any error)
python -m easkills validate-facts --root eval/example

# Which parts of the sources produced no facts -- candidate clarification questions
python -m easkills coverage --root eval/example

# Validate a model repository (exit 1 on any error -- use it as a CI gate).
# 'staging' validates as an overlay on 'approved': proposals may reference approved content.
python -m easkills validate --root eval/example
python -m easkills validate --root eval/example --zone staging

# Promote staging into approved -- the only write path. The gate validates the merged
# result by approved-zone standards; --dry-run shows the verdict and the plan.
python -m easkills promote --root eval/example --dry-run

# Compile to ArchiMate Open Exchange XML, validated against the Open Group XSDs
python -m easkills compile --root eval/example

# Render views to deterministic SVG and generate the architecture description
# (ISO 42010 Clause 6 shape, application portfolio with TIME quadrants, open
# assumptions) -- from the approved zone only.
python -m easkills docs --root eval/example

# Governance: validate the standards base and governance log (dispensations that
# expire loudly, decisions with mandatory rationale, six-level compliance verdicts)
python -m easkills validate-gov --root eval/example

# Maintenance: health reports and the continuous-ingestion delta
python -m easkills kpi --root eval/example
python -m easkills debt --root eval/example
python -m easkills staleness --root eval/example
python -m easkills conformance --root eval/example   # ISO 42010 Clause 6 checklist
python -m easkills delta --root eval/example         # fact register vs model

# AD-09: a scoped, freshness-labelled context pack for agents working downstream
python -m easkills context --root eval/example --scope app-erp-core

# Regression harness: score a pipeline run against a golden case (P/R/F1 + gates)
python -m easkills score --root <candidate> --gold eval/golden/clinic --min-f1 90
```

Output is colorized on interactive terminals (severity-coded findings, green/red
verdicts, dimmed paths) and degrades to plain text in pipes, CI logs and captures --
colour is display, never data, so exit codes and grep-ability stay the interface.
`NO_COLOR` disables styling, `FORCE_COLOR` forces it.

The worked example (`eval/example/`) is a small fictional B2B food manufacturer: a fact
register of twenty-five facts and eleven entities covering 100% of the source
statements, and seventeen elements from goal and capability map down to database, every one
traceable to a quote in `facts/sources/`, four concern-framed views, a generated
architecture description, zero findings.
`eval/fixtures/broken/` is its opposite -- every rule in the catalogue violated on
purpose, so the test suite can prove each rule actually fires.

```
$ python -m easkills validate --root eval/example
EA model validation -- zone 'approved' at .../eval/example
ArchiMate oracle 3.2; 17 elements, 15 relationships, 4 views

INFO    PROV006  model/approved/strategy.yaml:elements[3] [goal-shorten-lead-time]
         assumed, pending confirmation: Inferred from operational pain described in the
         interview, not stated as a goal by any stakeholder. Needs confirmation at the
         next architecture board.

0 error(s), 0 warning(s) -- PASS
```

And what a real catch looks like:

```
ERROR   REL001  model/approved/broken.yaml:relationships[1] [rel-swapped]
         Realization from BusinessProcess 'process-invoicing' to ApplicationComponent
         'app-finance' is not permitted by the ArchiMate 3.2 relationship matrix.
         Permitted here: Association, Flow, Serving, Triggering -- it is permitted in the
         opposite direction, so the endpoints are probably swapped
```

## How it works

**Authoring format is fragmented YAML** (`model/<zone>/*.yaml`), so git diffs stay
reviewable at concept level. Open Exchange XML is a build artifact, never hand-edited.
Identifiers are author-supplied stable slugs, so re-running a pipeline produces a
reviewable diff rather than a rewrite.

**Two zones, one write path.** `staging/` holds machine proposals; `approved/` holds
human-signed content. Staging validates as an *overlay* on approved (a proposal may
reference approved elements; re-using an id proposes an update), so skills model the
delta rather than copying the world. The only way into `approved` is
`python -m easkills promote`, whose gate validates the merged result by approved-zone
standards -- ownership and review dates, advisory while drafting, block there. The git
commit of the move is the approval record.

**The motivation layer binds, mechanically.** Requirements, constraints, principles
and goals carry an `appliesTo` selector naming the elements they bind; the validator
checks every binding resolves and that selectors stay on motivation elements. Model
concepts may cite facts (`provenance: [{fact: ...}]`) instead of repeating quotes --
the validator resolves the fact and re-verifies its quotes, keeping one evidence base.

**Intake comes first and is measured.** `ea-intake` extracts a **fact register**
(`facts/register/*.yaml`) from raw sources chunk by chunk: atomic statements, each with
a verbatim quote the validator locates mechanically, plus an entity table
(`facts/entities.yaml`) so "the portal" and "Order Portal" stay one thing. Facts have
no `assumed` escape hatch -- what the sources do not say becomes a clarification
question, and the coverage report lists every source statement no fact cites, with
line numbers, so "we ingested everything" is a checked claim rather than a felt one.

**Every model concept is evidenced or declared.** Each element and relationship carries
`provenance` (source file plus verbatim quote) which the validator locates in the actual
file, or `assumed: true` with a rationale, which surfaces as an open question. There is
no third option -- and no way to quietly invent an element.

```yaml
elements:
  - id: app-erp-core
    type: ApplicationComponent
    name: ERP Core
    owner: finance-systems@aurorafoods.example
    lastReviewed: 2026-06-30
    properties:
      timeDisposition: Tolerate     # portfolio views come free, not from re-modelling
      lifecycle: active
    provenance:
      - file: facts/sources/interview-operations-2026-07-15.md
        quote: The ERP core holds the master order records and does the invoicing
```

**Views declare content, not geometry -- and a purpose.** A view lists which elements
to show and which declared stakeholder concerns it frames (ISO 42010's loop:
stakeholder ↔ concern ↔ view, closed by the `ISO*` rules). The compiler computes a
deterministic layered layout; the renderer draws the same layout as dependency-free,
byte-stable SVG. Neither a person nor a model hand-places coordinates, so diffs stay
about architecture.

**Governance is records + gates + diffs, git-native.** Standards live one per file
with a lifecycle; an element referencing a retired standard is an *error* unless an
open dispensation covers it -- and dispensations carry a schema-mandatory expiry that
turns into an error the day it passes, so exceptions stay governed instead of silent.
Decisions are MADR-shaped with mandatory rationale (ISO 42010 §6.10); compliance
verdicts use TOGAF's six levels, and a non-conformant verdict with no follow-up is
flagged. The git commit of any record is its audit trail.

**EA runs as a service, and demand steers maintenance (AD-10).** The catalog
(`services/`) defines what EA provides -- every offering with a named owner, a
fulfilment path and an SLA in days, schema-mandatory. The demand ledger
(`governance-log/requests/`) records who asked for what: fulfilment must point at
the deliverable, refusals need a written reason, and an open request past its SLA is
flagged and lands in KPI as a breach. Demand then feeds back: the staleness review
queue orders by how often consumers actually ask about an element, and
never-requested content is named a de-scoping candidate -- architecture grows
on demand, and rots only where nobody is looking anyway.

**The model governs agents, not just people (AD-09).** `python -m easkills context
--scope <system>` produces a scoped extract for coding agents in downstream repos:
binding requirements via `appliesTo`, standards with lifecycle and waivers, applicable
decisions, integration neighbours -- opened by a mandatory freshness label, because a
stale model served as binding constraints carries false authority.

**Documentation is generated, committed, and provably fresh.** `python -m easkills
docs` produces the architecture description (Clause 6 shape: stakeholders → concerns
→ views, plus portfolio TIME quadrants, capability support and every open assumption)
from `model/approved/` only. Output is deterministic -- the "as of" date is the newest
`lastReviewed` in the model, not the wall clock -- so the generated files are
committed and CI fails when they go stale.

**The oracle is vendored and hash-pinned.** Semantic rules come from Archi's
`relationships.xml` (the ArchiMate 3.2 permitted-relationship matrix, 11 569
combinations) and the Open Group exchange schemas -- not from rules typed from memory,
and genuinely not fetched at runtime: schema building runs with the network disabled at
parser level, and a test proves it. See [`oracle/NOTICE.md`](oracle/NOTICE.md). The JSON
Schema for the DSL is *generated* from the same oracle, so the authoring format cannot
drift from the validator.

Full rule list with severities: [`docs/RULES.md`](docs/RULES.md). Design rationale and
the research behind it: [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md).

## Standards position

| Concern | What is used | How |
|---|---|---|
| Notation | **ArchiMate 3.2** | Primary. Enforced from the machine-readable matrix, exported as Open Group Model Exchange XML. |
| Architecture description | **ISO/IEC/IEEE 42010:2022** | Documentation structure and conformance checking: stakeholders, concerns, viewpoints, views, correspondences, decisions with rationale. Phase 3--4. |
| Method and governance | **TOGAF 10** | Used as vocabulary and for governance mechanics (conformance levels, dispensations with expiry, Phase H change classes, Architecture Repository layout) -- *not* as a process to march through. |
| Detail design | **UML** | Secondary, where ArchiMate is too coarse (sequences, deployment). |
| Decisions | **MADR** | Architecture decision records in the governance log. |

On TOGAF specifically: the empirical case-study literature finds that even
self-described TOGAF practices do not follow the ADM or use the Content Framework, and
that the single most-used EA artifact in practice -- the business capability map -- is not
in TOGAF's content metamodel at all. So this repository targets the artifact set
practitioners are documented to actually use (capability map first, then landscapes,
inventories, roadmaps, principles, standards, solution overviews, decision records) and
implements TOGAF where it is genuinely strong: governance mechanics.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| **0** | DSL + JSON Schema, three-layer validator, Open Exchange compiler, oracle pinning, worked example, negative fixtures, test suite | **done** |
| **1** | `ea-intake`: chunked extraction with a gleaning pass, entity resolution, mechanically verified provenance, clarification questions where sources are thin | **done** |
| **2** | Modelling pipeline: capability map as spine, fact-referencing provenance, motivation layer with `appliesTo` selectors (AD-09), staging-as-overlay validation, gated promotion (`ea-approve`) | **done** |
| **3** | Stakeholder/concern register with the ISO 42010 loop enforced (`ISO001`-`006`), dependency-free byte-stable SVG rendering, generated architecture description with portfolio and capability outputs (`ea-stakeholders`, `ea-views`, `ea-docs`) | **done** |
| **4** | Governance and maintenance: standards base with lifecycle enforcement (`STD*`/`SIB*`), dispensations with mandatory, loud expiry (`DISP*`), MADR decisions (`DEC*`), six-level compliance (`COMP*`), Phase H change triage, delta ingestion, EA-debt register, staleness + KPI reports, 42010 conformance checklist, `ea-context` agent packs (AD-09) | **done** |
| **5** | Golden-set regression harness (`score` with P/R/F1 per category and a `--min-f1` gate, `eval/golden/`), `ea-eval` + `ea-run` skills, and the maintained capability comparison above | **done** |
| **6** | Service layer (AD-10, Architecture-as-a-Service / on-demand): offering catalog with schema-mandatory owners and SLAs (`SVC*`), demand ledger with evidenced fulfilment and SLA hygiene (`REQ*`), demand-weighted staleness, service KPIs, `ea-service` skill, catalog-first routing | **done** |

All planned phases are complete. Open items carried deliberately: `ea-check`
(compliance linting inside consuming repositories) stays deferred per AD-09 pending
the correspondence-mapping decision; ISO 42010 §6.9 correspondences remain an
explicit gap in the conformance checklist; the comparison table above has a monthly
re-check obligation.

Phase 4 is the point of the project, not an afterthought. Model *generation* is
crowded; governing and maintaining a validated ArchiMate repository over time is not.

## Honest positioning

There is no shortage of adjacent work: Claude skills that advise on TOGAF, MCP servers
that manipulate Archi models, tools that lint architecture-as-code in bespoke YAML,
markdown-only governance frameworks, and commercial platforms with real ingestion
agents. Several close neighbours appeared in mid-2026 and are moving quickly.

What is not otherwise available is the *combination*. The eight capabilities from the
design research, against the closest neighbours:

| Capability | ea-skills | mcp-archimate | 7bots / archimate-deep-agent | Transitrix | ArcKit | Ardoq |
|---|---|---|---|---|---|---|
| Packaged as agent skills | ✓ | — (MCP server) | — (platform) | partial (plugins) | ✓ | — (SaaS) |
| Unstructured-input ingestion | ✓ verified quotes | — | ✓ | ✓ | partial | ✓ |
| Real ArchiMate model files (Open Exchange) | ✓ XSD-validated | ✓ | ✓ | — (custom YAML) | — (markdown) | — |
| Generated views | ✓ deterministic SVG | ✓ | — | — | — | ✓ |
| Per-element source traceability | ✓ mechanically verified | — | ✓ claimed | partial | ✓ doc-level | partial |
| Deterministic semantic validation | ✓ vendored 3.2 matrix | ✓ | — | ✓ (own rules) | — | partial |
| Standards-shaped documentation (ISO 42010) | ✓ + conformance checklist | — | — | — | — | — |
| Governance + maintenance (SIB, dispensations with expiry, debt, staleness, agent context packs) | ✓ | — | — | partial (PR gate) | partial (docs) | partial |

Verified against the 2026-07-29 competitive survey behind
[`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) (§8 lists the projects and what each is
strongest at); the ea-skills column reflects this repository as of 2026-08-03.
Neighbours move fast -- **re-check monthly**, and correct this table when a claim
stops being true. Each capability exists somewhere; the integration is the
contribution, and the governance end is where it is thinnest elsewhere.

## Repository layout

```
easkills/        deterministic tooling (oracle, DSL, validator, compiler, CLI)
oracle/          vendored, hash-pinned rule data + NOTICE.md
schema/          model.schema.json -- generated from the oracle
skills/          the Claude Code skills
template/        scaffold to copy for a new enterprise
eval/example/    worked example, clean (doubles as the largest golden case)
eval/golden/     golden-set cases for the regression harness (see its README)
eval/fixtures/   negative fixtures, deliberately broken
tests/           pytest suite
docs/            BLUEPRINT.md (design + research), RULES.md (rule catalogue)
```

## Development

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest tests -q          # 220 tests
.venv/Scripts/python -m easkills oracle-info     # oracle version + pin status
.venv/Scripts/python -m easkills gen-schema      # regenerate the DSL schema
```

Licence: MIT for the code in this repository. The vendored oracle files are third-party
material with their own terms -- see [`oracle/NOTICE.md`](oracle/NOTICE.md).
