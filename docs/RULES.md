# Rule catalogue

Every rule is deterministic. None of them consults a language model, and every one is
exercised by a case in `eval/fixtures/broken/` -- adding a rule means adding a fixture
case for it, otherwise the test suite fails to prove the rule works.

Severity meanings:

* **error** -- the model is wrong. Exit code 1; the compiler refuses to run.
* **warning** -- the model is questionable. Passes by default, fails under `--strict`.
* **info** -- a declared, accepted state worth surfacing (currently: assumptions).

Three validators share this catalogue: `python -m easkills validate` covers the model
zones (`ORACLE`/`SCHEMA`/`ID`/`REF`/`PROV`/`GOV`/`MOT`/`STD`/`ISO`/`REL`/`NAME`/`SMELL`/`PLAT`),
`python -m easkills validate-facts` covers the fact register (`FACT`/`ENT`/`SRC`), and
`python -m easkills validate-gov` covers the standards base, governance log, the
service layer and the correspondences that cross between them
(`SIB`/`DEC`/`DISP`/`COMP`/`SVC`/`REQ`/`CORR`). Three further commands own a family each,
deliberately kept out of the model gate so it stays focused: `python -m easkills
readiness` (`RDY`) asks whether each layer is *finished*, `python -m easkills align`
(`ALN`) measures the model against a reference architecture, and `python -m easkills
check` (`CHK`) runs outside this repository entirely — in a consuming product
repository. All three are catalogued in their own sections at the end.

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
| `SCHEMA002` | error | An `ea.config.yaml` value other rules depend on is unusable: `stalenessDays`/`quoteMatchThreshold` not a number or outside its usable range, or `factsRoot`/`sourcesDir` resolving outside the repository. The documented default is applied so the run still completes -- but a silently mis-set threshold decides whether fabricated quotes pass, so it is an error, never a fallback in silence. The file is additionally checked against `schema/ea-config.schema.json`, which closes the key vocabulary: an unknown top-level key or `costModel` rate key is this code too. Unlike an element's deliberately open `properties` map, a *tooling* key the tooling does not read is always a typo, and the failure is silent -- `stalenessDay` leaves the 365-day default in place while the repository looks fresh. A key both checks object to is reported once. |
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
| `PROV008` | error | The provenance `file:` resolves outside the repository (`../../secrets.txt`, or via a `factsRoot` that escapes). A quote verified against a file no reviewer can open is unreviewable traceability -- and in CI on untrusted content, pass/fail would leak whether a string exists on the runner. The file is refused, not read. |
| `PROV009` | info | The concept cites a **contested** fact: the sources disagree and this model follows one side. Reported, never blocked -- choosing is the architect's job; choosing invisibly is not. Listed in the architecture description's open questions with the other side quoted. |

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

## Zone semantics, and what promotion actually does

`staging` is validated as an **overlay on `approved`**: staging is a proposed delta,
so a staging relationship may reference approved elements, and a staging concept
re-using an approved id is an update proposal, not `ID001`. Governance metadata
(`GOV001`/`GOV002`) warns in staging and blocks at the promotion gate
(`python -m easkills promote`), which validates approved + staging merged, by
approved-zone standards. Promotion is the only write path into `approved` (AD-02);
the git commit of the moved files is the approval record.

**File shadowing.** Promotion is a rename onto the mirrored path, so a staging file
named like an approved one *replaces* it whole — anything the approved file held and
the staging file leaves out is deleted. Every zone read applies that rule (the
`--zone staging` view, the promotion gate, `compile`, `render`), so what the gate
validates is what the move produces: dropping a still-referenced element fails with
`REF001` before anything moves. A replacement that only drops unreferenced content
passes, and `promote` lists the concepts it removes — a deletion is a decision, and the
commit signs for it.

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
| `FACT008` | error | The evidence `file:` resolves outside the repository. Same rule as `PROV008`, one layer earlier: the evidence for a fact must be a source file in this repository. |
| `FACT009` | error | `confidence: contested` without a `contests:` reference. A contradiction nobody can follow is hinted at, not recorded. |
| `FACT010` | error | `contests:` names a fact that is not in the register. |
| `FACT011` | warning | The named fact does not record the disagreement back (not `contested`, or not pointing here). A one-sided contradiction reads as if one source simply won. |

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
| `DISP008` | error | `expires` or `granted` passes the schema's date *pattern* but is not a real calendar date (`2027-13-45`). An expiry that cannot be parsed cannot expire -- how a waiver becomes permanent by accident -- and the date-independent checks (`DISP004`, `DISP005`) still run alongside this finding rather than being skipped with the record. |

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
| `REQ009` | error | `requested` or `fulfilled` passes the date pattern but is not a real calendar date. SLA and fulfilment timing are computed from these fields, so an unreadable date quietly removes the request from the ledger's arithmetic. |
| `REQ010` | error | `fulfilled` is before `requested`. Both dates are real, so `REQ009` stays silent -- but the service line averages the interval between them, and a negative one reports EA as faster than it is. (The waiver-side counterpart is `DISP007`.) |

## Roadmap -- the Implementation & Migration layer

ArchiMate already carries the concepts: a `Plateau` is the architecture at a point in
time, a `Gap` is the distance between two of them, a `WorkPackage` produces a
`Deliverable`. They validated the day the schema was generated from the oracle, so
nothing is invented here. The one thing the standard does not carry is a **date**, and
without it a sequence of states is a set of states -- so `plateauDate` is a constrained
property (the `timeDisposition` lesson: if the tooling interprets a key, the schema
enumerates or patterns it) and these rules make the plan answerable.

Membership is the standard idiom: a plateau *aggregates or composes* the elements that
exist in that state. Plateaus here are expected to hold what the migration changes, not
a full copy of the architecture per plateau -- the duplicate is what goes stale first.

| Code | Severity | Rule |
|---|---|---|
| `PLAT001` | error | A `Plateau` with no `plateauDate`. A plateau without a date is a state, not a step: nothing can order it. |
| `PLAT002` | error | Two plateaus share a `plateauDate`. Two states of the architecture at the same instant is not a sequence. Reported once, against the second. |
| `PLAT003` | error | `plateauDate` passes the schema pattern but is not a real calendar date (`2027-03-32`). The roadmap is ordered by it, so an unreadable date silently drops the plateau out of the sequence -- the same trap as `DISP008`/`REQ009`. |
| `PLAT004` | warning | A `Gap` associated with no `Plateau`. A gap describes the distance between two states; one that names neither cannot be planned or closed. (Association is the only relationship the 3.2 matrix permits here -- and the one `impact` refuses to traverse, so this rule is what makes the link load-bearing.) |
| `PLAT005` | warning | An element whose TIME disposition is `Migrate` or `Eliminate` that **no plateau includes**. The portfolio decision has been taken and no plan carries it. Silent when the repository has no plateaus at all: a model that has not started planning is not breaking its roadmap. |
| `PLAT006` | warning | Every plateau is in the past. A roadmap whose horizon has passed is a record of intentions; close it or extend it. |
| `PLAT007` | warning | A `WorkPackage` that realizes no `Deliverable` -- a project with no output is one nobody can accept or refuse. |

## Correspondences (ISO 42010 §6.9)

A correspondence relates AD elements to one another; a correspondence rule is what that
relation has to satisfy. They are **derived, never authored twice**: a decision record
already names the elements it decides, a requirement already names what it binds, an
element already names the standards it follows, a concept already names the facts that
evidence it. Asking for the same relation a second time in a `correspondences:` block
would buy conformance with duplication, and the two copies would drift.

Every one of these relations crosses a boundary no ArchiMate relationship can reach
across -- into the governance log, into the fact register. Inside the model, a relation
between two elements is a *relationship*, and the oracle governs it.

| Kind | Relates | What must hold | Enforced by |
|---|---|---|---|
| `realizes` | decision → element | The decision still stands: superseded, rejected or deprecated records no longer describe the architecture. | `CORR001`, `DEC005` |
| `binds` | motivation element → element | The obligation has a bearer that is not on its way out. | `CORR002`, `MOT001`, `MOT002` |
| `governed-by` | element → standard | The standard is in the SIB and not retired, unless an open dispensation covers the pair. | `STD001`, `STD002`, `STD004` |
| `assessed-by` | assessment → element | The assessed elements are in the approved model. | `COMP005` |
| `evidenced-by` | concept → fact | The cited fact is in the register and its quotes are located in their sources. | `PROV007`, `PROV003`, `PROV001` |

Only two of those rules needed a new check; the rest were already enforced, and naming
the code that enforces them is more useful than reporting the same defect twice. Run
`python -m easkills correspondences` for the table, including every pair and its verdict.

| Code | Severity | Rule |
|---|---|---|
| `CORR001` | warning | An element of the approved model still realises a decision whose status is `superseded`, `rejected` or `deprecated`. The record is in perfect order -- successor named, rationale present -- so no `DEC*` rule can see this; what is stale is the *relation*. A warning, not an error: the model is not malformed, the governance log has simply moved on without it. |
| `CORR002` | warning | A requirement, constraint, principle or goal binds elements of which **every** one is TIME `Eliminate`. The obligation outlives its bearers -- the seven-year retention requirement nobody thinks about until the system holding the records is switched off. One eliminated bearer among several is a migration, not a gap, and is not reported. |

## Layer readiness -- `readiness` (the RDY family)

`python -m easkills readiness` is the mechanical half of "is this layer done?". One
checkpoint list per ArchiMate layer, each finding **naming the elements** that fail it —
the 0.11.0 scorer lesson, where a count without names cost three investigations that were
hand-diffs of two YAML trees.

**Nothing in this family is an error, ever.** An unfinished layer is not a wrong model,
and a report that blocked a commit for incompleteness would be switched off within a week
— after which it measures nothing while still looking like coverage. `--strict` is how a
repository that *claims* completeness opts into the gate.

**An empty layer is shown, never flagged.** The report prints `empty` beside it, so the
shape is visible without inventing a finding. Same rule that keeps `PLAT005` silent when
a repository has no plateaus: not having started a layer is not breaking it.

**A part contributes through its whole.** `RDY006`, `RDY007` and `RDY008` are satisfied
when the element *or any element that composes/aggregates it* serves or realizes
something. The worked example's `PostgreSQL 16` is composed into the ERP application
server, and the server serves the ERP — correct, idiomatic ArchiMate that the first
version of this checklist reported as unfinished technology. A checkpoint that flags
idiomatic modelling teaches people to ignore the report.

| Code | Severity | Layer | Rule |
|---|---|---|---|
| `RDY001` | warning | Strategy | A `Capability` that nothing realizes **and** whose weakness the model does not record. Both idioms count as recorded: a `properties: {assessment: ...}` value (what `ea-capability-map` teaches) or an associated `Gap`/`Assessment` element. `debt` lists *every* unsupported capability as a smell; this asks the narrower question — unsupported *and unexamined* — because an examined gap is a finding worth keeping, not a hole to fill with a plausible application. |
| `RDY002` | **info** | Strategy | A `Capability` no reference mapping anchors. Silent when no reference pack exists — no reference model, no question, rather than "every capability is unanchored". Deliberately **info**, not warning: this is the same observation `align` reports as information, and making it a warning would fail `readiness --strict` for a business doing something its industry blueprint never heard of. One observation, one severity, whichever report it appears in. |
| `RDY003` | warning | Business | A `BusinessProcess`/`BusinessFunction` realizing neither a capability nor a service. A process attached to neither cannot be read as delivering anything, and appears in no capability or portfolio view. |
| `RDY004` | warning | Business | A `BusinessActor`/`BusinessRole` attached to nothing. Overlaps `SMELL001`, which catches the total orphan in the *gate*; this asks the narrower per-layer question and can fire where `SMELL001` does not (an actor whose only link is an `Association` to another actor). |
| `RDY005` | warning | Application | An `ApplicationComponent` with no `lifecycle` or no `timeDisposition`. The TIME quadrants and the obsolescence exposure are derived from these, so until they are set the component is invisible to every portfolio report — present in the model and absent from every conversation the model exists for. |
| `RDY006` | warning | Application | An `ApplicationComponent` that realizes nothing (containment counted, see above). An application supporting no capability and publishing no service is either unmodelled work or a system nobody can justify keeping. |
| `RDY007` | warning | Application | An `ApplicationService` with no recorded consumer. Scoped to the application layer, per the increment that defined it: a `BusinessService` with no consumer is the same defect and is **not** checked yet — said out loud rather than left as an apparent clean bill of health. |
| `RDY008` | warning | Technology | A `Node`/`Device`/`SystemSoftware` that serves and realizes nothing. Infrastructure nothing runs on cannot be costed, retired or impact-assessed. |
| `RDY009` | warning | Motivation | A `Requirement`/`Constraint` with no `appliesTo` at all. Distinct from `MOT001`, where the selector exists and points at something absent: here the obligation has no bearer, so no context pack will ever serve it to the team it was written for. |
| `RDY010` | warning | cross | The fact register covers a layer (via `topics:`) that the model leaves empty — evidence gathered and never modelled, the one kind of incompleteness the *sources* can prove. The facts carrying the topic are named. `topics:` is a free tag by schema, so only values that name a layer are read: `risk` and `integration` are real topics in the golden set and neither is a layer. |

## Reference alignment -- `align` (the ALN family)

`python -m easkills align` measures the model against a **reference architecture**: a
hash-pinned taxonomy in `reference/<name>/` (`model.yaml` + `NOTICE.md` + `SHA256SUMS`)
plus a human-authored `mappings.yaml`. It answers the question `coverage` cannot — *did
we model what an industry blueprint says a business like this has*, as opposed to *did
we model what we were told*.

The family is owned by `align`, not by `validate`: a repository with no reference pack is
not an invalid repository, and the model gate stays about the model.

Three things to know before reading a report:

* **Only leaf nodes are scored.** A branch is a heading, not something an application
  realizes; branches carry a rolled-up percentage of their subtree instead. `covered`
  counts 1, `partial` counts ½ (found the connection, contested the grain — the same
  arithmetic the golden-set scorer uses for a derived relationship), `gap` counts 0,
  `out-of-scope` leaves the denominator.
* **`out-of-scope` inherits downwards; coverage does not.** Excluding a branch is one
  decision about one area, so it carries to the whole subtree. Claiming a branch covered
  would be a claim about every leaf under it, and those are earned one at a time.
* **Everything fails closed.** An exclusion without a rationale does not exclude
  (`ALN005`); a claim resting on an element this zone does not hold does not cover
  (`ALN003`, `ALN007`). Under-reporting a gap is the failure mode that matters here, so
  every ambiguity resolves towards *gap*.

`mappings.yaml` is deliberately **not** hash-pinned: it is the one file an architect
edits, so pinning it would make re-pinning a reflex, and a pin you re-run without reading
is not a pin. The taxonomy is what must not move underneath a coverage claim.

| Code | Severity | Rule |
|---|---|---|
| `ALN000` | error | A reference or mapping file cannot be read: unparsable, top level not a mapping, violating `schema/reference.schema.json` / `schema/reference-mappings.schema.json`, or structurally impossible in a way no schema expresses — a duplicate node id, a `parent` that is not a node of the same pack, a parent cycle. This is also where a coverage claim with no `elements` lands, because a claim with nothing behind it is not a claim. |
| `ALN001` | error | The pack does not match its pinned SHA-256 sums, has no `SHA256SUMS`, or does not pin `model.yaml` and `NOTICE.md`. The pack is **refused, not read**: coverage measured against an edited taxonomy is not a measurement, so no node of it is reported as covered *or* as a gap. Same discipline as `ORACLE001`; re-pin with `pin-reference` only for a deliberate, reviewed upgrade. |
| `ALN002` | error | A mapping targets a node id the reference does not hold. A mapping to nothing is coverage of nothing. |
| `ALN003` | error | A mapping names an element id that is not in the zone being read. Check the id, or model the thing before claiming it as coverage. |
| `ALN004` | warning | **The gap**: a leaf node is mapped to nothing and not declared out-of-scope. Either the architecture has a gap there, or the decision not to cover it is unrecorded — and those are different problems with the same silence. A warning, not an error: an unmapped node is a question. Suppressed when a more specific code already names that node as the reason it is a gap (`ALN003`, `ALN005`, `ALN007`), which keeps the finding list free of duplicates while the node table still shows every gap. |
| `ALN005` | error | `out-of-scope` with no rationale. Out-of-scope is a decision somebody signs; without one the node is reported as a gap, so a silent exclusion excludes nothing. |
| `ALN006` | error | Two mapping entries target one reference node. One node, one recorded judgement — the first is kept and the second reported, because two entries usually disagree. |
| `ALN007` | warning | A mapping claims coverage from an element that exists only in `model/staging/`, while the report reads `approved`. The node stays a gap until the proposal is promoted; `--zone staging` is how to ask what promotion would close. |
| `ALN008` | error | The pack declares no nodes. An empty yardstick reports full coverage of nothing, which is worse than no yardstick at all. Silent when `ALN000` already said the taxonomy did not parse. |

Local elements that no mapping anchors are reported as **information, never as
findings**. A business does things its industry blueprint never heard of, and a tool that
called that a defect would teach architects to model the blueprint instead of the
business.

## Regulatory register -- `dora-register` (the REG family)

`python -m easkills dora-register` generates the DORA Register of Information from the
approved model. Scope is declared per element by `properties.regulatoryScope: dora`, not
inferred from a type and not listed in config -- scope is a fact about the element, so it
lives next to it, moves with it, and shows up in the diff of the commit that changed it.

**A generator, not an attestation.** The structure follows the shape the ESAs'
implementing technical standards ask a register to have; the content comes from the
model and nowhere else; no completeness against the official templates is claimed. The
generated document says so in its own header, above the tables, and its last section
lists every field the model could not fill with the element ids missing it. That section
is the reason the document is safe to hand over: it states what it does not know.

With no element in scope, no register is produced at all -- the correct output for an
organisation the regulation does not apply to, and a deliberate refusal to emit an empty
page that looks like a filing.

| Code | Severity | Rule |
|---|---|---|
| `REG001` | warning | An in-scope element carries no `doraCriticality`. The register cannot say how much depends on it, and an unclassified dependency is the one a supervisor asks about. |
| `REG002` | error | A `critical` element has no `provider` or no `contractRef`. These are the first two fields a register is read for; a critical row with neither is not a partial answer, it is a blank. |
| `REG003` | info | A `critical` or `important` element is covered by an **open dispensation**. Exposure to disclose, not a violation to fix -- making this a warning would push people to close waivers to clear a report, losing the record of the exposure the register exists to show. |
| `REG004` | warning | A register section is empty while in-scope content exists. Silence in a regulatory document reads as "nothing to report", which is a different statement from "we did not record it". |

Control-framework gaps are **not** a REG code: a control framework is a taxonomy, so an
unmapped control is `ALN004` against a `kind: control` reference pack. One mechanism,
one rule family -- see [`ea-regulatory`](../skills/ea-regulatory/SKILL.md).

## Regulatory register -- `ai-act-register` (the AIR family)

`python -m easkills ai-act-register` generates the EU AI Act system inventory from the
approved model. Scope is declared per element by `properties.regulatoryScope: ai-act`,
never inferred from a type or from a name that sounds like AI -- and an element can be
in both registers' scope at once (`regulatoryScope: ai-act dora`, a closed enum of
alphabetical combinations; membership is read through one shared splitter so neither
register drops the row). Everything the REG family established holds here too: the
generated document says it is not a compliance record in its own header, its last
section names every field the model could not fill, and with nothing in scope no
document is produced at all.

| Code | Severity | Rule |
|---|---|---|
| `AIR001` | warning | An in-scope element carries no `aiRiskClass`. The inventory cannot say which of the Act's obligations attach, and an unclassified AI system is the one a supervisor asks about. |
| `AIR002` | error | A `high`-risk element has no `aiRole` or no `aiOversight`. The obligations differ by operator role, and Art. 14 asks who oversees the system; a high-risk row with neither is not a partial answer, it is a blank. |
| `AIR003` | info | A `high`- or `limited`-risk element is covered by an **open dispensation**. Accepted AI risk to disclose, not a violation to fix -- the mandatory expiry on a dispensation fits model-risk acceptance exactly, and closing the waiver to clear the report would lose the record of the exposure. |
| `AIR004` | warning | An inventory section is empty while in-scope content exists. Silence in a regulatory document reads as "nothing to report". The provider section is only expected once some in-scope system was made by someone else (role `deployer`/`importer`/`distributor`) -- an estate that builds everything it runs owes no such section. |
| `AIR005` | error | An approved element is classified as a **prohibited practice** (Art. 5). That is not a row to file but a decision the board must see: retire the practice or correct the classification, and record whichever happened. |

## Consuming repositories -- `ea-check` (AD-09)

`python -m easkills check` runs in a *product* repository, not in the EA repository:
it reads dependency manifests and holds them against the standards the element that
repository implements claims to follow. Detection is declared by each SIB entry
(`detect:`), so the tooling never infers that a library "is" a standard, and matching
is by dependency name -- the observed version is reported, never interpreted, because
range logic would answer questions it cannot settle.

| Code | Severity | Rule |
|---|---|---|
| `CHK000` | error | A dependency manifest cannot be parsed. An unreadable manifest cannot be declared compliant, so the check refuses rather than skipping it. |
| `CHK001` | error | `--scope` is not an element in the approved model. There is nothing to check against, and silence would read as compliance. |
| `CHK002` | error | A declared dependency implements a **retired** standard and no open dispensation covers this element. Migrate, or file a time-bounded waiver in the EA repository. |
| `CHK003` | warning | A declared dependency implements a **deprecated** standard -- plan the migration before it is retired. |
| `CHK004` | info | A retired/deprecated implementation is covered by an open dispensation; reported with the waiver id and its expiry, after which it becomes `CHK002`. |
| `CHK005` | warning | The model says this element follows a standard, but nothing in this repository evidences it -- the claim is unverified here. |
| `CHK006` | info | A dependency implements a standard the model does not record for this element: drift the model should absorb (`ea-delta-ingest`), not a build failure. |
| `CHK007` | warning | No dependency manifests found. The check ran and proved nothing -- said out loud, because an empty report otherwise reads as a clean bill of health. |

## Not yet implemented

Stated so nobody mistakes silence for a clean bill of health:

* **Potential derivation rules** (Appendix B.3) -- the derivations the specification
  itself calls *uncertain*, whose probability "depends on the specifics of the model
  concerned". A deterministic core does not guess, so they stay out.
  The **valid** derivation rules DR1--DR8 of Appendix B.2 **are** implemented
  (`easkills/derive.py`) and used by the golden-set scorer to tell "you did not draw this
  edge" from "your model implies this edge at a finer grain". They are not a *gate*: the
  relationship matrix already permits every derivable pair, so a derived relationship
  cannot be a violation. The B.4 restriction on deriving through a third domain is
  enforced in `derive.py`; the remainder of B.4 is enforced by construction, because the
  vendored matrix is what those restrictions produced.
* **The wider EA smells catalogue.** The gate implements `SMELL001` plus duplicate
  naming; the debt register (`python -m easkills debt`) adds unsupported capabilities,
  hub elements, stale content and dead-standard references as report-level queries.
  Cyclic dependency beyond composition and strict-layer violations remain unchecked.
* **Verb-phrase naming for behaviour elements.** The convention (noun phrases for
  structure, verb phrases for behaviour) is real but needs more than a regex to check
  honestly, so it is not pretended at.
* **Correspondences to elements outside this AD.** §6.9 also covers relations to AD
  elements *in another architecture description* -- another team's model, a supplier's.
  Nothing here can check the far end of one, so none is derived; the conformance
  checklist counts only correspondences whose both sides this repository holds.
