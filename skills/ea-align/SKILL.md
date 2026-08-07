---
name: ea-align
description: Measure the model against a reference architecture or industry blueprint and record the result. Use when asked whether a layer or the model is "complete" or "done", for a gap analysis against a reference model (BIAN, APQC PCF, eTOM, ACORD, NIST CSF, an internal capability standard), when asked what is missing compared to industry practice, or when maintaining reference/<name>/mappings.yaml. Also use before answering "is our capability map finished?" -- that question has no answer without a yardstick.
---

# Aligning the model to a reference architecture

"Is this layer done?" is not answerable from inside the model. Two yardsticks exist here,
and they answer different questions:

* `python -m easkills coverage` -- **did we model what we were told**. Source statements
  no fact cites. Complete against one conversation.
* `python -m easkills align` -- **did we model what a business like this has**. Reference
  nodes no element answers. Complete against an industry blueprint.

A model can score 100% on the first and still have no invoicing capability, because
nobody mentioned invoicing. That is exactly the hole this skill fills.

## Non-negotiables

1. **Never transcribe a licensed taxonomy.** BIAN, APQC PCF, eTOM, ACORD, TOGAF's TRM are
   licensed works. If the organisation has not licensed one, it does not have it, and you
   do not have it either. Writing out "the BIAN service domains" from memory is two
   failures at once: a licence breach, and fabrication that nobody can audit — an
   invented node is indistinguishable from a real one to every later reader, and it will
   be used to justify investment. Ask for an export from the licensed copy, or use an
   openly licensed pack (`references/` in the ea-skills repository ships NIST CSF 2.0,
   public domain). If neither exists, **say so and stop** — an invented yardstick is
   worse than none, because it measures.
2. **Never author `model.yaml`; never edit a pinned pack.** The taxonomy is hash-pinned
   data (`ALN001`). If `align` refuses a pack, the fix is finding out who changed it, not
   `pin-reference`. Re-pinning to make a report green is the reference-model equivalent
   of editing the oracle.
3. **`mappings.yaml` is the only file you write.** One entry per node.
4. **Out-of-scope always carries a rationale.** No exceptions, and none needed: if you
   cannot say why something is out of scope, it is not out of scope — it is a gap you
   have not thought about yet.
5. **Report gaps as gaps.** Do not close a gap by mapping a loosely related element to
   make a number move. The number is not the deliverable; the named list is.

## Choosing a reference

Ask what the organisation **actually licensed and actually uses**, not what looks
impressive in a report. A BIAN mapping at a food wholesaler is theatre; an internal
capability standard that three business units already argue in terms of is worth ten of
them. Order of preference:

1. A reference the organisation already uses in planning (even a spreadsheet).
2. An openly licensed one that fits the domain (NIST CSF 2.0 for security governance).
3. A licensed industry model the organisation holds, exported from its own copy.
4. Nothing. Say the model has no reference yardstick, and that `coverage` is the only one
   available. This is a legitimate answer, and it is the right one more often than an
   architect wants to admit.

Multiple packs are fine and often correct: a capability reference *and* NIST CSF answer
different questions about the same model. `align` reports each separately.

## Mapping is judgement, recorded

Every entry is a claim someone can contest, so write it so they can:

```yaml
mappings:
  - ref: wc-invoicing
    status: partial
    elements: [app-erp-core]
    note: >
      The ERP core does the invoicing and the sources say so, but no capability is
      modelled for it and receivables are not modelled at all -- so the application is
      recorded and the capability line stays half-answered on purpose.
```

The `note` is where the work is. `status: partial` without one is a shrug in YAML: the
next reader cannot tell whether the grain is wrong, a sub-capability is missing, or you
were unsure. **Say what is missing, and the note becomes the requirement.**

Grain rules that keep mappings honest:

* **`covered` means a reader of the model could find this.** Usually a capability, often
  a capability plus the applications realizing it. If the only thing you can name is an
  application, that is `partial` — the reference asked about a business capability and you
  answered with a system.
* **Map to what answers the node, not to everything nearby.** A list of six elements
  where one is load-bearing tells the next reader nothing.
* **One node, one entry** (`ALN006`). If you want to say two contradictory things, the
  disagreement belongs in an ADR, not in two mapping entries.
* **Never map a node to an element you are about to propose.** A staging element does not
  count (`ALN007`); `--zone staging` is how you show what promotion *would* close.

## Out-of-scope is a decision, not a filter

`out-of-scope` is how an architecture says "we know, and we chose". It needs three things
in the rationale: *what* is out, *why*, and *who or what settles it*.

```yaml
  - ref: wc-transport
    status: out-of-scope
    rationale: >
      Deliveries are contracted to a third-party carrier; Aurora Foods operates no
      transport capability of its own. Recorded as a decision so the next reader can tell
      an outsourced capability from a forgotten one.
```

Legitimate reasons: outsourced; owned by another architecture with its own description;
outside the declared scope of this description; a business the organisation is not in.
Illegitimate: "not modelled yet" (that is a gap), "no time" (a gap), "not important" (a
gap with an opinion attached).

An exclusion at a **branch** inherits down its whole subtree, so one recorded decision can
account for a whole domain — that is the intended way to exclude an area, and much better
than nine copies of the same rationale. A coverage claim never inherits: covering a branch
is a claim about every leaf under it, and those are earned one at a time.

If an exclusion is contentious or expensive, it is an ADR (`ea-adr`) and the rationale
cites it. Scope decisions get relitigated; a decision record survives the relitigating,
a YAML comment does not.

## Method

1. **Check what exists.** `python -m easkills align --root <repo>`. No packs? Go back to
   *Choosing a reference*; this is the whole conversation until one exists.
2. **Read the gaps before writing anything.** `ALN004` names each one. Sort them
   yourself into: covered but unmapped (mapping work), genuinely missing from the model
   (modelling work), out of scope (decision work), missing from the *business*
   (a finding for the board, not for you).
3. **Write the mappings you can evidence**, hardest first. The nodes you argue about are
   the ones the notes matter for.
4. **Record the exclusions**, each with a rationale that names its reason.
5. **Re-run and read the branch rollup.** A domain at 20% is a report line; a domain at
   20% *with three of its five leaves out of scope* is a different conversation.
6. **Route what is left.**
   * A gap the sources never mentioned → a clarification question (`ea-intake`).
   * A gap the model should hold and does not → modelling work (`ea-model`,
     `ea-capability-map`).
   * A gap in the business itself → the board agenda (`ea-board`), never a mapping edit.
   * A contested exclusion → an ADR (`ea-adr`).
7. **Gate only a number you would defend.** `--strict` (gaps fail) or `--min-coverage
   <pct>` in CI is right for a repository that claims completeness. It is wrong on day
   one: a freshly dropped pack is 100% gaps, and a gate that is red from the first commit
   gets disabled instead of fixed.

## Reading the report honestly

* **Coverage is not quality.** 90% against a reference means the model names the things
  the reference names. It says nothing about whether they are named well, owned, or true.
* **Only leaf nodes are scored**, `partial` counts half, and out-of-scope nodes leave the
  denominator entirely. So a repository can raise its percentage by excluding things —
  which is why every exclusion needs a rationale a human will read, and why the report
  prints the out-of-scope count next to the percentage rather than hiding it.
* **The unanchored list is information, not a defect.** Local elements the reference does
  not anchor are usually the business doing something the blueprint never heard of. A long
  unanchored list next to a high coverage number is a sign the reference is the wrong one
  — not a sign that the model is wrong.
* **Two references disagreeing is normal.** They partition the world differently. Do not
  reconcile them; report both.

## Reporting back

Say, in this order: which references were aligned and why those; the coverage per pack and
per branch, with the out-of-scope count beside it; the **named** gaps sorted by the routing
in step 6; every exclusion recorded in this pass with its rationale in one line; and what
you could not decide. A percentage on its own is the one output of this skill that is
worse than silence — it invites a target, and coverage of a reference nobody chose
carefully is a target worth nothing.
