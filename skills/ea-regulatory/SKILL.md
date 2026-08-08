---
name: ea-regulatory
description: Map regulatory controls onto the architecture and maintain the DORA Register of Information. Use for control-framework gap analysis (NIST CSF, KNF Rekomendacja D and similar), ICT third-party risk, DORA register upkeep, regulatory scope questions, security-architecture coverage, or when asked which systems a regulation touches and what evidence exists. For the EU AI Act and AI risk, see ea-ai-governance.
---

# Regulatory controls and the DORA register

```bash
python -m easkills align --root <repo> --reference nist-csf-2.0   # control gaps, named
python -m easkills dora-register --root <repo> --as-of <date>     # the register + its own gaps
python -m easkills dora-register --root <repo> --as-of <date> --out docs/dora-register.md
```

The EU AI Act has its own register (`ai-act-register`) and its own skill —
[`ea-ai-governance`](../ea-ai-governance/SKILL.md). One element can be in both scopes at
once (`regulatoryScope: ai-act dora`); neither register drops it.

## Non-negotiables

* **This tooling generates; it does not attest.** The register's structure follows the
  shape the ESAs' implementing technical standards ask for. Its content comes from the
  model and nowhere else. No completeness against the official templates is claimed and
  no legal review has happened. Say that out loud every time you hand the document over
  — the generated file says it in its own header, and that header is not decoration to
  be trimmed.
* **Never mark an element in scope to make a report look complete**, and never mark one
  out of scope to make a finding go away. Scope is a fact about the element, decided by
  what the regulation says, and it is recorded next to the element where the next reader
  will find it.
* **A gap is disclosed, not closed by editing.** The register's last section lists every
  field the model could not fill, with element ids. Filling a field with a guess is
  worse than the gap — the gap is true.

## Controls are a reference overlay

A control framework is a taxonomy, so it uses the mechanism `ea-align` already
describes: a hash-pinned pack under `reference/<name>/` with nodes of `kind: control`,
plus a human-authored `mappings.yaml`. Nothing new to learn, and one consequence worth
stating: **a control gap is `ALN004`** — an unmapped control node, named. Out-of-scope
needs its mandatory rationale, exactly as it does for capabilities, and "this control
does not apply to us" is a sentence somebody has to sign.

NIST CSF 2.0 ships in [`references/`](../../references/) (public domain), and so does
**KNF Rekomendacja D (2013)** — the Polish supervisor's expectations for IT governance
and ICT security in banks, shipped as public law with each recommendation's statement
verbatim. Licensed frameworks stay in the adopter's repository under the adopter's
licence — see `template/reference/README.md`. Check the pack's `NOTICE.md` before you
rely on it:
verification state is stated there and in the library table, a pack labelled *structure not
yet verified* is a working draft rather than an authority, and a verified one is verified
against one dated edition — which a later edition of the framework silently invalidates.

## Security architecture, in the existing layers

There is no security layer in this model and none is missing: ArchiMate deliberately has
none, and everything a security architecture consists of already has a governed home
here. Use the homes; do not invent a parallel structure.

* **Posture is measured by control packs.** NIST CSF 2.0 (verified) and KNF
  Rekomendacja D for banks are the shipped yardsticks; an unexamined area is a named
  `ALN004` gap, and an exclusion is a signed rationale. Two packs partition the world
  differently on purpose — report each separately, never reconciled.
* **Security principles and requirements are motivation-layer elements** (`Principle`,
  `Requirement`, `Constraint`) bound to the elements they govern via `appliesTo` —
  checked by `MOT001`/`MOT002`, not left as a policy PDF nobody can trace.
* **Concrete security standards are SIB entries** — web-application security among them
  (see `ea-standards-base` for the pattern, including OWASP ASVS-derived standards and
  HA/failover tiers). Elements claim them with `standards:`, `ea-check` holds product
  repositories to the detectable ones, and retiring one turns every laggard into a
  named `STD002` failure.
* **Accepted security risk is a dispensation** with a mandatory expiry and a named
  grantor — never a deleted finding. It then surfaces by itself in the DORA register
  (`REG003`) and the AI inventory (`AIR003`).
* **The tooling's own security posture** is a different subject and lives in
  `SECURITY.md` at the repository root.

## Scope: what puts an element in the register

One property, on the element:

```yaml
properties:
  regulatoryScope: dora
  doraCriticality: critical        # critical | important | standard
  provider: PaySwitch AG       # the ICT third-party service provider
  contractRef: ctr-2023-payswitch
```

`regulatoryScope` is a closed enum on purpose. `DORA` or `dora ` as free text would
drop the element out of the register silently, and **under-inclusion is the failure
mode that matters** in a regulatory report — a missing row does not announce itself.
For scopes this tool does not generate a register for, use your own property key.

Scope lives on the element rather than in a config list for the same reason ownership
does: it moves with the element, it is greppable, and the commit that changed it shows
what changed. A list in `ea.config.yaml` is a second place to forget.

## The four rules

| Code | Severity | What it means when it fires |
|---|---|---|
| `REG001` | warning | In scope, no `doraCriticality`. The register cannot say how much depends on it. |
| `REG002` | error | Critical, with no `provider` or no `contractRef`. These are the first two fields a supervisor asks for. |
| `REG003` | info | A critical or important element under an **open dispensation**. Exposure to disclose, not a violation to fix. |
| `REG004` | warning | A register section is empty while in-scope content exists. Silence reads as "nothing to report". |

`REG003` is the one people misread. An open waiver is a legitimate internal governance
record; in a register it is a fact about the state of the estate on the date the
document is read. Do not close a dispensation to clear it, and do not leave it out. The
coupling is deliberate: `ea-dispensation` grants the waiver, and it surfaces here
without anyone having to remember to mention it.

## Keeping the register alive

* **Regenerate with `--as-of`, always.** Waiver expiry is date-dependent; a register
  with no date on it cannot be reproduced or compared to the last one.
* **Read the gap section first**, before the tables. It is the only part that tells you
  what the document does not know.
* **Concentration is a view, not a table.** The register lists providers; whether four
  critical services behind one provider is acceptable is an architecture judgement.
  Draw it (`ea-views`) and take it to the board (`ea-board`) — a table makes
  concentration easy to miss.
* **A new provider is an intake event.** When the register gains a row nobody
  recognises, the model changed before the paperwork did; route it through
  `ea-delta-ingest` and confirm the contract reference against a real contract.
* **Nothing in scope is a legitimate answer.** For an organisation DORA does not apply
  to, `dora-register` reports that no element is tagged and generates nothing. That is
  the correct output — and the wrong one for an organisation that simply has not tagged
  its ICT services yet. Know which of the two you are looking at.

## Reporting back

The register's headline numbers (in-scope elements, providers, contracts, critical
functions), then three lists that need a human: the fields the model could not fill with
their element ids, the open waivers on critical or important elements, and any provider
concentration worth a decision. Close with the sentence the document carries: this is
generated from the model, and the legal judgement belongs to whoever signs the filing.
