# <Organisation> enterprise architecture

Model repository scaffolded from the `ea-skills` template. Copy this directory, edit
`ea.config.yaml`, and start with intake — or, if you already have a model somewhere
else, with the import.

**Bring what you already have**

```bash
python -m easkills intake-csv --root . --file inventory.csv       # spreadsheet -> citable source
python -m easkills import     --root . --file export.xml          # Archi/Open Exchange -> staging
```

**Intake and modelling**

```bash
python -m easkills chunk          --root .            # split sources for extraction
python -m easkills validate-facts --root .            # the fact register gate
python -m easkills coverage       --root .            # what the facts do not cover yet
python -m easkills validate --root . --zone staging   # proposals, overlaid on approved
python -m easkills promote  --root . --dry-run        # the promotion gate, no move
python -m easkills promote  --root .                  # staging -> approved (on human sign-off)
python -m easkills validate --root . --zone approved  # the published model
```

**Publish**

```bash
python -m easkills compile  --root . --zone approved  # -> build/model.xml
python -m easkills docs     --root .                  # -> docs/ (AD + SVG views)
python -m easkills render   --root .                  # views only
python -m easkills validate-gov --root .              # standards + governance log gate
```

**Operate**

```bash
python -m easkills kpi            --root .            # one-screen health
python -m easkills staleness      --root .            # review queue, by consumer demand
python -m easkills debt           --root .            # EA-smell register
python -m easkills conformance    --root .            # ISO 42010 Clause 6 checklist
python -m easkills correspondences --root .           # §6.9, with the rule each is held to
python -m easkills roadmap        --root .            # plateaus, gaps, unscheduled intent
python -m easkills delta          --root .            # what the facts know, the model doesn't
python -m easkills impact  --root . --scope <id>      # blast radius + Phase H count
python -m easkills context --root . --scope <id>      # agent context pack (AD-09)
```

**Is it done?**

```bash
python -m easkills maturity  --root .                    # level 1-5 per dimension, no composite
python -m easkills readiness --root .                    # per-layer checkpoints, advisory
python -m easkills readiness --root . --zone staging     # including proposals
```

**Measure against a reference architecture** (see [`reference/README.md`](reference/README.md))

```bash
python -m easkills pin-reference --root . --reference <name>   # after dropping a pack in
python -m easkills align --root .                              # covered / partial / gap / out-of-scope
```

**Turn findings into staged work** — skeletons only; the words are yours to write.

```bash
python -m easkills propose --root . --from align     --as-of <date> --dry-run
python -m easkills propose --root . --from readiness --as-of <date>
python -m easkills propose --root . --from overlap   --as-of <date>
python -m easkills propose --root . --from time      --as-of <date>
```

Each stub is `assumed: true` and opens with `PROPOSED --`. Complete it or delete it;
promotion will not take it without an owner and a review date.

**If you are regulated** — tag in-scope ICT elements with `regulatoryScope: dora` plus
`doraCriticality`, `provider` and `contractRef`, then:

```bash
python -m easkills dora-register --root . --as-of <date>                      # + the fields it could not fill
python -m easkills dora-register --root . --as-of <date> --out docs/dora-register.md
```

A generator, not an attestation: read its last section first, and remember that the
legal judgement belongs to whoever signs the filing. Untagged repositories get no
document, which is the right answer when the regulation does not apply to you.

## Layout

| Path | Holds |
|---|---|
| `facts/sources/` | Raw input, unedited: interview notes, exports, documents. Provenance quotes must be findable here verbatim. |
| `facts/register/` | The fact register produced by intake: atomic statements, each with a mechanically verified quote. |
| `facts/entities.yaml` | Canonical names and aliases for the things the sources mention. |
| `model/staging/` | Machine-proposed concepts awaiting human approval. Ownership metadata is advisory here. |
| `model/approved/` | Human-signed model. Ownership and review dates are mandatory. Everything downstream reads only from here. |
| `landscape/` | Architecture landscape partitioned by scope: `strategic/`, `segments/`, `capabilities/`. Baseline, transition and target states are modelled as ArchiMate plateaus inside the model, not as copies of it. |
| `reference/` | Reference architectures this model is measured against: one directory per model, hash-pinned taxonomy plus your own `mappings.yaml`. Licensed content lives here, under your licence — see `reference/README.md`. |
| `standards/` | Standards information base. One file per standard, carrying its type (legal / industry / organisational) and lifecycle state (proposed, trial, active, deprecated, retired). |
| `services/` | Architecture-service catalog (AD-10): one offering per file with owner, fulfilment path and SLA. |
| `governance-log/requests/` | Demand ledger: who asked for which offering, with evidenced fulfilment. Demand feeds the staleness review queue. |
| `requirements/` | Architecture requirements. |
| `governance-log/decisions/` | Architecture decision records (MADR). |
| `governance-log/compliance/` | Compliance assessments, recorded with TOGAF's six conformance levels rather than pass/fail. |
| `governance-log/dispensations/` | Time-bounded waivers. **An expiry date is mandatory** -- a dispensation without one is not governance. |
| `docs/` | Generated architecture description and audience-facing outputs. |
| `build/` | Compiled artifacts. Reproducible; not committed. |

## Change requests

`.github/ISSUE_TEMPLATE/change_request.md` ships with this scaffold: in a governed
architecture repository the issue *is* the change-request record (AD-08), and
`ea-change-triage` works from it — classification, evidence and routing are filled in
on the same issue. Keep it; the ids it asks for are the ones in `model/approved/`,
`standards/` and `governance-log/decisions/` here.

## Conventions

Identifiers are stable lower-case slugs and are never regenerated. Every element and
relationship is either evidenced by a verbatim source quote or explicitly marked
`assumed: true` with a rationale. Views declare which elements to show; layout is
computed. See `docs/RULES.md` in the ea-skills repository for the full rule catalogue.
