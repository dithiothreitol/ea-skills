# EA Skills Repository — Verified Blueprint
**Research-verified design for a Claude Code skills repository covering the full enterprise-architecture lifecycle: define → document → govern → maintain.**
Research date: 2026-07-29. All claims below are backed by the four research reports (competitive sweep, standards depth, toolchain verification, LLM-EA research grounding); key sources inline.

---

## 1. Uniqueness verdict (honest version)

**The gap is real as of 2026-07-29, but it is integrational, not inventional — and it is closing fast.**

- No project (open-source or commercial) combines all eight capabilities: **(1)** packaged as Claude Code skills, **(2)** unstructured-input ingestion, **(3)** real ArchiMate model files (Open Exchange / Archi format), **(4)** generated views, **(5)** per-element source traceability, **(6)** deterministic validation, **(7)** standards-compliant documentation, **(8)** governance + maintenance.
- Velocity risk is severe: 7 of the 10 closest competitors were created after 2026-06-01. Two "evidence → traceable ArchiMate model" multi-agent platforms (7bots-mvp, archimate-deep-agent) appeared **2026-07-25** — four days before this research.
- Every individual capability is commoditized (byrondelgado/mcp-archimate has model+validation+views; ArcKit has governance-of-documents at 2.1k stars; Transitrix has deterministic linting + PR governance on custom YAML; rnovicky proves skills can author Open Exchange XML directly).
- **Defensible differentiation must therefore rest on**: (a) the governance + maintenance end of the lifecycle — the least-served stage in ArchiMate-native OSS; (b) deterministic validation quality; (c) mechanically verified traceability; (d) ISO 42010:2022 conformance checking (nobody has it); (e) a published capability-comparison table maintained in the README.
- **Ship fast.** The claim "first comprehensive treatment" has a shelf life measured in weeks/months, not years.

## 2. Verified assumptions — what survived, what changed

| Original assumption | Verdict | Evidence |
|---|---|---|
| Model-first, not diagram-first | **CONFIRMED, strengthened** | coArchi2 independently converged on "one model file per git repo"; all serious competitors that matter are model-first; diagram-only projects are commodity |
| TOGAF 10 ADM as process backbone | **REVISED — demoted to vocabulary + governance mechanics** | Kotusev (27–47 orgs): even self-described TOGAF shops do not use the ADM or Content Framework; the most-used artifact (Business Capability Model) is not even in TOGAF's content metamodel |
| ArchiMate 3.2 as primary notation | **CONFIRMED** | Only tool-neutral standard with XSD-validatable exchange format; machine-readable relationship matrix exists (Archi's `relationships.xml`, 11,569 allowed pairs, version 3.2) |
| ISO 42010 as documentation frame | **CONFIRMED, upgraded to differentiator** | 2022 edition Clause 6 gives a checkable conformance list (stakeholders ↔ concerns ↔ viewpoints ↔ views ↔ correspondences ↔ decisions); no competitor implements it |
| Deterministic validation gate | **CONFIRMED, oracle found** | LLM relationship semantics is the weakest capability (relationships F1 far below elements — MODELS 2023/2024; correctness not statistically above neutral — Ferrari et al.); Archi's `relationships.xml` + `relationships-keys.xml` is the authoritative rule table |
| Traceability to source | **CONFIRMED, must be mechanically verified** | LLMs fabricate citations (rationales citing non-existent sentences — Pagels/Hacks/Bemthuis SAC 2026); provenance must be string/fuzzy-matched against sources, never trusted |
| Governance/maintenance coverage | **NEW — was missing, now the anchor** | Repository staleness is the canonical EA death mode; TOGAF governance mechanics (dispensations with expiry, 6-level conformance, Phase H change triage, SIB lifecycle) are the most automatable and least-served part of the standard |

## 3. Architecture decisions (ADR-style)

**AD-01 — Authoring format: fragmented YAML DSL; interchange formats are build artifacts.**
Source of truth = YAML files (one per element group / view / governance record) validated by JSON Schema. A compiler produces Open Exchange XML, validated against the vendored Open Group XSDs. This resolves the fragmentation-vs-single-file tension: git diff granularity at the YAML level (GRAFICO-style benefit), tool interop at the artifact level (coArchi2-style benefit). Compilation must be idempotent with stable deterministic IDs so re-runs produce reviewable diffs, not rewrites.
*Implemented in Phase 0.* Scope call: Open Exchange XML only. Native `.archimate` output was dropped from Phase 0 — Archi imports the exchange format, so a second emitter buys nothing until rendering lands in Phase 3, where Archi's headless CLI (`--xmlexchange.import` + `--saveModel`) converts it as a build step.

**AD-02 — Two-zone repository: `staging/` (LLM-proposed) vs `approved/` (human-signed).**
The only path between zones is an explicit approval skill. Downstream governance/reporting skills read only from `approved/`. Rationale: vendors uniformly position ~90% AI accuracy as unacceptable for risk-bearing decisions (Ardoq 2024); every serious platform converged on human-gated writes.

**AD-03 — Extraction pipeline is staged, chunked, multi-sampled.**
(a) chunked extraction (small chunks ≈ 2× entity recall — GraphRAG) with ≥1 gleaning pass; (b) entity resolution / merge stage (canonical names, alias table); (c) element typing against the metamodel; (d) relationship proposal; (e) deterministic validate → repair loop **capped at 3 iterations** (diminishing returns after 3–4 — arXiv 2607.05197), residuals go to a human review queue; (f) multi-candidate majority voting on high-stakes steps. Never one mega-prompt. Multi-step decomposition = +75% relationship F1 (MODELS 2024).

**AD-04 — Provenance is mandatory and mechanically verified.**
Every element/relationship carries `source: {file, quote}`; a verifier fuzzy-matches the quote against the actual source. Non-quoted elements are tagged `assumed` and surface in an open-questions report. The elicitation skill generates targeted clarification questions when source coverage is thin — the pipeline invents nothing.

**AD-05 — Validation stack is three-layer, vendored, in CI.**
(1) JSON Schema on the YAML DSL; (2) XSD validation of the Open Exchange export (Open Group schemas); (3) semantic checks: relationship matrix (vendored `relationships.xml` + `relationships-keys.xml`, hash-pinned), derivation-rule restrictions (Appendix B), naming conventions (noun phrases for structure, verb-noun for behavior), orphan/duplicate detection, EA-smells subset (from the 63-smell catalog, as deterministic graph queries). Standards must be vendored — pubs.opengroup.org is SSO-gated; skills must never fetch standards at runtime.

**AD-06 — Capability map is the spine; the artifact set is Kotusev's lean core, not TOGAF's deliverable list.**
Generated artifacts: Principles, Business Capability Map (first, everything attaches to it), Landscape Diagrams, Inventories (with APM fields from day one: functional fit, technical fit, TIME disposition, 6R, lifecycle state + dates, cost, criticality, owner), Roadmaps, Technology Reference Model / Standards, Solution Overviews, ADRs. TOGAF ceremony (Communications Plan, Statement of Architecture Work, Tailored Framework...) is out of scope by design — documented as a deliberate, evidence-backed decision.

**AD-07 — Temporal modeling via ArchiMate plateaus, not model copies.**
Baseline / Transition(s) / Target as Plateau elements with Gap elements in one model; a skill diffs plateaus and regenerates the roadmap.

**AD-08 — Governance is records + gates + diffs, git-native.**
PR review = compliance gate; CODEOWNERS = Architecture Board delegation; issue templates = Change Request / dispensation forms; tags = landscape snapshots.

**AD-09 — The approved model doubles as a machine-consumable governance plane for development agents.**
The repository's second audience (after humans) is the coding / requirements-definition agents working in downstream system repositories: principles, active standards (SIB), ADRs, requirements/constraints and integration context are served to them as scoped, generated extracts. This repositions the product from "EA repository maintained by agents" to "EA repository maintained by agents *and governing agents*". Deliberately staged by risk:

* **`ea-context` (cheap, safe — Phase 4).** Read-only query over `approved/` → per-system / per-capability context pack (generated `AGENTS.md`/`CLAUDE.md` section, file in the consuming repo, or MCP answer): applicable principles, *active* standards, relevant ADRs, constraints, data owners. Agents never read the raw EA repo — scope-filtered extracts only. Respects AD-02 (approved-only reads). Every pack must surface model freshness (the mandatory `lastReviewed` metadata): a thin or stale model served as "binding constraints" carries false authority, which is worse than no context.
* **`ea-check` (hard — deferred, decide after Phase 5).** Deterministic compliance lint in the consuming repo's CI. Honest constraint: full checking requires a model-element ↔ code-artifact correspondence (a CMDB-class mapping problem — the canonical failure point of commercial EA tools). Start narrow: dependency manifests (`package.json`/`pom.xml`) vs SIB lifecycle states. Anything requiring repos to maintain an integration manifest is a convention-adoption cost, not just an implementation cost — separate decision.
* **Motivation layer in the DSL (Phase 2).** Requirement / Constraint / Principle / Goal become first-class DSL elements with an applicability selector (which capability/system they bind). Already covered by the vendored 3.2 matrix; this is completing ArchiMate, not extending the vision.
* **Feedback path** is `ea-delta-ingest` (already catalogued): agents doing the work report drift back to `staging`. This may materially mitigate staleness; it is a process-discipline hypothesis, not a mechanism guarantee.

Rationale: TOGAF dispensation-with-expiry mechanics map directly onto agent workflows (an agent that must violate a standard files a time-bounded waiver instead of drifting silently). Competitive note: for context *provisioning* alone, markdown-only governance (ArcKit) is sufficient — the model-backed moat exists only where something is deterministically *checked* (relationship matrix, standards lifecycle, provenance), i.e. the `ea-check` half. Sequencing guard: none of this may delay Phases 2–5 (§1: ship fast).

**AD-10 — EA operates as a service with a catalog and a demand ledger (Architecture-as-a-Service / on-demand).**
Added post-roadmap (2026-08). Two record types complete the operating model the rest of the repository implies:

* **Catalog** (`services/`, one offering per file): what EA provides, phrased from the consumer's side, with a named owner, a fulfilment path (skill/command) and an **SLA in days** — a promise with a number, schema-mandatory. Lifecycle proposed→active→retired; `selfService` marks offerings consumers run themselves (an SLA that cannot be breached).
* **Demand ledger** (`governance-log/requests/`): who asked for which offering, for which model elements (`scope`), with what outcome. Fulfilment must point at the deliverable (`REQ005`); refusal needs a reason (`REQ007`); an open request past its SLA warns (`REQ006` — warning not error: lateness does not make the *model* wrong, but breaches surface in KPI and on the board agenda).
* **Demand feeds maintenance (the on-demand rule):** `staleness` carries per-element demand and the review queue orders by it; zero-demand + stale = de-scoping candidate. `kpi` gains the service line (offerings, open/fulfilled/declined, SLA breaches, average fulfilment) — the AaaS value evidence: consumption, not model size. Routing is catalog-first (`ea-run`), and a request's scope caps the work: unmodelled areas hit by a request go through intake *scoped to that request*, thin-slice, never big-up-front.

Deliberately not included: a network facade (MCP/HTTP) over the read-only commands for true self-service — same adoption-decision class as `ea-check`, and they belong together as the one integration surface for consuming repositories.

## 4. Skill catalog

### Phase D — Define & Document (pipeline order)
| Skill | Contract (input → output) |
|---|---|
| `ea-intake` | raw sources → fact register (statements with verified provenance) + coverage report + clarification questions |
| `ea-stakeholders` | fact register → stakeholder / concern / viewpoint matrix (ISO 42010 6.2–6.4) → view plan |
| `ea-capability-map` | facts → capability map (the spine) |
| `ea-model-business` / `-application` / `-technology` / `-data` | facts + capability map → typed elements & relations (YAML DSL, staging zone) |
| `ea-inventory` | facts → application/technology inventories with APM fields |
| `ea-validate` | staging model → validation report (matrix, smells, naming, orphans, provenance) ; repair loop ≤3 |
| `ea-approve` | staging + human decision → approved zone (the only write path) |
| `ea-views` | view plan + approved model → view definitions → rendered SVG/HTML (viewpoints from ArchiMate Appendix C, selected by stakeholder concerns, each doubling as an ISO 42010 §8.1 viewpoint spec) |
| `ea-gap` | baseline/target plateaus → gap elements + roadmap + Implementation & Migration layer |
| `ea-docs` | approved model + views + records → architecture description (42010 Clause 6 structure) + per-audience one-pagers, heatmaps, TIME quadrants |

### Phase G — Govern & Maintain (the differentiator)
| Skill | Contract |
|---|---|
| `ea-adr` | decision context → MADR record in governance log |
| `ea-compliance` | project artifacts + approved model → compliance assessment with TOGAF 6-level verdict (irrelevant / consistent / compliant / conformant / fully conformant / non-conformant), tailorable checklist |
| `ea-dispensation` | rejected assessment → time-bounded waiver with **mandatory expiry**; expiry re-triggers review (a dispensation without expiry is the tell of fake governance) |
| `ea-standards-base` | standards → SIB files with type (legal/industry/org) + lifecycle (proposed→trial→active→deprecated→retired); linter flags architectures referencing deprecated/retired standards |
| `ea-change-triage` | change request → Phase H classification (simplification / incremental / re-architecting; ≥2 impacted stakeholders → ADM re-entry, else maintenance) → routed action |
| `ea-delta-ingest` | new inputs (interview, CSV/CMDB export) → diff vs approved model → proposed additions/retirements in staging (continuous ingestion, not one-shot generation) |
| `ea-debt` | approved model → EA-smells scan (63-smell catalog subset, deterministic graph queries; LLM only for text-borne smells) → debt register |
| `ea-staleness` | model metadata (`owner`, `lastReviewed` mandatory on every element) → staleness report |
| `ea-kpi` | model + registers → model-quality metrics (completeness, freshness, orphans) + business metrics (apps per capability, obsolescence exposure, retirement savings) |
| `ea-conformance-42010` | docs repo → ISO 42010 Clause 6 conformance check (every concern ↔ stakeholder ↔ viewpoint ↔ view; correspondences 6.9; decisions with rationale 6.10) — checkable from front matter |
| `ea-board` | governance log → Architecture Board agenda/minutes per TOGAF standing agenda |
| `ea-context` | scope (system/capability) + approved model + governance log → agent-consumable context pack (applicable principles, active standards, relevant ADRs, constraints, owners) with freshness metadata (AD-09) |

Deliberately **not** a skill yet: `ea-check` (compliance lint inside consuming repos) — deferred per AD-09; decide after Phase 5, starting at most with dependency-manifest-vs-SIB linting.

Orchestrator: `ea-run` — routes a request to the right skills, maintains pipeline state.

## 5. Repository layout (target)

```
/skills/                      # the Claude Code skills (this is the product)
/schema/                      # JSON Schemas for the YAML DSL + governance records
/oracle/                      # vendored validation data (hash-pinned):
                              #   relationships.xml, relationships-keys.xml (Archi, 3.2),
                              #   Open Exchange XSDs, smells catalog, naming rules
/tools/                       # compiler (YAML→.archimate/AOEF), validators, renderers
/template/                    # the scaffold a user instantiates per enterprise:
  model/
    staging/  approved/       # two-zone YAML DSL (elements, relations, views)
  facts/                      # ea-intake output: fact register + sources/
  metamodel/                  # tailoring, conventions
  landscape/                  # strategic/ segments/ capabilities/ (plateau-based)
  standards/                  # SIB
  requirements/
  governance-log/
    decisions/ compliance/ dispensations/ capability-assessments/
    calendar.md portfolio.md metrics.md
  docs/                       # generated AD (42010 structure) + audience outputs
  build/                      # model.archimate, AOEF XML, SVG views, HTML report
/eval/                        # golden-set regression harness (input docs → expected model),
                              #   seeded EAModelSet-style; runs on every skill change
/README.md                    # incl. the 8-column capability comparison table
```

## 6. Toolchain (verified 2026-07-29) + risk register

| Role | Primary | Fallback | Risk notes |
|---|---|---|---|
| Model manipulation | **`lxml` against the vendored Open Group XSDs** (chosen in Phase 0) | pyArchimate 1.12.2 if SVG/auto-layout is needed; jArchi 1.11 headless via Archi CLI | Revised during implementation: Phase 0 needed no ArchiMate library at all, which **avoids the GPL-3.0 dependency** and the single-maintainer/API-churn risk of pyArchimate (20 releases in 3 months). Reconsider only for rendering. |
| Model file | `.archimate` (Archi 5.9 native) + AOEF XML export | — | AOEF is mildly lossy vs native — treat native as canonical artifact |
| Rendering | Archi headless docker (`ghcr.io/woozymasta/archimate-ci-image`) for HTML report; pyArchimate SVG per view | rebuild image from its Dockerfile (bundles Archi 5.7 vs current 5.9; last push Oct 2025) | community image, single maintainer; no official Archi image |
| UML / C4 views | PlantUML 1.2026.6 (`ghcr.io/plantuml/plantuml`) + C4-PlantUML | Kroki | Archimate-PlantUML stdlib = 3.1 sprites, semantics-free — rendering only, never modeling |
| Human editing | Archi 5.9.0, opens committed file directly | — | do NOT use coArchi (v1 legacy Grafico) or coArchi2 ("do not use in production", Patreon-gated) — plain git suffices since skills drive git |
| Validation oracle | vendored Archi `relationships.xml` + `relationships-keys.xml`; Open Group XSDs | SHACL (AlbertoDMendoza/archimate_ontology) for derivation-rule depth | no off-the-shelf "archimate-lint" exists — this build is ~days of work and a genuine differentiator |
| Avoid | Mermaid for architecture views (no ArchiMate, C4 experimental); MCP servers as foundations (all ≤1 year old, <30★) | | |

Letter legend for `relationships.xml` (from `relationships-keys.xml`): a=Access, c=Composition, f=Flow, g=Aggregation, i=Assignment, n=Influence, o=Association, r=Realization, s=Specialization, t=Triggering, v=Serving.

## 7. Roadmap (phased, riskiest-first)

1. **Phase 0 — Validation core**: YAML DSL schema + compiler to `.archimate`/AOEF + three-layer validator using the vendored oracle. *This is the technically defensible heart; nothing else matters if this is weak.*
2. **Phase 1 — Intake + traceability**: `ea-intake` with chunking/gleaning/entity-resolution + mechanical provenance verification + `assumed` tagging. *The quality ceiling of the whole system.*
3. **Phase 2 — Modeling pipeline**: capability map, per-layer modeling skills, validate-repair loop, two-zone approval. Includes Motivation-layer elements (Requirement/Constraint/Principle/Goal) with applicability selectors in the DSL (AD-09).
4. **Phase 3 — Views + docs**: viewpoint selection by stakeholder concerns, rendering, 42010-structured AD, audience outputs.
5. **Phase 4 — Governance & maintenance**: compliance, dispensations, SIB, change triage, delta ingest, debt, staleness, KPIs, 42010 conformance checker, `ea-context` agent context packs (AD-09). *The uniqueness anchor — do not cut.*
6. **Phase 5 — Eval harness + comparison table**: golden-set regression (potentially publishable), README capability matrix vs competitors.

Deferred, decide after Phase 5: `ea-check` — deterministic EA-compliance linting inside consuming system repos (AD-09). Not scheduled; requires the correspondence mapping and a convention-adoption decision.

Each phase ends with tests, plan update, memory update, clean close (per working convention).

## 8. Closest competitors to watch (re-check monthly)

| Project | Why it matters | Missing |
|---|---|---|
| byrondelgado/mcp-archimate (2026-07-28!) | model+validation+views core with pyArchimate matrix + quality gates | ingestion, traceability, docs, governance |
| 7bots-mvp / archimate-deep-agent (2026-07-25) | exact "evidence → traceable ArchiMate → git PR" concept | heavyweight platforms, 4-day-old MVPs, no views/docs/governance |
| Transitrix (active, plugin marketplace) | methodology + deterministic linting + PR governance + ingest skill | custom YAML, no ArchiMate interop |
| ArcKit (2.1k★) | strongest doc-level governance + traceability | markdown-only, will never emit a model |
| Ardoq (commercial ceiling) | real ingestion agents, controlled-write custom agents | proprietary SaaS, no ArchiMate exchange, no skills |

## 8a. Implementation status

**Phase 0 — complete (2026-07-30).** Built and tested:

* `easkills/oracle.py` — loads Archi's `relationships.xml` (declares `version="3.2"`), the letter legend, and the Open Group XSDs; verifies SHA-256 pins; maps all 61 concepts to layers (drift-guarded by a test).
* `schema/model.schema.json` — **generated** from the oracle, so the DSL cannot drift from the validator. A test fails if the committed schema is stale.
* `easkills/validate.py` — 26 rule codes across three layers, catalogued in `docs/RULES.md`. Flagship checks: `REL001` (matrix, with a swapped-endpoints hint), `PROV003` (quote located in the actual source file — fabricated citations rejected), `GOV001/002` (ownership mandatory in `approved`, advisory in `staging`).
* `easkills/aoef.py` — compiler to Open Exchange XML with deterministic layered layout, derived connections, layer-based organizations, governance metadata surfaced as model properties; output XSD-validated and byte-stable across runs.
* `eval/example/` — worked example, 15 elements / 15 relationships / 2 views, zero errors and zero warnings, every concept quote-verified.
* `eval/fixtures/broken/` — negative fixture violating every rule on purpose; CI asserts it keeps failing.
* 64 pytest tests; CI workflow gating tests, strict validation of the example, compilation, and the negative fixture.
* Skills: `ea-model` (authoring discipline), `ea-validate` (running and interpreting the gate, three-iteration repair cap).

Deviations from the plan above, and why: Open Exchange XML only (no native `.archimate` emitter — see AD-01); `lxml` instead of pyArchimate (no GPL dependency — see toolchain table). One usability fix found in implementation: YAML silently parses unquoted `2026-07-15` as a date object, so the loader normalizes dates back to ISO strings rather than forcing authors to quote every date.

**Phase 1 — complete (2026-08-01).** Intake + traceability, per AD-03/AD-04:

* Fact register DSL: `facts/register/*.yaml` (atomic statements) + `facts/entities.yaml` (canonical names + alias table). Schemas generated by the same mechanism as the model schema. **No `assumed` field by design** — a fact without provenance is a schema error; unsourced knowledge becomes a clarification question instead.
* `easkills/facts.py` — register loader + validator: 11 new rule codes (`FACT000–007`, `ENT001–003`, `SRC001`), catalogued in `docs/RULES.md`. Quote verification reuses the model validator's matcher (`FACT004` = fabricated citation, error). `ENT002` enforces one-term-one-entity so downstream modelling can't silently merge two things. `SRC001` flags sources never cited by any fact.
* `easkills/intake.py` — deterministic chunker (blank-line blocks greedily packed to a char budget, exact 1-based line numbers, stable ids; oversized blocks split at line granularity) and a coverage report: sources are sentence-segmented in the same normalized space as quote matching, quote intervals are unioned, and a sentence counts covered at ≥50% overlap. Markdown headings/emphasis-metadata and short table headers are filtered. Uncited spans come out with line numbers — the mechanical input for clarification questions.
* CLI: `validate-facts` (gate, `--strict`, `--json`), `chunk` (`--file`, `--max-chars`, `--json`), `coverage` (`--json`, `--min-coverage` gate).
* Worked example extended: 25 facts, 11 entities, both sources at 100% coverage, zero findings — including one `confidence: implied` fact and one fact merged from quotes in two different sources. Negative fixture extended to fire every new rule.
* Skill: `ea-intake` (chunk → extract → glean → resolve entities → validate ≤3 repairs → coverage → clarification questions).

Design calls made in implementation: entity `kind` is an informal hint, not an ArchiMate type (typing is Phase 2, per AD-03 stage c); the coverage report is advisory by default (uncited ≠ defect) with an opt-in `--min-coverage` CI gate; chunking is line-accurate rather than sentence-accurate so a chunk can always be found in the file a human has open.

**Phase 2 — complete (2026-08-01).** Modelling pipeline, per AD-02/AD-03/AD-09:

* **Fact-referencing provenance**: model concepts may cite `provenance: [{fact: <id>}]`; the validator resolves the fact in the register and re-verifies the fact's quotes against the sources (`PROV007` for a dangling reference; resolved quotes report as PROV002/003/004 "via fact"). One evidence base, mechanically chained end to end.
* **Motivation layer with applicability selectors (AD-09)**: `appliesTo: [element-ids]` on Requirement/Constraint/Principle/Goal; `MOT001` (unresolved binding), `MOT002` (selector outside the Motivation layer). Bindings count as connectivity for `SMELL001` and are surfaced in the exchange file as `appliesTo`/`provenance` properties, so they are visible in any ArchiMate tool and queryable by `ea-context` in Phase 4.
* **Staging as overlay**: `validate --zone staging` loads staging *on top of* approved — proposals may reference approved elements, same-id concepts are update proposals. Skills model the delta instead of copying the world.
* **Gated promotion**: `python -m easkills promote [--file ...] [--dry-run]` — the only staging→approved write path. The gate (`validate_promotion`) judges approved+staging merged by approved-zone standards (GOV rules become errors). On a clean gate, files move by rename; the git commit is the approval record. Deliberately no auto-stamping of `owner`/`lastReviewed` — the gate forces human-supplied review evidence to exist before the move. Partial promotion supported.
* Worked example: +2 motivation elements (Requirement bound to data+ERP, Constraint bound to WMS), both evidenced by fact references — 17 elements, still zero findings. Negative fixture extended (PROV007, MOT001, MOT002).
* Skills: `ea-capability-map` (the spine: 6–12 noun-phrase L1 capabilities, Realization attachments, weakness-as-property), `ea-approve` (explicitly human-gated; refuses autonomous promotion), and updates to `ea-model` (facts-first citation, motivation guidance, delta modelling) and `ea-validate` (zone semantics, promotion gate). 123 tests.

Deviations from the catalog: the four per-layer skills (`ea-model-business/-application/-technology/-data`) were folded into the single `ea-model` skill plus `ea-capability-map` — the authoring discipline is identical across layers and the per-layer split would duplicate 90% of the text; revisit if layer-specific guidance actually accumulates.

**Phase 3 — complete (2026-08-03).** Views + docs, per the ISO 42010 frame:

* **Stakeholder/concern register in the model DSL** (`stakeholders:`/`concerns:` sections, views gain `concerns:`): the 6.3–6.4 loop (stakeholder ↔ concern ↔ view) is enforced by six new rules — `ISO001/002` (dangling references, errors) and `ISO003–006` (coverage gaps, warnings that fire only once the repository declares the apparatus). The register rides the same two-zone staging→promotion flow as everything else.
* **`easkills/render.py`** — dependency-free SVG renderer reusing the compiler's deterministic layered layout: Archi-like layer colours, derived connections with arrowheads (dashed Realization/Specialization), `appliesTo` bindings drawn dotted so selector links cannot be misread as ArchiMate semantics. Byte-stable.
* **`easkills/docgen.py`** — architecture description generator (Clause 6 shape): stakeholders → concern-coverage table (open loop shown as bold **nobody**/**no view**) → views with element tables and embedded SVGs → application portfolio with TIME quadrants → capability support (including "nothing realizes this") → declared assumptions as open questions. Reads `approved/` only (AD-02). Deterministic: "as of" = newest `lastReviewed`, no wall clock.
* CLI: `render` (`--zone` for previewing staging), `docs` (refuses a model with validation errors). Generated outputs (`docs/architecture-description.md`, `docs/views/*.svg`) are **committed in the example and freshness-checked by a test and CI** — the same stale-artifact contract as the generated schemas.
* Worked example: +2 views (Customer Service Gap, Retention Obligations with dotted bindings), 3 stakeholders / 4 concerns, loop fully closed, still zero findings. Negative fixture fires all six ISO rules. 144 tests.

Deviations from the plan: rendering is native SVG instead of Archi-headless-docker/pyArchimate — Phase 0's lxml-only decision extends here (no GPL dependency, no docker requirement, byte-stable output, testable in CI); the Archi CLI route remains documented in the toolchain table for full-notation needs. Rendered views land in `docs/views/` rather than `build/` so the committed architecture description is self-contained. Audience one-pagers are a skill discipline (`ea-docs`), not a generator feature — extracts vary too much to template honestly.

**Phase 4 — complete (2026-08-03).** Governance & maintenance, the uniqueness anchor:

* **Governance records DSL** (schemas generated like the rest): `standards/*.yaml` (SIB: type legal/industry/organisation, lifecycle proposed→trial→active→deprecated→retired, successor), `governance-log/decisions/` (MADR-shaped, **rationale schema-mandatory** per ISO 42010 6.10), `governance-log/dispensations/` (**expiry schema-mandatory**), `governance-log/compliance/` (TOGAF six-level verdict enum). One record per file — the git history is the audit trail (AD-08).
* **`easkills/govern.py` + `validate-gov`**: 25 rule codes (`SIB000–004`, `DEC000–005`, `DISP000–007`, `COMP000–005`). Flagships: `DISP003` — an expired-but-open dispensation is an *error* (expiry re-triggers review by construction; the worked example will deliberately start failing on 2027-07-01 unless a human renews or closes the waiver); `COMP003` — non-conformant with no follow-up is flagged as theatre.
* **SIB lifecycle enforced in the model gate**: elements carry `standards: [std-...]`; `STD001` unknown, `STD002` retired = error unless an open dispensation covers the (element, standard) pair → `STD004` info with waiver id + expiry, `STD003` deprecated = warning. Surfaced into the exchange file as properties.
* **Maintenance reports** (`easkills/reports.py`, all deterministic given `--as-of`, all `--json`): `staleness` (review queue by owner), `kpi` (evidence share, staleness share, obsolescence exposure, unsupported capabilities, ISO loop state), `debt` (register from smell queries: isolated, hubs ≥10 degree, unsupported capabilities, duplicate names, stale content, dead-standard references), `conformance` (ISO 42010 Clause 6 checklist — every clause `pass`/`fail` where a check exists, `gap` where it does not, never silent conformance; `--strict` gates), `correspondences` (§6.9: every relation crossing out of the model, with the rule it is held to), `delta` (unmodelled entities + unused facts — the mechanical half of continuous ingestion).
* **`ea-context` packs (AD-09)** (`easkills/contextpack.py` + `context` CLI): scoped, approved-only extract per element (capability scope expands to realizers): binding motivation via `appliesTo` closure, standards with lifecycle + covering waivers, applicable decisions, cross-boundary integration with owners, open dispensations — opened by a **mandatory freshness label** (stale content ⇒ advisory banner). Byte-stable; footer routes drift back to delta ingestion.
* Worked example: SIB (3 standards incl. one retired with successor), a dispensation covering ERP+WMS until 2027-06-30, an accepted ADR, a conformant assessment — model and governance both zero-findings; conformance checklist 7 pass / 0 fail / 1 gap. Negative fixture fires all 25 governance codes + STD001–003. 189 tests.
* Skills: `ea-standards-base`, `ea-dispensation`, `ea-adr`, `ea-compliance`, `ea-context`, `ea-delta-ingest`, `ea-health`, `ea-change-triage`, `ea-board`.

Deviations from the catalog: `ea-debt`/`ea-staleness`/`ea-kpi` folded into one `ea-health` skill (three reports, one review discipline); change requests stay git-native (issues per AD-08) rather than gaining a record type; correspondences (42010 §6.9) are derived from the records that declare them. `ea-check` stays deferred per AD-09.

**Phase 5 — complete (2026-08-03). All planned phases done.**

* **Golden-set harness** (`easkills/score.py`, `score` CLI): a candidate repository is scored against a gold one — P/R/F1 per category with literature-grounded matching: entities by term-set overlap (name+aliases, normalized), facts by normalized-statement similarity ≥0.85 (one-to-one greedy), elements by (ArchiMate type, normalized name), relationships by type + endpoints mapped through element matches. The candidate's own validation gates run alongside — matching gold while failing provenance verification is fabrication that happens to be right, and `--min-f1` refuses it regardless of the numbers. Degradation tests prove each category moves independently (dropped fact → fact recall only; renamed element → elements + its relationships; invented element → precision not recall).
* **Golden set**: `eval/golden/clinic/` (1 source, 7 facts, 6 entities, 6 elements, 5 relationships — zero findings, self-score 100%) + `eval/example/` doubling as the largest case; `eval/golden/README.md` documents the evaluation procedure (run the pipeline blind on a case's sources into a scratch repo, score, compare against the previous run, never edit gold to pass).
* **Capability comparison table** now lives in the README: the 8 §1 capabilities vs mcp-archimate, 7bots/archimate-deep-agent, Transitrix, ArcKit, Ardoq — dated (research 2026-07-29, ea-skills column 2026-08-03) with the monthly re-check obligation stated in place.
* Skills: `ea-eval` (regression discipline: all cases, spread over cherry-picks, gold changes never land with skill changes) and `ea-run` (the orchestrator: state check first, routing table, from-scratch stage order). Skill catalog complete at 19. 201 tests.

Open items carried deliberately beyond the roadmap: `ea-check` decision now due (AD-09 said "decide after Phase 5"); monthly competitive re-check of the README table; the worked example's scheduled failures (dispensation expiry 2027-06-30, staleness horizon mid-2027) are maintenance rehearsals, not defects.

**Phase 6 — complete (2026-08-04).** The service layer (AD-10, Architecture-as-a-Service / on-demand):

* Catalog + demand ledger as governance records (schemas generated like the rest): `services/*.yaml` (owner + `slaDays` + fulfilment schema-mandatory, lifecycle, `selfService`) and `governance-log/requests/*.yaml` (offering, requester, `scope` of model elements, status open/fulfilled/declined with evidenced fulfilment).
* `validate-gov` gains 12 rule codes: `SVC000–002`, `REQ000–008`. Flagships: `REQ005` — a fulfilment without a deliverable pointer is a closed ticket, not a service; `REQ006` — an open request past its offering's SLA warns and lands in KPI as a breach (warning, not error — documented rationale in RULES.md).
* Demand-weighted maintenance: `staleness` carries per-element demand (requests naming it in scope) and a `neverRequested` count; the review queue orders by demand. `kpi` gains the Service line: active offerings, request dispositions, SLA breaches, average fulfilment days.
* Worked example: 3 offerings (context pack, compliance review, standard exception) + 2 fulfilled requests — one pointing at the existing compliance assessment as its deliverable, closing the loop request→offering→record. Negative fixture fires all 12 new codes. 220 tests.
* Skills: new `ea-service` (catalog discipline: an offering is a promise with a number; request lifecycle; SLA hygiene without silent date edits); `ea-run` routes catalog-first with the scope-caps-the-work rule; `ea-board` gets the service-performance agenda item; `ea-health` reads demand in the review queue.

Design calls: requests that are *fulfilled* are timeless (the example carries no open requests, so no CI time-bomb beyond the deliberate 2027 ones); the network facade for self-service stays deferred with `ea-check` per AD-10.

**Hardening pass — documentation as a checked artifact (2026-08-04, post-Phase 6).** A review of the public-documentation set found the predictable failure: prose asserting mechanisms that were only partly implemented. Resolved by moving the claims into code rather than softening them.

* **Oracle pins verified by every consumer, not just `validate`.** `compile`, `render`, `docs` and `gen-schema` now refuse on drift (`--skip-validation` does not bypass it) — `gen-schema` mattered most, since it writes the authoring contract *from* the matrix. Proven by a parametrized test that tampers with the pin file per command.
* **Claims that carry a number are tested.** One registry drives `gen-schema` and its freshness test (all nine schemas, not three); the shared-flag table in `docs/CLI.md` is compared against the argparse tree; the CONTRIBUTING pre-push block is compared against every `easkills` invocation in the workflow; rule and skill counts in the README are compared against `docs/RULES.md` and `skills/`. Hand-maintained test counts were removed instead of being corrected — a number nothing checks is a claim waiting to rot (`tests/test_repo_docs.py`).
* **One wording per convention.** The gold rule read three different ways across CONTRIBUTING, the PR template and the README; generated `eval/example/docs/` is now an explicit carve-out of the "authored gold does not move with tooling" rule, so a renderer change is not simultaneously required and forbidden.
* **Packaging honesty (relates to AD-05).** The oracle and generated schemas live at the repository root by design, so a wheel would ship a package that cannot validate anything. Rather than restructure vendored, hash-pinned data into package data, the PyPI-shaped metadata was dropped (long description, platform classifiers, console script) and the clone-first usage stated in `pyproject.toml`; `[build-system]` and the PEP 639 licence form stay for editable installs. Decision recorded here so it is not "fixed" later by adding a publish workflow.
* **CI matrix.** Suite + `oracle-info` on Python 3.11/3.12/3.13 × Linux/Windows; the artifact, gold and negative-fixture gates stay on one runner because they check content, not the interpreter. Windows is now genuinely exercised — it is the development platform, and `.gitattributes` line-ending conversion of the oracle would break `ORACLE001`.
* The Phase-H change-request form moved into `template/.github/ISSUE_TEMPLATE/` (AD-08 says the issue *is* the record — in the architecture repository, whose `model/approved/`, `standards/` and `governance-log/decisions/` ids it asks for); the tooling repository keeps bug reports and the rule-proposal triple form.

**Core code review — gate robustness (2026-08-04).** The documentation pass above reviewed prose; this one reviewed the 6.2k lines of `easkills/`. Four defects, each reproduced first, each now regression-tested. Five rule codes added: 96 total.

* **False negatives beat false positives to the top of the queue.** `DISP008`: a dispensation with `expires: 2027-13-45` (shape-valid per the schema pattern, impossible per the calendar) hit an `except ValueError: continue` whose comment claimed "schema already rejected the format" — it had not. The record left the gate *entirely* unchecked: `DISP003`/`DISP004`/`DISP005`/`DISP007` all silent, `ok=True`. A waiver becomes permanent exactly this way. Now the date is reported and the date-independent checks continue; `REQ009` closes the same trap in the demand ledger. **Lesson recorded: a comment asserting another layer's behaviour is not a check — pattern-shaped date validation is not date validation.**
* **Provenance could leave the repository** (`PROV008`/`FACT008`): `(facts_root / file).resolve()` with no containment test meant `file: ../../secret.txt` was read and its quote "verified" — zero errors. Two consequences: traceability no reviewer can open, and, against SECURITY.md's "safe to run in CI on untrusted content", an existence oracle over the runner's filesystem. References are now refused unless they resolve inside the root, `factsRoot`/`sourcesDir` included.
* **A gate that crashes reports nothing** (`SCHEMA002`): `int(config["stalenessDays"])` and `int(data["slaDays"])` raised straight out of the checks on `soon`/`ten`, replacing findings with a traceback — and `slaDays` did it *before* the schema check that would have reported it. Loading is now uniformly best-effort (the convention dsl.py and facts.py already stated, govern.py violated), with unusable config values reported and the documented defaults applied. The range check also catches `quoteMatchThreshold: 90`, which would have accepted fabricated quotes silently.
* Method note: every finding was reproduced in a scratch repository *before* the fix, and the reproduction became the test — `test_an_impossible_expiry_does_not_silence_the_other_dispensation_checks` is the probe from the review, not a paraphrase of it.

**Core code review, part 2 — the write path, the zones, the reports (2026-08-04).** Continuing through `promote.py`, `aoef.py`, `score.py`, `intake.py`, `reports.py`, `contextpack.py`, `render.py`. Six defects; 97 rules total.

* **The gate validated a model the move then changed (worst so far).** Promotion renames `staging/x.yaml` onto `approved/x.yaml`, but `load_merged` unioned the two files id-by-id. So promoting an updated `application.yaml` that omitted one component passed with `ok=True`, deleted that component, and left `REF001` in the *approved* zone — the one place this design promises is always valid. Fixed by making the merge model the post-move truth (file shadowing), which is now the single rule every zone read applies. A replacement that drops only unreferenced content still passes, and `promote` names what it removes: deletion stays a signed decision, not a discovery in a later diff. **Lesson: a gate must validate the artifact the write produces, not a convenient approximation of it.**
* **One definition of "zone" (`dsl.load_zone`).** `compile`/`render --zone staging` loaded staging alone and told the user to "validate before compiling" a delta that had just validated. Three commands, three semantics, is a bug waiting for a user.
* **PyYAML's date resolver crashed the loaders.** `lastReviewed: 2026-06-31` (one character) is resolved to `datetime.date` *during parsing* and raises a bare `ValueError` — not a `YAMLError`. Every command died with a traceback where `SCHEMA000` belonged. All four loaders now catch one shared error tuple.
* **Reports that lied quietly:** `REQ010` (a request fulfilled before it was requested reported `avgFulfilmentDays: -19`); an empty repository printing "100% owned; 100% stale/unreviewed" on one line (a share of *bad* things needs 0.0, not vacuous 1.0, for "nothing to measure"); ISO 42010 §6.8 hardcoded to `pass` — decorative conformance in the report whose whole purpose is refusing it, now a real check against the generated description; and context packs deciding their mandatory freshness banner by sniffing for the substring "stale", so an unreadable review date read as "current".
* Clean on review: `score.py` (greedy matching is documented and deterministic; the vacuous-truth conventions are consistent), `intake.py` (chunk and sentence spans are exact and terminate), `aoef.py` (id collisions and duplicate property definitions are caught by XSD validation rather than passing silently).

**Core code review, part 3 — the last modules (2026-08-04).** `genschema.py`, `docgen.py`, `render.py`, `ui.py`. One defect, of a class worth naming.

* **An interpreted key without a vocabulary is a silent data-loss bug.** `properties` is deliberately free-form, but three components *read* `timeDisposition`: the schema (nothing), `kpi` (counts non-empty), `docs` (buckets by exact value, iterating the four TIME quadrants). A lowercase `tolerate` therefore validated clean, counted as 100% classified, and vanished from the architecture description's quadrant line together with its application — a portfolio summary quietly omitting a system. Fixed by giving the vocabulary one home (`genschema.TIME_DISPOSITIONS`), constraining that one key in the schema while leaving the map open, counting only recognised values, and having docgen *name* what it cannot classify. **Rule going forward: if the tooling interprets a property key, the schema constrains it and the reports refuse to drop unknown values silently.**
* Two invariants that held only by discipline are now structural tests: the literals the governance checks compare against must exist in their schema enums (rename `non-conformant` and `COMP003` would simply stop existing), and no artifact-generating module may import `ui` (styling depends on TTY detection and console encoding; leaking it into a written file would make the CI freshness check runner-dependent).
* Reviewed clean: `render.py` (no model data reaches an SVG *attribute*, so single-quote escaping is not load-bearing; coordinates fixed to one decimal), `ui.py`, and the schemas' `additionalProperties: false` — which is what makes RULES.md's "unknown key" claim true.

**AD-09 decision taken — `ea-check` ships narrow (2026-08-04).** The blueprint said "decide after Phase 5"; this is the decision.

* **Scope:** dependency manifests (`package.json`, `pom.xml`, `requirements.txt`) versus SIB lifecycle, with dispensations honoured and their expiry surfaced. Eight rules, `CHK000–CHK007`.
* **What made it shippable was refusing the hard half.** Full model-element ↔ code-artifact correspondence is a CMDB-class problem *and* a convention every consuming team would have to adopt — the documented failure point of commercial EA tooling. So: the consuming repository declares nothing (`--scope` is the whole convention, one CI line), and the *standard* declares how it is evidenced (`detect:` rules in the SIB entry). The tooling never infers that a library "is" a standard, which keeps the correspondence problem where it belongs — in a governed record, reviewed like any other.
* **Deliberate non-features:** no version-range logic (would need a semver dependency and would answer questions it cannot settle — the version is reported, never judged); no suppression file (the three honest exits are migrate, file a dispensation, or change the lifecycle); no write access to the EA repository from a consuming repo.
* **Drift is reported both ways**, which is what makes this more than a lint: `CHK006` (the code follows a standard the model does not record) is intake material for `ea-delta-ingest`, and `CHK005` (the model claims a standard nothing evidences) is a claim the EA repository should stop making.
* **Network facade: still deferred, now with a decision rule.** `ea-check` needs no service, so the facade is not on its critical path. The AD-10 demand ledger is the instrument that should settle it — repeated requests for an offering are evidence that a self-service surface is wanted; speculation is not. Recorded so the question stops re-opening on taste.

**End-to-end run and what it changed (2026-08-05).** The pipeline was run blind through its own documented evaluation procedure: the clinic case's source into a scratch repository scaffolded from `template/`, extraction and modelling by judgement, then every gate, every artifact, and `score`.

* **The pipeline held.** Intake → evidence gate → 100% source coverage → model → semantic gate → promotion (dry run, then move) → documentation apparatus → governance records → XSD-valid exchange file → SVG → architecture description → conformance 7 pass / 0 fail / 1 gap → KPI/debt/delta → context pack. No tooling failure, no manual patching.
* **The flagship rule earned its place on live material.** The run modelled `Assignment` from an `ApplicationComponent` to an `ApplicationInterface`; `REL001` refused it and listed what the 3.2 matrix does permit. One repair round. This is the documented weakest LLM capability being caught by the oracle rather than by a reviewer — evidence, not a fixture.
* **The harness failed the same run.** The candidate recalled 100% of gold's elements and relationships, and scored 15% / **0%**: element matching keyed on (type, exact name), and relationship matching cascaded through unmatched elements. Two faithful models disagreeing about "EHR" versus "Electronic Health Record System" produced a number that reads as total failure. **Lesson: a metric that conflates vocabulary disagreement with missing content will eventually be optimised for vocabulary.**
* **What changed** (deliberately a change to the measuring stick, in its own commit): names resolve through both repositories' entity alias tables — the knowledge was already in `facts/entities.yaml` and the scorer ignored it; facts are matched on the *source ground they cover*, so the register's own push towards atomic facts stops being punished, with statement similarity retained as full-versus-half credit so wording still counts; a type disagreement inside one layer is half a match, across layers none; a label-independent `rel-structural` count is reported as an ungated diagnostic. Self-scores stay 100%, so the CI contract is unchanged. On the run that prompted it: 15% → 77% elements, 0% → 73% relationships, 50% → 75% facts.
* **The gold case was leaking the answer.** `eval/golden/clinic/ea.config.yaml` said "seven facts, six elements" in its documentation, and the procedure copies that file into the scratch repository the candidate is produced in. Removed, with the reason recorded in the file itself.
* Also caught, by the existing degradation suite, while implementing the above: the new fact matcher keyed statements by fact id across both registers — and a candidate is usually a *copy* of gold with the same ids, so every statement was being compared with itself. The test that distorts a statement failed exactly as it should.

**Contradictions between sources (2026-08-05).** The end-to-end run named the gap the golden set could not measure, and building the case for it found the mechanism missing entirely: `confidence` offered `stated`/`implied`, and `assumed: true` is reported only when a concept has *no* provenance — so "both sources are quoted and they disagree" had nowhere to live. In practice that means the resolution is decided by whichever document was read last, and the description reads as settled fact.

* **The register keeps both sides.** `confidence: contested` plus `contests: [fact-id]`, with three rules that keep the contradiction followable rather than merely labelled (`FACT009`/`FACT010`/`FACT011`). Nothing here decides who is right — that is a modelling judgement, and the tooling's job is to stop it being made in silence.
* **The model may choose, but not quietly.** `PROV009` (info) reports a concept citing a contested fact, and the architecture description gives contested citations their own paragraph **quoting the side that was not followed**. A reader can overturn the choice without opening the register. Info, not error: blocking would push the choice back into prose, which is where it was.
* **Golden case `contested/`** — a courier whose May inventory says a scheduling system was decommissioned and whose July interview says dispatch uses it every Friday. It exercises two-source intake, entity resolution across documents, and the mechanism end to end. Note what the case *teaches* by existing: an unowned system that one source says is gone is the archetypal shadow-IT finding, and the repository now has a way to state it without pretending it is settled.
* Building it also cost two `REL001` findings against the author (`Assignment` component→interface, `Serving` node→data object) — the same rule, on the same weak spot, in a second sitting.

**ISO 42010 §6.9 correspondences — the last labelled gap (2026-08-05).** The clause asks for the relations between AD elements to be recorded, for the rules governing them to be stated, and for violations to be known. The obvious implementation was a `correspondences:` authoring block, and it was rejected on the same ground the whole repository stands on: a decision record already names the elements it decides, a requirement already names what it binds, an element already names the standards it follows, a concept already names the facts that evidence it. A second copy of those relations would have bought conformance with duplication and drifted within a quarter.

* **Derived, never authored twice.** Five rules — `realizes`, `binds`, `governed-by`, `assessed-by`, `evidenced-by` — each crossing a boundary no ArchiMate relationship can reach across: into the governance log, into the fact register. Inside the model a relation between two elements is a *relationship*, and the oracle governs it; that boundary is what makes the vocabulary closed and small rather than a matter of taste.
* **Only two rules needed a new check, and they are the two nothing could see.** `CORR001`: an element still realising a `superseded`/`rejected`/`deprecated` decision — the record is in perfect order (successor named, rationale present), so no `DEC*` rule looks at it; what is stale is the relation, and superseding was never finished until the elements moved. `CORR002`: a requirement whose bound elements are *all* TIME `Eliminate` — the retention obligation that outlives the system holding the records. One eliminated bearer among several stays silent, because a migration is not a gap and a rule that cries at plans gets ignored.
* **The other three name the code that already enforces them** (`STD002`, `COMP005`, `PROV007`) instead of reporting the same defect twice, which makes the correspondence table double as a map of which gate holds which relation together. **Rule going forward: a clause is not implemented by inventing checks for relations that are already checked — it is implemented by stating the rule and pointing at the enforcement.**
* **§6.10 was strengthened on the way past**, exactly as §6.8 had been earlier: a decision in the governance log is one somebody can find, not one the *description* records. Both clauses now depend on the generated document, which is why the description gained §7 Decisions and §8 Correspondences and lost the footer promising them "in a later phase".
* **Determinism trap avoided:** correspondence verdicts depend on dispensation coverage, which depends on a date. The description evaluates them as of the model's own `lastReviewed` horizon, never the wall clock — otherwise the committed document would change bytes overnight and the freshness gate would fail on a day nobody touched the repository.
* Left underived, deliberately: correspondences to AD elements in *another* architecture description. Nothing here can check the far end of one, and the checklist counts only relations whose both sides this repository holds.

**Brownfield import — the adoption path (2026-08-05).** Asked what would most strengthen the competitive position, the honest answer was none of the remaining rigor items: it was that every path into this repository assumed an empty start, and no organisation with an architecture starts empty. The moat of every incumbent EA tool is the model already inside it; an import that reads the standard exchange format dissolves it.

* **`aoef.py` run backwards** (`easkills/importer.py`): the same format the compiler writes, read best-effort with every omission named. The round trip against the worked example is a pinned test, so the importer and the compiler cannot drift apart silently.
* **The rules apply on entry, not later.** Staging only; everything `assumed` (the old tool's content is a claim — its `provenance` property is kept as information, never trusted as verification); owner/review metadata lifted where the export carried it; `appliesTo` renamed together with the elements it binds — the smoke test caught exactly that dangle before the tests did.
* **The import never judges; the gate does.** A matrix-illegal relationship is imported as-is and reported by `REL001` — "your previous tool allowed this" is the migration's first deliverable, and it comes from the same validator as every other finding. Likewise `STD001/STD002` on lifted standards claims: the SIB migrates too, or the claim goes.
* **The differentiator is the honesty, not the parser.** Commercial importers advertise fidelity; this one advertises *what it refused to believe*. A migration summary that lists every rename, skip, mapping and unverifiable claim is the first artifact a new adopter can trust — and `validate --zone staging` right after it is the adoption backlog, already itemised. The skill's discipline: promote in slices someone vouches for; wholesale promotion signs off a thousand unreviewed claims.
* Deliberately absent: reading vendors' native formats (Archi `.archimate`, tool databases). One standard, both directions, XSD-validated — a tool that cannot export the exchange format its vendor signed is making a different argument.

**Impact analysis — the counting `ea-change-triage` was asking a human to do (2026-08-05).** The skill has always documented the Phase H test as *"count the stakeholder groups whose concerns are touched; two or more means re-architecting"*, pointed at `context --scope`, and left the counting to the reader. In a repository whose thesis is "the model supplies judgement, the tooling supplies proof", that was judgement all the way down.

* **The hard part is not traversal, it is direction.** The vendored matrix answers which relationships are *permitted* and says nothing about which way a change travels. That is a semantic reading of the specification, so it lives in one declared table (`impact.PROPAGATION`) with a reason attached to every entry, and a test asserts the table covers exactly the oracle's type set — the same contract the schema enumerations already have.
* **`Association` is the honest hole.** ArchiMate leaves its meaning to the modeller, so it is reported as adjacency of unknown direction and never traversed. A blast radius that walked associations would look more thorough and be partly invented; and an association that *does* matter for a change is a modelling finding — the relationship that was meant should be there instead.
* **The tooling reaches the arithmetic verdict only.** Two of the three Phase H tests are judgement; the report names the one it evaluated and declares the one it did not. Zero stakeholder groups is reported as *possibly a gap in the views* rather than as no impact — the failure mode of any reachability metric is silence reading as safety.
* **No new skill.** `ea-impact` was drafted and dropped: two skills for one job dilutes the catalogue, and the capability belongs inside the triage discipline that already documents the threshold. A test pins the threshold constant against the number written in that skill, so the two cannot drift.

**Roadmap: the plan as a model (2026-08-05).** The Implementation & Migration layer had been valid in the DSL since the schema was first generated -- `Plateau`, `Gap`, `WorkPackage`, `Deliverable` all come from the oracle -- and nothing checked any of it. So a target state could be recorded and quietly contradict the portfolio decisions sitting next to it, which is the failure mode of every roadmap slide this repository was built to replace.

* **One new key, constrained on purpose.** The standard carries no date on a plateau, and without one a sequence of states is a set of states. `plateauDate` is patterned in the schema *before* an incident rather than after one -- the `timeDisposition` lesson applied prospectively.
* **`PLAT005` is the rule the layer exists for**: an element decided `Migrate` or `Eliminate` that no plateau includes. A portfolio decision nobody scheduled becomes, within a year, a portfolio decision nobody made. It stays silent when a repository has no plateaus at all, because a model that has not started planning is not breaking a roadmap -- the same shape as `CORR002`'s group-awareness, and for the same reason: a rule that fires on plans nobody has made yet gets ignored.
* **`PLAT004` earns the association back.** A `Gap`-to-`Plateau` link can only be an `Association` in the 3.2 matrix, and association is precisely what `impact` refuses to traverse. The two decisions meet here: the gap link is not load-bearing for traversal, so a rule makes it load-bearing for validation instead.
* **The example records a contradiction rather than a tidy plan**: a 2028 plateau for the warehouse system's cloud move, and a constraint saying the move has no approved budget. That is the honest state of most roadmaps, and it belongs in the model where a gate can see it.
* Caught while building the fixture: `plateauDate: 2027-03-32` unquoted takes the *whole file* down through PyYAML's date resolver -- the `ValueError`-not-`YAMLError` trap the loaders were hardened against earlier. The fixture now quotes it and says why, which is the second time that trap has had to be documented in place.

## 9. Key sources (load-bearing)

Standards: Archi relationship matrix — github.com/archimatetool/archi/blob/master/com.archimatetool.model/model/relationships.xml (+ relationships-keys.xml) · Open Group XSDs — opengroup.org/xsd/archimate/ · ISO/IEC/IEEE 42010:2022 — iso.org/standard/74393.html · TOGAF 10 (SSO-gated) — pubs.opengroup.org/togaf-standard/ · ArchiMate viewpoints — Appendix C of spec · SHACL ontology — github.com/AlbertoDMendoza/archimate_ontology

Research: relationships are the LLM weak spot — MODELS 2023 (ieeexplore 10344012), MODELS 2024 (+75% rel. F1 from decomposition, dl.acm.org/doi/10.1145/3652620.3687807) · repair loops cap at 3–4 — arXiv 2607.05197 · chunking/gleaning — GraphRAG arXiv 2404.16130 · fabricated citations + P0.88/R0.25 — arXiv 2604.00046 · multi-candidate aggregation — arXiv 2508.00255 · EAModelSet (978 models) — github.com/me-big-tuwien-ac-at/EAModelSet

Practice: Kotusev — kotusev.com/Enterprise%20Architecture%20on%20a%20Single%20Page.pdf, eaonapage.com · EA smells — ea-debts.org · staleness mitigations — eatransformation.com/p/how-to-keep-enterprise-architecture-alive · Ardoq on AI accuracy — ardoq.com/blog/ai-enterprise-architecture-modeling · TIME/APM — leanix.net/en/wiki/apm/gartner-time-model

Competitive: full sweep in research report (2026-07-29); table §8 above.

Local research assets: `C:\tmp\ea-research\` — relationships.xml, RelationshipsMatrix.java, archimate31.pdf, am31_full.txt (full spec text), iso42010.txt. Still to fetch: `relationships-keys.xml` (raw.githubusercontent.com/archimatetool/archi/master/com.archimatetool.model/model/relationships-keys.xml).
