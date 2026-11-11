---
name: ea-ai-governance
description: Govern the AI systems in the architecture and maintain the EU AI Act system inventory. Use for AI risk-framework gap analysis (NIST AI RMF), AI Act scope and risk-classification questions, the AI system inventory, recording accepted AI risk, or when asked which systems use AI and what obligations attach.
argument-hint: "[as-of YYYY-MM-DD]"
allowed-tools:
  - Bash(easkills ai-act-register *)
  - Bash(easkills align *)
  - Bash(easkills propose *)
  - Bash(python -m easkills ai-act-register *)
  - Bash(python -m easkills align *)
  - Bash(python -m easkills propose *)
---

# AI governance and the AI Act inventory

```bash
easkills align --root <repo> --reference nist-ai-rmf-1.0   # AI-risk gaps, named
easkills ai-act-register --root <repo> --as-of <date>      # the inventory + its own gaps
easkills ai-act-register --root <repo> --as-of <date> --out docs/ai-act-register.md
easkills propose --root <repo> --from ai-act --as-of <date>   # FRIA skeletons, Art. 27
```

If `propose` reports that it could not write its file (a shell that may not write, as in
a sandbox), run the same command again with `--print`: it writes nothing and prints
exactly that file, in full -- do not pipe it through `head` or `tail`. Write that
output, unchanged, to the path the error named, with your file tool. Edited on the way,
it would be your text, not the generator's.

`--lang pl` renders the inventory in Polish; the model's own text is not translated.

## Non-negotiables

* **This tooling generates; it does not attest.** The inventory's structure follows the
  concepts the AI Act reasons in — risk classes, Art. 3 operator roles, Art. 14 human
  oversight. Its content comes from the model and nowhere else. No completeness against
  the Act's registration or documentation duties is claimed and no legal review has
  happened. Say that out loud every time you hand the document over — the generated
  file says it in its own header, and that header is not decoration to be trimmed.
* **Never classify a system to make a report look calm.** `aiRiskClass` is a fact about
  what the system does, decided by what the Act says, and it is recorded next to the
  element where the next reader will find it. Downgrading a risk class to clear AIR002
  is worse than the finding — the finding is true.
* **A gap is disclosed, not closed by editing.** The inventory's last section lists
  every field the model could not fill, with element ids. Filling a field with a guess
  is worse than the gap.

## Scope: what puts a system in the inventory

One property, on the element — declared, never inferred from a type or from a name
that sounds like AI:

```yaml
properties:
  regulatoryScope: ai-act
  aiRiskClass: high            # prohibited | high | limited | minimal
  aiRole: deployer             # provider | deployer | importer | distributor | gpai-provider | ...
  aiOversight: Credit risk committee reviews every declined application
  provider: Scorewell GmbH     # who made it, when someone else did
  contractRef: ctr-2025-scorewell
```

An element can be in more than one register's scope: a bought credit-scoring service is
DORA's ICT third-party risk *and* the AI Act's high-risk system, and it declares both as
`regulatoryScope: ai-act dora` — the space-joined combination in alphabetical order,
still a closed enum. Any other spelling or order is a schema error, never a silent
row-drop; under-inclusion is the failure mode that matters in a regulatory report.

**An AI system is not a new element type.** It is an application component or a
technology service like any other, governed by the same oracle — what is AI-specific is
the evidence around it: these properties, the principles that bind it (motivation
layer), the standards it claims (`ea-standards-base`), and the accepted risk on it
(`ea-dispensation`).

## The five rules

| Code | Severity | What it means when it fires |
|---|---|---|
| `AIR001` | warning | In scope, no `aiRiskClass`. The inventory cannot say which obligations attach. |
| `AIR002` | error | High-risk, with no `aiRole` or no `aiOversight`. The obligations differ by role, and Art. 14 asks who oversees the system. |
| `AIR003` | info | A high- or limited-risk system under an **open dispensation**. Accepted AI risk to disclose, not a violation to fix. |
| `AIR004` | warning | An inventory section is empty while in-scope content exists. Silence reads as "nothing to report". The provider section is only expected once some in-scope system was made by someone else. |
| `AIR005` | error | An approved element classified as a **prohibited practice** (Art. 5). Not a row to file — a decision the board must see: retire the practice or correct the classification, and record whichever happened as a decision (`ea-adr`). |

`AIR003` works exactly like `REG003`: `ea-dispensation` grants a time-bounded waiver —
model-risk acceptance has a natural horizon, so the mandatory expiry fits AI risk
unusually well — and it surfaces in the inventory without anyone having to remember to
mention it. Do not close a dispensation to clear it, and do not leave it out.

`gpai-provider` is the role of an organisation that provides the general-purpose AI
model a system is built on (Chapter V). Those obligations differ from the system's own,
and an inventory most often forgets to say the organisation holds them -- record the
role when it is true, even when the system itself is minimal-risk.

## Fundamental-rights impact assessments (Art. 27)

`propose --from ai-act` writes an `Assessment` skeleton (`asm-fria-<element>`) into
staging for each high-risk system the organisation **deploys** with no assessment bound
to it. Art. 27 does not bind every deployer -- it binds bodies governed by public law,
private entities providing public services, and deployers of the Annex III point 5(b)
and 5(c) systems (creditworthiness, life and health insurance pricing) -- so the first
placeholder asks whether it reaches the organisation at all. If it does not, delete the
skeleton and record why as a decision (`ea-adr`); if it does, the assessment's prose,
owner and review date stay human, exactly as for every other proposal, and `ea-approve`
promotes it. A re-run skips the system by name while the skeleton sits in staging.

## The AI RMF is a reference overlay

An AI risk framework is a taxonomy, so it uses the mechanism `ea-align` already
describes: NIST AI RMF 1.0 ships in [`references/`](../../references/) (public domain)
as a hash-pinned pack — four functions, nineteen categories, each category's outcome
statement verbatim because the RMF publishes no short names. An unmapped category is
`ALN004`, and "this category does not apply to us" is a sentence somebody has to sign.
Check the pack's NOTICE first: until its structure is verified against NIST AI 100-1 by
a human reading, it is a working draft — a legitimate gap-list generator, not an
authority to cite.

ISO/IEC 42001 is licensed and stays in the adopter's repository under the adopter's
licence, same mechanism (`template/reference/README.md`) — and nothing may transcribe
it from memory.

## Keeping the inventory alive

* **Regenerate with `--as-of`, always.** Waiver expiry is date-dependent; an inventory
  with no date on it cannot be reproduced or compared to the last one.
* **Read the gap section first**, before the tables.
* **A new AI system is an intake event.** When the inventory gains a row nobody
  recognises, the model changed before the governance did; route it through
  `ea-delta-ingest` and confirm the risk class against what the system actually does.
* **Nothing in scope is a legitimate answer.** For an organisation running no AI system
  the Act reaches, `ai-act-register` reports that no element is tagged and generates
  nothing. That is the correct output — and the wrong one for an organisation that has
  simply not tagged its AI systems yet. Know which of the two you are looking at.

## Reporting back

The inventory's headline numbers (systems in scope, risk-class breakdown, third-party
providers), then three lists that need a human: the fields the model could not fill
with their element ids, the open waivers on high- or limited-risk systems, and any
`AIR005` — which is never a list item to skim but a meeting to call. Close with the
sentence the document carries: this is generated from the model, and whether a system
is correctly classified and its obligations met is a decision for the people
accountable for it.
