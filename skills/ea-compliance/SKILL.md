---
name: ea-compliance
description: Assess a project or system against the approved architecture and record the verdict with TOGAF's six compliance levels. Use when asked to review a solution against the architecture, run a compliance check or architecture review, or when a non-conformant assessment needs recording and follow-up.
---

# Compliance assessment

An assessment compares *what a project is building* against *what the approved
architecture says*, and records the verdict on TOGAF's six-level spectrum -- because
"pass/fail" hides exactly the distinctions that matter:

| Verdict | Meaning |
|---|---|
| `irrelevant` | The architecture does not cover what this project does. |
| `consistent` | Follows the spirit; specification not fully used. |
| `compliant` | Follows the architecture where it applies; gaps where it is silent. |
| `conformant` | Uses the specification correctly; adds beyond it. |
| `fully-conformant` | Matches the specification completely. |
| `non-conformant` | Violates it. Must lead somewhere (see below). |

```yaml
# governance-log/compliance/comp-2026-07-order-portal.yaml
id: comp-2026-07-order-portal
subject: Order portal hosting review, July 2026
date: 2026-07-22
assessor: ea@example.test
verdict: conformant
findings:
  - Hosted in managed cloud, per std-cloud-hosting.
  - Consumes the order API only; no direct database access.
relatedElements: [app-order-portal]
```

## Method

1. **Scope from the model, not from memory.** Generate the checklist inputs with
   `python -m easkills context --scope <element>`: the binding requirements and
   constraints (`appliesTo`), the standards with their lifecycle, and the decisions
   that apply. That *is* the tailored checklist -- assess against those, item by
   item, and put the per-item outcomes in `findings`.
2. **Judge with evidence.** Every finding cites something observable (a config, a
   manifest, an interview answer). "Seems fine" is not a finding.
3. **Pick the verdict honestly.** The common dodge is `compliant` for things that
   are actually `consistent` (vibes-level alignment). If you are unsure between two
   levels, take the lower and say why.

## Non-conformant must lead somewhere

A `non-conformant` verdict with no `followUp` draws `COMP003` -- a failed assessment
that goes nowhere is theatre. The three honest exits:

* the project fixes it (note in `followUp.notes`, re-assess later);
* a **dispensation** is granted (`ea-dispensation`) -- time-bounded, by a real authority;
* the architecture itself is wrong -- an ADR (`ea-adr`) changes it, and the
  assessment links that decision.

`followUp.dispensation` / `followUp.decision` must reference real records (`COMP004`).

Validate with `python -m easkills validate-gov`. Report the verdict, the findings
that drove it, and the follow-up path -- in that order.
