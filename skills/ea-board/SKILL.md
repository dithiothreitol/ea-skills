---
name: ea-board
description: Prepare the Architecture Board agenda and minutes from the governance log and health reports. Use when asked to prepare, run or minute an architecture board / governance review meeting, or to summarise what needs architectural decision this period.
argument-hint: "[as-of YYYY-MM-DD]"
allowed-tools:
  - Bash(easkills diff *)
  - Bash(easkills maturity *)
  - Bash(easkills trend *)
  - Bash(easkills validate *)
  - Bash(easkills validate-gov *)
  - Bash(python -m easkills diff *)
  - Bash(python -m easkills maturity *)
  - Bash(python -m easkills trend *)
  - Bash(python -m easkills validate *)
  - Bash(python -m easkills validate-gov *)
---

# Architecture Board support

The board's agenda is not invented -- it is *read out of the repository*. Everything
that needs a human authority decision is already a finding, an expiring record, or
an open assumption.

## Building the agenda

Collect, in this order (the standing agenda):

1. **Expiring and expired dispensations** -- `easkills validate-gov`
   (`DISP003` errors, `DISP006` warnings). Each is a decision: renew (why is
   compliance still impossible?) or close (what changed?).
2. **Open assumptions** -- `PROV006` items from `easkills validate`; each
   either gets confirmed into evidence, accepted for another period (say so in the
   minutes), or removed.
3. **Compliance assessments since last board** -- `governance-log/compliance/`,
   leading with `non-conformant` verdicts and their follow-up state (`COMP003`
   flags the ones going nowhere).
4. **Proposed decisions** -- ADRs with `status: proposed` awaiting acceptance.
5. **Health movements** -- `easkills trend` over the committed KPI snapshots names
   what regressed since the last one (take today's with `kpi --as-of <date>
   --snapshot` first and commit it with the minutes); `easkills diff --ref <commit of
   the last board>` lists what changed in the approved model since then, by field.
   Obsolescence exposure, unsupported capabilities, the review queue by owner.
   For a roadmap item, `easkills diff --plateau <from> <to>` states what the target
   state changes -- what enters, what leaves, and the gap that closes it.
6. **Rationalization candidates** -- `debt` items of kind `rationalization-candidate`,
   `overlapping-applications` and `duplicate-service`. Each is a board item precisely
   because the tool cannot decide it: overlap is either portfolio drift or *bought
   redundancy*, and only a human knows which. The decision the board makes is one of
   three, and all three end in a record: consolidate (which system wins, and who funds
   the migration), **keep both on purpose** -- which means an ADR naming the reason, so
   the finding stops coming back every quarter -- or split the capability, because two
   realizers can also mean the map is drawn too coarse. Bring the realizers' TIME
   dispositions to the table; `debt` prints them next to each candidate for this reason.
   An overlap carried unrecorded from one board to the next is the finding, not the
   overlap.
7. **Service performance** -- the `kpi` Service line: SLA breaches (`REQ006`) each
   need a disposition (fulfil, decline, renegotiate the promise), offerings nobody
   requests are candidates for retirement, and repeated informal asks are a missing
   catalog entry.
8. **Pending promotions** -- staged content whose review is stuck
   (`promote --dry-run` shows what is ready).

For each item, prepare the *decision to be made*, not just the topic: "renew
disp-onprem-legacy for 6 months or fund the migration" is an agenda item;
"discuss on-premise hosting" is not.

## The maturity table as a board artifact

`easkills maturity --as-of <date>` produces the one slide a board actually
acts on — provided you bring it whole. **Never reduce it to a single figure**, and
never present a level without the items blocking the next one: a level is a
description, the blockers are the agenda. Two dimensions moving in opposite directions
is the interesting case and an average would erase it.

Bring it quarterly, against your own previous run. A `not measurable` row is a
resourcing question ("we own no reference model"), not a bad score — and it is the one
row where the fix is a decision the board can take in the room.

## Minutes

Minutes are the records they change, plus a summary. Every board outcome lands as a
concrete edit in the same commit series: an accepted ADR (`status: accepted`), a
renewed/closed dispensation, a confirmed assumption (evidence added, `assumed`
removed) or its conscious re-acceptance, an updated `lastReviewed`. A written
summary (`governance-log/board-YYYY-MM-DD.md`) lists attendees, decisions taken and
who owns each follow-up -- but the summary *points at records*; it never contains
governance that exists nowhere else.

## Reporting back

The agenda as a numbered list of decisions-to-make with their evidence, anything
that could not be prepared for lack of an owner or record, and -- after the board --
the commit(s) carrying the outcomes.
