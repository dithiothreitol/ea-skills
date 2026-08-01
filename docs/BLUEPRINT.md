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
3. **Phase 2 — Modeling pipeline**: capability map, per-layer modeling skills, validate-repair loop, two-zone approval.
4. **Phase 3 — Views + docs**: viewpoint selection by stakeholder concerns, rendering, 42010-structured AD, audience outputs.
5. **Phase 4 — Governance & maintenance**: compliance, dispensations, SIB, change triage, delta ingest, debt, staleness, KPIs, 42010 conformance checker. *The uniqueness anchor — do not cut.*
6. **Phase 5 — Eval harness + comparison table**: golden-set regression (potentially publishable), README capability matrix vs competitors.

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

## 9. Key sources (load-bearing)

Standards: Archi relationship matrix — github.com/archimatetool/archi/blob/master/com.archimatetool.model/model/relationships.xml (+ relationships-keys.xml) · Open Group XSDs — opengroup.org/xsd/archimate/ · ISO/IEC/IEEE 42010:2022 — iso.org/standard/74393.html · TOGAF 10 (SSO-gated) — pubs.opengroup.org/togaf-standard/ · ArchiMate viewpoints — Appendix C of spec · SHACL ontology — github.com/AlbertoDMendoza/archimate_ontology

Research: relationships are the LLM weak spot — MODELS 2023 (ieeexplore 10344012), MODELS 2024 (+75% rel. F1 from decomposition, dl.acm.org/doi/10.1145/3652620.3687807) · repair loops cap at 3–4 — arXiv 2607.05197 · chunking/gleaning — GraphRAG arXiv 2404.16130 · fabricated citations + P0.88/R0.25 — arXiv 2604.00046 · multi-candidate aggregation — arXiv 2508.00255 · EAModelSet (978 models) — github.com/me-big-tuwien-ac-at/EAModelSet

Practice: Kotusev — kotusev.com/Enterprise%20Architecture%20on%20a%20Single%20Page.pdf, eaonapage.com · EA smells — ea-debts.org · staleness mitigations — eatransformation.com/p/how-to-keep-enterprise-architecture-alive · Ardoq on AI accuracy — ardoq.com/blog/ai-enterprise-architecture-modeling · TIME/APM — leanix.net/en/wiki/apm/gartner-time-model

Competitive: full sweep in research report (2026-07-29); table §8 above.

Local research assets: `C:\tmp\ea-research\` — relationships.xml, RelationshipsMatrix.java, archimate31.pdf, am31_full.txt (full spec text), iso42010.txt. Still to fetch: `relationships-keys.xml` (raw.githubusercontent.com/archimatetool/archi/master/com.archimatetool.model/model/relationships-keys.xml).
