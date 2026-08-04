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

Build the capability map first (6–12 noun-phrase capabilities), then attach
applications via `Realization`, then the rest. When you believe something the
sources do not say, declare it: `assumed: true` plus a `rationale` — it will surface
as an open question instead of masquerading as fact.

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

## 6. Operate — the loops that keep it alive

```bash
python -m easkills kpi --root .          # incl. the service/demand line
python -m easkills staleness --root .    # review queue, ordered by consumer demand
python -m easkills debt --root .         # EA-smell register
python -m easkills conformance --root .  # ISO 42010 Clause 6 checklist
python -m easkills delta --root .        # what the facts know that the model doesn't
python -m easkills context --root . --scope <element-id>   # pack for a dev team/agent
```

New information arrives → back to step 1, scoped to what changed (`ea-delta-ingest`);
someone asks EA for something → record it in `governance-log/requests/`
(`ea-service`) and let demand steer the maintenance queue.

## Working with the agent skills

Everything above is what the twenty [skills](../skills/) instruct an agent to do —
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
