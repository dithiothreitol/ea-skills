---
name: ea-run
description: Orchestrate the EA pipeline - route a request to the right ea-* skill and keep the stage order honest. Use when a request spans multiple stages ("model our architecture from these documents"), when unsure which ea-* skill applies, or when resuming work in an EA repository whose state you have not inspected yet.
---

# Routing the pipeline

The stages depend on each other; the most common failure is starting downstream of
missing input. Establish the repository's state first, then route.

## State check (one minute, always)

```bash
python -m easkills validate-facts --root .   # is there a verified fact register?
python -m easkills validate --root . --zone approved
python -m easkills validate --root . --zone staging
python -m easkills validate-gov --root .     # governance records healthy?
python -m easkills delta --root .            # unmodelled entities / unused facts
python -m easkills align --root .            # is there a reference yardstick, and where does it stand?
```

## Routing table

When a `services/` catalog exists, route **catalog-first**: an incoming ask that
matches an offering becomes a recorded request (`ea-service`) and is fulfilled
through that offering's path -- the ask defines the scope, and the scope caps the
work (on-demand discipline: model the slice the request needs, nothing more).
Everything else routes by situation:

| Situation | Skill |
|---|---|
| Someone asks EA for something an offering covers | `ea-service` (record it, then fulfil via the offering) |
| New raw documents; empty or stale fact register | `ea-intake` |
| Facts exist, no capability map | `ea-capability-map` (the spine comes first) |
| Facts + capability map; elements/relations to add | `ea-model` |
| Staging has content; human asks to publish | `ea-approve` (never on your own initiative) |
| Who is this for / concerns unclear / ISO findings | `ea-stakeholders` |
| Views needed or stale | `ea-views`; then `ea-docs` for the description |
| New info against an existing model | `ea-delta-ingest` |
| A change request arrives | `ea-change-triage` first, then its route |
| Standards, waivers, decisions, assessments | `ea-standards-base` / `ea-dispensation` / `ea-adr` / `ea-compliance` |
| "Is this done / complete?" · gap analysis against a reference model or industry blueprint | `ea-align` (there is no answer without a yardstick) |
| Regulation, control frameworks, ICT third-party risk, "the DORA register" | `ea-regulatory` — control gaps are `align` against a `kind: control` pack; the register is `dora-register`, and it generates rather than attests |
| "Make a backlog out of these findings" · gaps into requirements or work packages | `propose --from align\|readiness\|overlap\|time` writes the skeletons; the words, owner and review date are the human half (`ea-align`, `ea-adr`) |
| Downstream repo needs its constraints | `ea-context` |
| Periodic health / board preparation | `ea-health` / `ea-board` |
| "How mature is our architecture practice?" | `maturity` via `ea-health` — five dimensions, never one number; the blockers are the answer |
| "Do two systems do the same thing?" · application rationalization | `ea-health` reads the `debt` overlap items; the verdict goes to `ea-change-triage` (undecided overlap classifies **up**) or `ea-board`, and deliberate redundancy ends in `ea-adr` |
| Skill behaviour changed | `ea-eval` |

## Order for a from-scratch engagement

`ea-intake` → `ea-stakeholders` → `ea-capability-map` → `ea-model` (layer by layer,
staging) → `ea-validate` → human review → `ea-approve` → `ea-views` → `ea-docs` →
governance records as they arise. Do not compress stages: modelling without a fact
register produces unevidenced concepts the validator will reject; views before
stakeholders produce diagrams nobody asked for.

## Rules that hold across every route

* Deterministic gates decide, skills propose. If a gate blocks, fix inputs -- never
  bypass flags in anything you present as done.
* Three-repair cap everywhere; after that, escalate the open question.
* `approved/` changes only via `promote`, on explicit human instruction.
* Report at the end of any multi-skill run: which stages ran, gate verdicts, what is
  staged awaiting review, and the open questions -- one consolidated summary, not one
  per skill.
