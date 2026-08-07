# Getting started: from a raw interview to a governed architecture

This tutorial walks the whole pipeline once, by hand, so you know what the agent
skills automate and what the gates enforce. It takes about twenty minutes. You need
Python ≥ 3.11 and a clone of this repository:

```bash
python -m pip install -r requirements.txt
```

Throughout, `python -m easkills <cmd> --help` shows every flag, and
[CLI.md](CLI.md) is the full reference. Exit code 0 means the gate passed; 1 means
error-severity findings — the same commands are your CI.

## 0. Scaffold a repository

Copy [`template/`](../template/) somewhere and make it yours:

```bash
cp -r template ~/my-ea && cd ~/my-ea
git init && git add -A && git commit -m "Scaffold from ea-skills template"
```

Edit `ea.config.yaml` — set the `name` and a one-paragraph `documentation` stating
what this model exists to decide. A model with no stated audience goes unused; the
ISO 42010 conformance check (6.2) will hold you to it.

The scaffold also brings `.github/ISSUE_TEMPLATE/change_request.md`: in your repository
the issue *is* the change-request record (step 6), which is why the form asks for ids
from `model/approved/`, `standards/` and `governance-log/decisions/`.

## 1. Drop in a source and extract facts

Put raw material into `facts/sources/` — an interview transcript, a systems-inventory
export, meeting notes. **Never edit sources**; they are the evidence everything else
points into. Then split them into extraction chunks:

```bash
python -m easkills chunk --root .
```

Now extract facts — atomic statements, each with a **verbatim quote** — into
`facts/register/<source>.yaml`, and canonical names with aliases into
`facts/entities.yaml` (this is what the `ea-intake` skill does chunk by chunk, with a
gleaning pass):

```yaml
# facts/register/interview.yaml
facts:
  - id: fact-erp-role
    statement: The ERP core holds the master order records and performs invoicing.
    provenance:
      - file: facts/sources/interview.md
        quote: The ERP core holds the master order records and does the invoicing.
    entities: [erp-core]
```

Gate it, then measure what you missed:

```bash
python -m easkills validate-facts --root .    # every quote located in its source
python -m easkills coverage --root .          # uncited statements, with line numbers
```

A fabricated quote is an **error** (`FACT004`), not a nitpick — this stage is the
quality ceiling of everything downstream. Uncited source statements are candidate
clarification questions, not defects.

## 2. Model — capability map first, everything as a delta

Model into `model/staging/` (never directly into `approved/`), citing facts:

```yaml
# model/staging/strategy.yaml
elements:
  - id: cap-order-management
    type: Capability
    name: Order Management
    owner: ea@yourco.example
    lastReviewed: 2026-08-04
    provenance:
      - fact: fact-erp-role
```

One concept per authored file group, so diffs stay reviewable — the applications that
realize the capability go in their own file:

```yaml
# model/staging/application.yaml
elements:
  - id: app-erp-core
    type: ApplicationComponent
    name: ERP Core
    owner: finance-systems@yourco.example
    lastReviewed: 2026-08-04
    provenance:
      - fact: fact-erp-role
relationships:
  - id: rel-erp-realizes-order-management
    type: Realization
    source: app-erp-core
    target: cap-order-management
    provenance:
      - fact: fact-erp-role
```

Build the capability map first (6–12 noun-phrase capabilities), then attach the
applications that realize them (as above), then the rest. When you believe something
the sources do not say, declare it: `assumed: true` plus a `rationale` — it will
surface as an open question instead of masquerading as fact.

```bash
python -m easkills validate --root . --zone staging
```

Staging validates as an *overlay* on approved: proposals may reference approved
elements, and re-using an id proposes an update. If `REL001` fires, read the
message — it lists what ArchiMate 3.2 permits between those two types and tells you
when your endpoints are simply swapped. Cap yourself at three fix-and-revalidate
rounds; unresolved findings are review questions, not grinding material.

## 3. Promote — the human gate

```bash
python -m easkills promote --root . --dry-run   # the gate + the plan
python -m easkills promote --root .             # move staging -> approved
git add -A && git commit -m "Approve initial capability map and application layer"
```

The gate judges approved+staging merged **by approved-zone standards**: missing
owners or review dates block here. The commit is the approval record — promotion is
a decision a human signs, which is why the `ea-approve` skill refuses to run
unprompted.

## 4. Document — stakeholders, views, the description

Declare who the architecture is for and what they ask (`model/approved/…` via the
same staging→promote flow):

```yaml
stakeholders:
  - id: stakeholder-cio
    name: CIO
    concerns: [concern-portfolio]
concerns:
  - id: concern-portfolio
    statement: Which applications support which capability, and where is investment due?
views:
  - id: capability-realization
    name: Capability Realization
    viewpoint: Capability Map
    concerns: [concern-portfolio]
    include: [cap-order-management, app-erp-core]
```

The `ISO*` rules keep the loop closed: every concern held by someone, framed by some
view; every view answering a declared question. Then generate everything:

```bash
python -m easkills docs --root .      # ISO 42010 description + SVG views into docs/
python -m easkills compile --root .   # ArchiMate Open Exchange XML into build/
```

Open `build/model.xml` in [Archi](https://www.archimatetool.com/) (File → Import →
Model Exchange File) — the model is real interchange, not a lookalike.

## 5. Govern — standards, exceptions, decisions

```yaml
# standards/std-postgres-16.yaml
id: std-postgres-16
name: PostgreSQL 16 for relational storage
type: organisation
lifecycle: active
owner: infra@yourco.example
```

Reference it from elements (`standards: [std-postgres-16]`). Retire a standard and
every element still on it becomes an error — the honest exits are migration or a
**dispensation** with a mandatory expiry that will error the day it passes. Record
decisions as MADR files (rationale is schema-required), assessments with TOGAF's
six-level verdict, and your service catalog with SLAs:

```bash
python -m easkills validate-gov --root .
```

## 5a. Already have a model? Import it

```bash
python -m easkills intake-csv --root . --file inventory.csv   # a spreadsheet becomes a citable source
python -m easkills import --root . --file legacy-export.xml   # Archi: File > Export > Model To Open Exchange File
python -m easkills validate --root . --zone staging           # the findings ARE the adoption backlog
```

Everything lands in `model/staging/` marked `assumed` — the old tool's content is a
claim, not evidence. Owners and review dates are lifted where the export carried
them; what the 3.2 matrix forbids is reported by the gate, not silently kept.
Promote in slices (`ea-import` explains the discipline), evidence what matters
through intake, and let the rest sit visibly in staging.

## 5b. Ask whether a layer is done

Two yardsticks, and the first one is inside the model already:

```bash
python -m easkills readiness --root .                    # the approved model
python -m easkills readiness --root . --zone staging     # including what you are proposing
```

One checkpoint list per layer, each finding naming the elements that fail it: capabilities
nothing realizes *and* nothing has assessed, processes attached to neither a capability nor
a service, applications with no `lifecycle`/`timeDisposition` (invisible to every portfolio
report until they have one), services with no consumer, infrastructure serving nothing,
obligations binding nothing, and layers your fact register covers while your model does not.

**Nothing there is an error.** An unfinished layer is not a wrong model, and a layer you
have not started is printed as `empty` rather than flagged. Read it as a worklist — and
never close a checkpoint with an edge you cannot evidence, because a fabricated Realization
satisfies the report and corrupts the model. The honest way to close an unsupported
capability is to record the weakness (`properties: {assessment: weak}`, or a `Gap`
element): the gap stops being *unexamined*, which is what the checkpoint actually asks.

```bash
python -m easkills readiness --root . --strict    # a completeness claim, for CI
```

Add that gate when the report is one you would defend, not on day one.

## 5c. Measure against a reference architecture

`coverage` (step 1) answers *did we model what we were told*. It cannot answer *is this
layer done*, because the sources are not a yardstick — they are one conversation. A
**reference model** is the second yardstick: an industry blueprint's list of what a
business like yours has.

Drop one into `reference/<name>/` — a taxonomy (`model.yaml`), a `NOTICE.md` saying where
it came from and under what licence, and the pins:

```bash
mkdir -p reference/wholesale-core
$EDITOR reference/wholesale-core/model.yaml reference/wholesale-core/NOTICE.md
python -m easkills pin-reference --root . --reference wholesale-core
python -m easkills align --root .
```

Every node comes back as a **gap** at first, which is the honest starting point. You close
them by authoring `reference/<name>/mappings.yaml`: one entry per node, either naming the
local elements that answer it (`covered`, or `partial` with a note saying what is missing)
or recording that it is `out-of-scope` **with a rationale** — without one the node stays a
gap, because a silent exclusion excludes nothing (`ALN005`). That asymmetry is the whole
feature: a gap you decided about looks different from a gap nobody noticed.

```bash
python -m easkills align --root . --zone staging       # what promotion would close
python -m easkills align --root . --strict             # gaps fail: for a repo claiming completeness
python -m easkills align --root . --min-coverage 80    # or a floor, while you fill in
```

The tooling ships only openly licensed packs (`references/` in this repository — NIST CSF
2.0 is public domain). BIAN, APQC PCF, eTOM and the rest are **licensed**: export them
from the copy your organisation holds. Never let a person or an agent type a licensed
taxonomy from memory — it is a licence problem and a fabrication problem at once, and
nobody can tell an accurate transcription from a plausible one. Judgement calls (which
reference, how coarse a mapping may be, when a gap is a business choice) are the
[`ea-align`](../skills/ea-align/SKILL.md) skill's subject.

## 5d. If you are regulated: the DORA register

Skip this if you are not. If you are an EU financial entity, tag every ICT element DORA
puts in scope — on the element, not in a list somewhere:

```yaml
properties:
  regulatoryScope: dora
  doraCriticality: critical        # critical | important | standard
  provider: PaySwitch AG
  contractRef: ctr-2023-payswitch
```

```bash
python -m easkills dora-register --root . --as-of 2026-07-30
python -m easkills dora-register --root . --as-of 2026-07-30 --out docs/dora-register.md
```

The register tabulates providers, contracts, in-scope services, the business functions
depending on them, and the open dispensations covering any of it. **It is a generator,
not an attestation** — the structure follows the shape the ESAs' technical standards ask
for, the content comes from your model, and the legal judgement belongs to whoever signs
the filing. The generated document says exactly that in its own header.

Read its **last section first**: it lists every field the register wanted and the model
did not carry, with element ids. With nothing tagged, no document is produced at all —
correct for an organisation DORA does not apply to (the worked example is a food
wholesaler, deliberately out of scope), and a warning sign for one that has simply not
tagged its estate yet. Control-framework gaps ride the reference mechanism from §5c
instead: a pack of `kind: control` nodes, an unmapped control is `ALN004`. Both are
[`ea-regulatory`](../skills/ea-regulatory/SKILL.md)'s subject.

## 5e. Turn the findings into work

Every report above ends in a list somebody has to act on. `propose` writes the *shape* of
the action into staging — and nothing else:

```bash
python -m easkills propose --root . --from align     --as-of 2026-08-07 --dry-run
python -m easkills propose --root . --from readiness --as-of 2026-08-07
python -m easkills propose --root . --from overlap   --as-of 2026-08-07
python -m easkills propose --root . --from time      --as-of 2026-08-07
```

A reference gap becomes a `Requirement`, an open checkpoint a `Constraint` bound to its
element, a rationalization candidate a `WorkPackage` naming its realizers, and a TIME
disposition no plateau carries a `WorkPackage` for scheduling it — ordered by blast
radius, so the change that reaches furthest is proposed first. Everything
lands `assumed: true` in `model/staging/proposed-*.yaml`, and **every documentation field
starts with `PROPOSED --`**: the tool writes ids, types and bindings, never prose. Text
that reads as authored and is not is the same defect as a fabricated quote.

Then do the human half — write the words ([`ea-align`](../skills/ea-align/SKILL.md) says
what a good requirement contains), add an owner and a review date, and promote. Until you
do, the gate keeps the stubs in staging, which is the point: generating is cheap,
vouching is not. The honest dispositions are **complete it or delete it**; leaving a stub
untouched is neither, and the next reader cannot tell that from work in progress.

Re-running is safe — ids are derived from the finding, so a second run after fixing some
of them shows the remainder and skips the rest by name. `--as-of` is required here, alone
among the commands, because this one writes a date into a file you will commit.

## 6. Operate — the loops that keep it alive

```bash
python -m easkills kpi --root .          # incl. the service/demand line
python -m easkills staleness --root .    # review queue, ordered by consumer demand
python -m easkills debt --root .         # EA-smell register, incl. rationalization candidates
python -m easkills conformance --root .  # ISO 42010 Clause 6 checklist
python -m easkills correspondences --root .   # §6.9: what relates to what, and the rule it is held to
python -m easkills roadmap --root .      # plateaus, gaps, and intent nothing schedules
python -m easkills delta --root .        # what the facts know that the model doesn't
python -m easkills maturity --root .     # level 1-5 per dimension, and what blocks the next
python -m easkills context --root . --scope <element-id>   # pack for a dev team/agent
```

`debt` will also cost its own findings, but only once you tell it what things are worth.
Add a `costModel` block to `ea.config.yaml` (the scaffold ships it commented out) with a
currency and whichever unit rates your organisation can defend — per stale element-day,
per open dispensation-day, per element on a dead standard, per unrealized capability, per
surplus realizer. **The tool computes the exposure; you priced it.** Set only the rates
you can source: an exposure with no rate is printed as *not priced* beside the total,
which is a true statement, and a plausible guess is not. With no `costModel` the register
prints exactly what it printed before — the feature is invisible until you opt in.

When a change request arrives, do not eyeball its blast radius:

```bash
python -m easkills impact --root . --scope <element-id>              # the approved model
python -m easkills impact --root . --scope <element-id> --zone staging   # including proposals
python -m easkills render --root .                                   # views to SVG, without the full docs run
```

`impact` counts the stakeholder groups the change touches — the number TOGAF Phase H
triage turns on — and lists the decisions, obligations, waivers and consumer requests
inside the radius. It answers the arithmetic half and says so; the classification
stays a recorded judgement (`ea-change-triage`).

Product repositories can gate on this too: `python -m easkills check --root <this repo>
--repo . --scope <element-id>` fails a team's CI when a dependency implements a retired
standard with no dispensation (`ea-check`).

New information arrives → back to step 1, scoped to what changed (`ea-delta-ingest`);
someone asks EA for something → record it in `governance-log/requests/`
(`ea-service`) and let demand steer the maintenance queue.

## Working with the agent skills

Everything above is what the 24 [agent skills](../skills/) instruct an agent to do —
with the judgement calls (what is a capability, which concern a view frames, when to
decline a request) spelled out per skill. Point your agent at this repository, start
with `ea-run` (it checks repo state and routes), and keep one rule in view: **the
gates decide, the agent proposes.** If a gate blocks, the fix is better evidence or
better modelling — never a bypass flag.

## Where to go next

- [CLI reference](CLI.md) — every command and flag
- [Rule catalogue](RULES.md) — every finding you can encounter, with rationale
- [Blueprint](BLUEPRINT.md) — why the design is the way it is, with the research
- [Golden set](../eval/golden/README.md) — how pipeline quality is measured
