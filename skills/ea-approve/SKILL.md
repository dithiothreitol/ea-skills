---
name: ea-approve
description: Promote reviewed model content from staging to approved -- the only write path into the approved zone. Use when a human asks to approve, promote, accept or publish staged model changes, or after a review session concludes staged content is ready. Never use on your own initiative; promotion asserts human sign-off.
---

# Promoting staging to approved

`model/approved/` is human-signed content: downstream governance, reporting and
context extracts read only from it. Promotion is the act of a person putting their
name on a proposal. Your job is to make that act safe and informed -- never to
perform it unprompted.

## The one rule that is not negotiable

**Do not promote unless the human has explicitly asked for this promotion, now.**
"The validator passes" is not an instruction to promote. If you finished modelling
work and staging is clean, report that it is ready and stop. When in doubt whether
an instruction covers promotion, ask.

## Procedure

1. **Dry-run the gate:**

```bash
python -m easkills promote --root <repo> --dry-run
```

The gate validates approved + staging *as if already merged, by approved-zone
standards*: ownership and review dates become errors, every semantic rule is on.
This is stricter than a plain staging validation -- content that warns in staging
blocks here, by design.

2. **Present what would change.** List the files that would move, the concepts they
   add or update (a same-path file replaces the approved one -- that is the update
   flow), and every open `PROV006` assumption riding along. Assumptions do not block
   promotion, but promoting one means the human accepts it -- say so explicitly
   rather than letting it slide through in a file list.

3. **On explicit confirmation, promote:**

```bash
python -m easkills promote --root <repo>                          # everything
python -m easkills promote --root <repo> --file model/staging/x.yaml  # selected files
```

Partial promotion is normal: promote what was reviewed, leave the rest staged.

4. **Commit immediately.** The move is a plain file rename; the git commit is the
   approval record (who, when, what). Suggest a message naming what was approved and
   on whose decision. Do not batch unrelated changes into it.

## When the gate blocks

The usual causes, in order of frequency:

* `GOV001`/`GOV002` -- staged content missing `owner` or `lastReviewed`. These were
  warnings in staging and are errors now. Get the real owner from the human; never
  invent an address to make the gate pass.
* `PROV*` -- evidence problems that were tolerated during drafting. Fix them in
  staging, re-run the dry-run.
* Semantic errors surfacing only in the merged picture (a staged relationship whose
  approved endpoint was retyped, a duplicate name against approved content).

Fix in staging and re-run. **Never edit `model/approved/` directly to resolve a
promotion conflict** -- if approved content is wrong, that correction is itself a
staged proposal with its own review.

## Reporting back

State what was promoted (files and concepts), what was deliberately left in staging
and why, which assumptions the human accepted by promoting, and the commit that
records it. If you were asked to promote and refused, say exactly which rule blocked
it and what evidence is missing.
