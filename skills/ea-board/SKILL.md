---
name: ea-board
description: Prepare the Architecture Board agenda and minutes from the governance log and health reports. Use when asked to prepare, run or minute an architecture board / governance review meeting, or to summarise what needs architectural decision this period.
---

# Architecture Board support

The board's agenda is not invented -- it is *read out of the repository*. Everything
that needs a human authority decision is already a finding, an expiring record, or
an open assumption.

## Building the agenda

Collect, in this order (the standing agenda):

1. **Expiring and expired dispensations** -- `python -m easkills validate-gov`
   (`DISP003` errors, `DISP006` warnings). Each is a decision: renew (why is
   compliance still impossible?) or close (what changed?).
2. **Open assumptions** -- `PROV006` items from `python -m easkills validate`; each
   either gets confirmed into evidence, accepted for another period (say so in the
   minutes), or removed.
3. **Compliance assessments since last board** -- `governance-log/compliance/`,
   leading with `non-conformant` verdicts and their follow-up state (`COMP003`
   flags the ones going nowhere).
4. **Proposed decisions** -- ADRs with `status: proposed` awaiting acceptance.
5. **Health movements** -- `kpi`/`debt`/`staleness` deltas since the last run:
   obsolescence exposure, unsupported capabilities, the review queue by owner.
6. **Service performance** -- the `kpi` Service line: SLA breaches (`REQ006`) each
   need a disposition (fulfil, decline, renegotiate the promise), offerings nobody
   requests are candidates for retirement, and repeated informal asks are a missing
   catalog entry.
7. **Pending promotions** -- staged content whose review is stuck
   (`promote --dry-run` shows what is ready).

For each item, prepare the *decision to be made*, not just the topic: "renew
disp-onprem-legacy for 6 months or fund the migration" is an agenda item;
"discuss on-premise hosting" is not.

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
