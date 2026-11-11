---
name: ea-run
description: Orchestrate the EA pipeline - route a request to the right ea-* skill and keep the stage order honest. Use when a request spans multiple stages ("model our architecture from these documents"), when unsure which ea-* skill applies, or when resuming work in an EA repository whose state you have not inspected yet.
allowed-tools:
  - Bash(easkills align *)
  - Bash(easkills delta *)
  - Bash(easkills doctor *)
  - Bash(easkills init *)
  - Bash(easkills validate *)
  - Bash(easkills validate-facts *)
  - Bash(easkills validate-gov *)
  - Bash(python -m easkills align *)
  - Bash(python -m easkills delta *)
  - Bash(python -m easkills doctor *)
  - Bash(python -m easkills init *)
  - Bash(python -m easkills validate *)
  - Bash(python -m easkills validate-facts *)
  - Bash(python -m easkills validate-gov *)
---

# Routing the pipeline

The stages depend on each other; the most common failure is starting downstream of
missing input. Establish the repository's state first, then route.

Every command in these skills is `easkills <command>`. With the ea-skills plugin
enabled, `easkills` is on the Bash tool's PATH; from a clone of ea-skills,
`python -m easkills` is the same command with the same arguments and exit codes. If
neither resolves, the tooling is not installed -- say so; do not reason your way to a
verdict the tooling exists to compute.

**One command per call, written out in full.** Each skill pre-approves the `easkills`
commands its own text prescribes, matched by their literal text -- so run each command
as its own Bash call: no loop over subcommands, no shell variable (`$TMPDIR`, `$?`), no
command substitution. A line the permission check cannot read is put to the person, and
refused outright where nobody can answer, which leaves the check unrun. You never need
`echo $?`: the Bash tool reports a non-zero exit code beside the output.

## State check (one minute, always)

No repository yet? `easkills init <directory>` writes one from the template, pinned to
this release, CI and code owners included; `easkills doctor --root <repo>` says in one line
each what the machine or the repository is missing.

```bash
easkills validate-facts --root .   # is there a verified fact register?
easkills validate --root . --zone approved
easkills validate --root . --zone staging
easkills validate-gov --root .     # governance records healthy?
easkills delta --root .            # unmodelled entities / unused facts
easkills align --root .            # is there a reference yardstick, and where does it stand?
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
| Staging has content; human asks to publish | `ea-approve` -- the human invokes it; it never loads on your initiative |
| Who is this for / concerns unclear / ISO findings | `ea-stakeholders` |
| Views needed or stale | `ea-views`; then `ea-docs` for the description |
| New info against an existing model | `ea-delta-ingest` |
| A change request arrives | `ea-change-triage` first, then its route |
| Standards, waivers, decisions, assessments | `ea-standards-base` / `ea-dispensation` / `ea-adr` / `ea-compliance` |
| "Is this done / complete?" · gap analysis against a reference model or industry blueprint | `ea-align` (there is no answer without a yardstick) |
| Regulation, control frameworks, ICT third-party risk, "the DORA register" | `ea-regulatory` — control gaps are `align` against a `kind: control` pack; the register is `dora-register`, and it generates rather than attests |
| Security architecture, threat modelling, "what could an attacker reach", data classification, zero trust, SBOMs | `ea-security` -- `exposure` walks the reach from public elements, `propose --from threats` writes the assessments, control coverage is `align` against `nist-sp-800-53-r5` |
| AI systems, "the AI Act", risk classification, the AI inventory, AI risk acceptance | `ea-ai-governance` — same mechanism one register over: gaps are `align` against `nist-ai-rmf-1.0`, the inventory is `ai-act-register`, and accepted AI risk is a dispensation with an expiry |
| "Make a backlog out of these findings" · gaps into requirements or work packages | `propose --from align\|readiness\|overlap\|time\|coverage\|threats` writes the skeletons; the words, owner and review date are the human half (`ea-align`, `ea-adr`) |
| Downstream repo needs its constraints · an ad-hoc question about the model · another agent or MCP host needs the architecture | `ea-context` -- `context` packs, `query`, and `serve` (read-only MCP) |
| "What does the target state change?" · "what changed since the last board?" · "are we getting better?" | `diff --plateau`, `diff --ref`, `trend` via `ea-board` / `ea-health` |
| Diagrams for a wiki, a pull request or slides · colour a view by lifecycle or owner | `ea-views` -- `export --format mermaid\|plantuml`, `render --heatmap` |
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
