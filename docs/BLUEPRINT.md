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
* **`easkills/govern.py` + `validate-gov`**: 20 rule codes (`SIB000–004`, `DEC000–005`, `DISP000–007`, `COMP000–005`). Flagships: `DISP003` — an expired-but-open dispensation is an *error* (expiry re-triggers review by construction; the worked example will deliberately start failing on 2027-07-01 unless a human renews or closes the waiver); `COMP003` — non-conformant with no follow-up is flagged as theatre.
* **SIB lifecycle enforced in the model gate**: elements carry `standards: [std-...]`; `STD001` unknown, `STD002` retired = error unless an open dispensation covers the (element, standard) pair → `STD004` info with waiver id + expiry, `STD003` deprecated = warning. Surfaced into the exchange file as properties.
* **Maintenance reports** (`easkills/reports.py`, all deterministic given `--as-of`, all `--json`): `staleness` (review queue by owner), `kpi` (evidence share, staleness share, obsolescence exposure, unsupported capabilities, ISO loop state), `debt` (register from smell queries: isolated, hubs ≥10 degree, unsupported capabilities, duplicate names, stale content, dead-standard references), `conformance` (ISO 42010 Clause 6 checklist — 6.9 correspondences reported as an explicit `gap`, never silent conformance; `--strict` gates), `delta` (unmodelled entities + unused facts — the mechanical half of continuous ingestion).
* **`ea-context` packs (AD-09)** (`easkills/contextpack.py` + `context` CLI): scoped, approved-only extract per element (capability scope expands to realizers): binding motivation via `appliesTo` closure, standards with lifecycle + covering waivers, applicable decisions, cross-boundary integration with owners, open dispensations — opened by a **mandatory freshness label** (stale content ⇒ advisory banner). Byte-stable; footer routes drift back to delta ingestion.
* Worked example: SIB (3 standards incl. one retired with successor), a dispensation covering ERP+WMS until 2027-06-30, an accepted ADR, a conformant assessment — model and governance both zero-findings; conformance checklist 7 pass / 0 fail / 1 gap. Negative fixture fires all 20 governance codes + STD001–003. 189 tests.
* Skills: `ea-standards-base`, `ea-dispensation`, `ea-adr`, `ea-compliance`, `ea-context`, `ea-delta-ingest`, `ea-health`, `ea-change-triage`, `ea-board`.

Deviations from the catalog: `ea-debt`/`ea-staleness`/`ea-kpi` folded into one `ea-health` skill (three reports, one review discipline); change requests stay git-native (issues per AD-08) rather than gaining a record type; correspondences (42010 §6.9) remain an honest gap. `ea-check` stays deferred per AD-09.

## 9. Key sources (load-bearing)

Standards: Archi relationship matrix — github.com/archimatetool/archi/blob/master/com.archimatetool.model/model/relationships.xml (+ relationships-keys.xml) · Open Group XSDs — opengroup.org/xsd/archimate/ · ISO/IEC/IEEE 42010:2022 — iso.org/standard/74393.html · TOGAF 10 (SSO-gated) — pubs.opengroup.org/togaf-standard/ · ArchiMate viewpoints — Appendix C of spec · SHACL ontology — github.com/AlbertoDMendoza/archimate_ontology

Research: relationships are the LLM weak spot — MODELS 2023 (ieeexplore 10344012), MODELS 2024 (+75% rel. F1 from decomposition, dl.acm.org/doi/10.1145/3652620.3687807) · repair loops cap at 3–4 — arXiv 2607.05197 · chunking/gleaning — GraphRAG arXiv 2404.16130 · fabricated citations + P0.88/R0.25 — arXiv 2604.00046 · multi-candidate aggregation — arXiv 2508.00255 · EAModelSet (978 models) — github.com/me-big-tuwien-ac-at/EAModelSet

Practice: Kotusev — kotusev.com/Enterprise%20Architecture%20on%20a%20Single%20Page.pdf, eaonapage.com · EA smells — ea-debts.org · staleness mitigations — eatransformation.com/p/how-to-keep-enterprise-architecture-alive · Ardoq on AI accuracy — ardoq.com/blog/ai-enterprise-architecture-modeling · TIME/APM — leanix.net/en/wiki/apm/gartner-time-model

Competitive: full sweep in research report (2026-07-29); table §8 above.

Local research assets: `C:\tmp\ea-research\` — relationships.xml, RelationshipsMatrix.java, archimate31.pdf, am31_full.txt (full spec text), iso42010.txt. Still to fetch: `relationships-keys.xml` (raw.githubusercontent.com/archimatetool/archi/master/com.archimatetool.model/model/relationships-keys.xml).
