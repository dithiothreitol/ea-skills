# Rule catalogue

Every rule is deterministic. None of them consults a language model, and every one is
exercised by a case in `eval/fixtures/broken/` -- adding a rule means adding a fixture
case for it, otherwise the test suite fails to prove the rule works.

Severity meanings:

* **error** -- the model is wrong. Exit code 1; the compiler refuses to run.
* **warning** -- the model is questionable. Passes by default, fails under `--strict`.
* **info** -- a declared, accepted state worth surfacing (currently: assumptions).

Three validators share this catalogue: `python -m easkills validate` covers the model
zones (`ORACLE`/`SCHEMA`/`ID`/`REF`/`PROV`/`GOV`/`MOT`/`STD`/`ISO`/`REL`/`NAME`/`SMELL`),
`python -m easkills validate-facts` covers the fact register (`FACT`/`ENT`/`SRC`), and
`python -m easkills validate-gov` covers the standards base, governance log and the
service layer (`SIB`/`DEC`/`DISP`/`COMP`/`SVC`/`REQ`).

## Layer 0 -- oracle integrity

| Code | Severity | Rule |
|---|---|---|
| `ORACLE001` | error | A vendored oracle file is missing or does not match its pinned SHA-256. Verified by every command that consumes the oracle — `validate` and `oracle-info` report it, while `compile`, `render`, `docs` and `gen-schema` refuse to run (`--skip-validation` does not bypass it), so tampered rule data cannot reach an artifact or a generated schema. Re-pin deliberately with `python -m easkills pin-oracle`. |
| `ORACLE002` | warning | The relationship matrix declares an ArchiMate version other than 3.2. |
| `ORACLE003` | warning | The matrix contains a concept with no layer assignment in `easkills/oracle.py`. |

## Layer 1 -- schema and integrity

| Code | Severity | Rule |
|---|---|---|
| `SCHEMA000` | error | The YAML file cannot be parsed, or its top level is not a mapping. |
| `SCHEMA001` | error | The file violates `schema/model.schema.json` -- unknown key, missing required field, bad identifier pattern, or a `type` that is not an ArchiMate 3.2 concept. |
| `ID001` | error | Duplicate identifier. Reported against the second definition, naming the file holding the first. |
| `ID002` | error | The same identifier is used by both an element and a relationship. |
| `REF001` | error | A relationship endpoint does not resolve to an element in this zone. |
| `REF002` | error | A view includes an element that is not in the model. |
| `REF003` | warning | A view has no elements on it. |

## Layer 1 -- traceability

Traceability is verified, not trusted. A model whose citations are unchecked is a model
whose citations may be invented, and invented citations are a documented failure mode of
language-model extraction.

| Code | Severity | Rule |
|---|---|---|
| `PROV001` | error | No provenance and not marked `assumed: true`. Every concept is either evidenced or an explicit assumption. |
| `PROV002` | error | The cited source file does not exist. |
| `PROV003` | error | The quote does not occur in the cited file (whitespace- and case-insensitive). A citation that cannot be located is a fabricated citation. |
| `PROV004` | warning | The quote matches only approximately (similarity at or above `quoteMatchThreshold`, default 0.90). Quote verbatim text instead of paraphrasing. |
| `PROV005` | error | Marked `assumed: true` with no rationale. |
| `PROV006` | info | A declared assumption, listed so it can be confirmed or dropped at review. |
| `PROV007` | error | Provenance references a fact (`fact:`) that is not in the fact register. A resolved fact's own quotes are re-verified here (as `PROV002`/`PROV003`/`PROV004`, marked "via fact"), so the evidence chain stays mechanical even if the register changed after intake. |

## Layer 1 -- governance metadata

Ownership and review dates are the documented mitigations for the way EA repositories
actually die: content nobody owns, that nobody revisits. They are mandatory in the
`approved` zone and advisory in `staging`, where content is still a machine proposal.

| Code | Severity | Rule |
|---|---|---|
| `GOV001` | error / warning | No `owner`. Error in `approved`, warning in `staging`. |
| `GOV002` | error / warning | No `lastReviewed`. Error in `approved`, warning in `staging`. |
| `GOV003` | error | `lastReviewed` is not a valid ISO date. |
| `GOV004` | warning | Not reviewed within `stalenessDays` (default 365). |
| `GOV005` | warning | `lastReviewed` is in the future. |

## Layer 2 -- ArchiMate semantics

| Code | Severity | Rule |
|---|---|---|
| `REL001` | error | The relationship type is not permitted between these two element types by the ArchiMate 3.2 matrix. The message lists what *is* permitted, and says so explicitly when the relationship would be legal in the opposite direction -- swapped endpoints are the most common authoring mistake. |
| `REL002` | error | Composition or aggregation closes a cycle. Structural containment must form a hierarchy. |
| `REL003` | warning | Another relationship already has the same type, source and target. |

## Layer 2 -- motivation and applicability (AD-09)

`appliesTo` is the applicability selector on Motivation-layer elements: which
capabilities or systems a requirement, constraint, principle or goal binds. It is what
the agent context packs (`ea-context`, Phase 4) will be scoped by.

| Code | Severity | Rule |
|---|---|---|
| `MOT001` | error | An `appliesTo` entry does not resolve to an element. |
| `MOT002` | error | `appliesTo` on an element outside the Motivation layer. A dependency between architecture elements is a relationship, not a selector. |

## Layer 2 -- standards references (SIB lifecycle)

Elements declare what they follow with `standards: [std-...]`; the SIB
(`standards/`, one record per file) carries each standard's lifecycle. Deviation is
allowed only through a time-bounded dispensation -- never through silence.

| Code | Severity | Rule |
|---|---|---|
| `STD001` | error | The element references a standard that is not in the SIB. |
| `STD002` | error | The element references a **retired** standard and no open dispensation covers the pair. Migrate or file a waiver. |
| `STD003` | warning | The element references a **deprecated** standard -- plan the migration before retirement. |
| `STD004` | info | A retired/deprecated reference is covered by an open dispensation; reported with the waiver id and its expiry. |

## Layer 2 -- ISO 42010 alignment

The checkable half of ISO/IEC/IEEE 42010 6.3-6.4: stakeholders hold concerns, views
frame them, and the loop is closed. Reference errors are always on; the coverage
warnings fire only once the repository declares stakeholders or concerns, so a model
that has not started the documentation apparatus is not nagged about it.

| Code | Severity | Rule |
|---|---|---|
| `ISO001` | error | A view frames a concern that is not declared. |
| `ISO002` | error | A stakeholder holds a concern that is not declared. |
| `ISO003` | warning | A concern is framed by no view -- a documented gap in the architecture description. |
| `ISO004` | warning | A stakeholder holds no concerns. |
| `ISO005` | warning | A view frames no declared concern -- a view that answers no stakeholder question is a view nobody reads. |
| `ISO006` | warning | No stakeholder holds the concern -- an ownerless concern cannot be prioritised or confirmed. |

## Layer 2 -- conventions and smells

| Code | Severity | Rule |
|---|---|---|
| `NAME001` | warning | The name contains a placeholder (`TBD`, `TODO`, `XXX`, `???`, ...). |
| `NAME002` | warning | The name has leading, trailing or doubled whitespace. |
| `NAME003` | warning | The name is shorter than three characters. |
| `NAME004` | warning | Another element of the same type already has this name. Duplicate names are an EA smell and break traceability for anyone reading a view. |
| `SMELL001` | warning | The element has no relationships (isolated element / dead component). `appliesTo` bindings count as connectivity, in both directions. |

## Zone semantics

`staging` is validated as an **overlay on `approved`**: staging is a proposed delta,
so a staging relationship may reference approved elements, and a staging concept
re-using an approved id is an update proposal, not `ID001`. Governance metadata
(`GOV001`/`GOV002`) warns in staging and blocks at the promotion gate
(`python -m easkills promote`), which validates approved + staging merged, by
approved-zone standards. Promotion is the only write path into `approved` (AD-02);
the git commit of the moved files is the approval record.

## Fact register -- structure and traceability

Facts are what `ea-intake` extracts from raw sources, upstream of any ArchiMate
typing. A fact has **no** `assumed` escape hatch: a statement that cannot cite a
source is a clarification question, not a fact, so a missing `provenance` is a
schema error rather than a distinct rule.

| Code | Severity | Rule |
|---|---|---|
| `FACT000` | error | A register file cannot be parsed, or its top level is not a mapping. |
| `FACT001` | error | The file violates `schema/facts.schema.json` or `schema/entities.schema.json` -- unknown key, missing required field (including `provenance`), bad identifier pattern. |
| `FACT002` | error | Duplicate fact id. Reported against the second definition, naming the file holding the first. |
| `FACT003` | error | The cited source file does not exist. |
| `FACT004` | error | The quote does not occur in the cited file (whitespace- and case-insensitive). A citation that cannot be located is a fabricated citation. |
| `FACT005` | warning | The quote matches only approximately (similarity at or above `quoteMatchThreshold`, default 0.90). Quote verbatim text instead of paraphrasing. |
| `FACT006` | error | The fact references an entity id that is not in `facts/entities.yaml`. |
| `FACT007` | warning | Another fact already makes the same statement. Merge them and keep both quotes as provenance. |

## Fact register -- entity resolution

The entity table is what stops "the portal", "online order portal" and "Order
Portal" from becoming three different applications downstream.

| Code | Severity | Rule |
|---|---|---|
| `ENT001` | error | Duplicate entity id. |
| `ENT002` | error | A canonical name or alias resolves to more than one entity. One term, one entity -- a collision means downstream modelling would silently merge two things. |
| `ENT003` | warning | The entity is never referenced by any fact. |
| `SRC001` | warning | A file under `facts/sources/` is never cited by any fact -- it has not been ingested, or contains nothing extractable (which the intake report should say explicitly). |

## Governance log -- standards base

| Code | Severity | Rule |
|---|---|---|
| `SIB000` | error | A standards file cannot be parsed, or is not a single mapping. |
| `SIB001` | error | The file violates `schema/standard.schema.json`. |
| `SIB002` | error | Duplicate standard id. |
| `SIB003` | error | `successor` names something that is not a standard in the SIB. |
| `SIB004` | warning | A deprecated/retired standard names no successor -- teams being moved off a standard need to know what to move to. |

## Governance log -- dispensations

A dispensation is a time-bounded waiver. `expires` is required by schema: a
dispensation without an expiry is the tell of fake governance -- and an expiry
nobody acts on is equally fake, so expiry is an error, not a shrug.

| Code | Severity | Rule |
|---|---|---|
| `DISP000` | error | File cannot be parsed / not a single mapping. |
| `DISP001` | error | Violates `schema/dispensation.schema.json` (this is where a missing `expires` fails). |
| `DISP002` | error | Duplicate dispensation id. |
| `DISP003` | error | Expired and still open -- expiry re-triggers review: renew with a fresh grant or set `status: closed`. |
| `DISP004` | error | `appliesTo` names an element that is not in the approved model. |
| `DISP005` | error | `waives.standard` names an unknown standard. |
| `DISP006` | warning | Expires within 30 days -- schedule the review now. |
| `DISP007` | error | `expires` is before `granted`. |

## Governance log -- decisions

| Code | Severity | Rule |
|---|---|---|
| `DEC000` | error | File cannot be parsed / not a single mapping. |
| `DEC001` | error | Violates `schema/decision.schema.json` (rationale is mandatory -- ISO 42010 6.10). |
| `DEC002` | error | Duplicate decision id. |
| `DEC003` | error | `supersededBy` names a record that does not exist. |
| `DEC004` | warning | Status is `superseded` but no successor record is named. |
| `DEC005` | error | `relatedElements` names an element that is not in the approved model. |

## Governance log -- compliance assessments

| Code | Severity | Rule |
|---|---|---|
| `COMP000` | error | File cannot be parsed / not a single mapping. |
| `COMP001` | error | Violates `schema/compliance.schema.json` (verdict is one of TOGAF's six levels). |
| `COMP002` | error | Duplicate assessment id. |
| `COMP003` | warning | `non-conformant` with no `followUp` -- a failed assessment must lead to a dispensation, a decision, or documented remediation. |
| `COMP004` | error | `followUp` references a dispensation or decision that does not exist. |
| `COMP005` | error | `relatedElements` names an element that is not in the approved model. |

## Service layer -- catalog (AD-10)

Architecture-as-a-Service: EA's offerings live in `services/`, one per file. An
offering is a promise with a number -- owner and SLA are schema-mandatory.

| Code | Severity | Rule |
|---|---|---|
| `SVC000` | error | File cannot be parsed / not a single mapping. |
| `SVC001` | error | Violates `schema/service.schema.json` (owner, `slaDays` and fulfilment are required). |
| `SVC002` | error | Duplicate service id. |

## Service layer -- demand ledger

Requests (`governance-log/requests/`) record who asked for which offering.
Consumption that is not recorded cannot be measured -- and demand is what
maintenance is weighted by (`staleness` shows per-element demand; `kpi` shows the
service line).

| Code | Severity | Rule |
|---|---|---|
| `REQ000` | error | File cannot be parsed / not a single mapping. |
| `REQ001` | error | Violates `schema/request.schema.json`. |
| `REQ002` | error | Duplicate request id. |
| `REQ003` | error | References an offering that is not in the catalog. |
| `REQ004` | error | `scope` names an element that is not in the approved model. |
| `REQ005` | error | `fulfilled` status without a fulfilment date or a deliverable pointer -- an unevidenced fulfilment is a closed ticket, not a service. |
| `REQ006` | warning | Open past the offering's `slaDays`. Fulfil, decline with a reason, or renegotiate the catalog promise. (A warning, not an error: a late answer does not make the *model* wrong -- but breaches surface in `kpi` and on the board agenda.) |
| `REQ007` | warning | Declined without `notes` -- a refusal needs a reason the requester can read. |
| `REQ008` | warning | Requests a retired offering. |

## Not yet implemented

Stated so nobody mistakes silence for a clean bill of health:

* **Derivation rules** (DR1--DR8) and **potential derivation rules** (PDR1--PDR12) from
  Appendix B of the specification, and the Appendix B.4 restrictions on cross-domain
  derivation. The direct-relationship matrix is enforced; derived relationships are not
  yet checked.
* **The wider EA smells catalogue.** The gate implements `SMELL001` plus duplicate
  naming; the debt register (`python -m easkills debt`) adds unsupported capabilities,
  hub elements, stale content and dead-standard references as report-level queries.
  Cyclic dependency beyond composition and strict-layer violations remain unchecked.
* **Verb-phrase naming for behaviour elements.** The convention (noun phrases for
  structure, verb phrases for behaviour) is real but needs more than a regex to check
  honestly, so it is not pretended at.
* **ISO/IEC/IEEE 42010:2022 clause 6.9 (correspondences).** The conformance checklist
  (`python -m easkills conformance`) covers 6.2-6.8 and 6.10 and reports 6.9 as an
  explicit `gap` -- never as silent conformance.
