# Rule catalogue

Every rule is deterministic. None of them consults a language model, and every one is
exercised by a case in `eval/fixtures/broken/` -- adding a rule means adding a fixture
case for it, otherwise the test suite fails to prove the rule works.

Severity meanings:

* **error** -- the model is wrong. Exit code 1; the compiler refuses to run.
* **warning** -- the model is questionable. Passes by default, fails under `--strict`.
* **info** -- a declared, accepted state worth surfacing (currently: assumptions).

Two validators share this catalogue: `python -m easkills validate` covers the model
zones (`ORACLE`/`SCHEMA`/`ID`/`REF`/`PROV`/`GOV`/`REL`/`NAME`/`SMELL`), and
`python -m easkills validate-facts` covers the fact register (`FACT`/`ENT`/`SRC`).

## Layer 0 -- oracle integrity

| Code | Severity | Rule |
|---|---|---|
| `ORACLE001` | error | A vendored oracle file is missing or does not match its pinned SHA-256. Re-pin deliberately with `python -m easkills pin-oracle`. |
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

## Not yet implemented

Stated so nobody mistakes silence for a clean bill of health:

* **Derivation rules** (DR1--DR8) and **potential derivation rules** (PDR1--PDR12) from
  Appendix B of the specification, and the Appendix B.4 restrictions on cross-domain
  derivation. The direct-relationship matrix is enforced; derived relationships are not
  yet checked.
* **The wider EA smells catalogue.** One structural smell of roughly sixty-three
  catalogued ones is implemented (`SMELL001`), plus duplicate naming. Cyclic dependency
  beyond composition, strict-layer violations and portfolio-level smells are Phase 4.
* **Verb-phrase naming for behaviour elements.** The convention (noun phrases for
  structure, verb phrases for behaviour) is real but needs more than a regex to check
  honestly, so it is not pretended at.
* **ISO/IEC/IEEE 42010:2022 conformance** of the documentation set. Phase 4.
