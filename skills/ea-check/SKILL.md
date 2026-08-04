---
name: ea-check
description: Check a product/service repository against the architecture standards its system claims to follow. Use when asked "are we compliant?", "does this repo break any standard?", when adding or upgrading a dependency, or when wiring an EA gate into a team's CI. Runs in the consuming repository, not in the EA repository.
---

# ea-check — compliance lint inside a consuming repository

This is the half of the governance story that runs *outside* the EA repository. The
model knows what a system is supposed to be built on and whether an exception was
filed; the product repository knows what it actually declares. `check` joins the two.

## Non-negotiables

- **The command decides, you explain.** `python -m easkills check --root <ea-repo>
  --repo . --scope <element-id>` produces the findings. Never assess compliance by
  reading a manifest yourself and reasoning about standards — that is exactly the
  judgement this tooling exists to replace.
- **Never invent a correspondence.** A dependency implements a standard only when that
  standard's `detect:` rules say so. If a team believes a library evidences a standard,
  the fix is a `detect:` rule in the SIB entry (a governed change in the EA repository),
  never a claim in a report.
- **`CHK002` is not a bug to route around.** Three honest exits: migrate off the
  retired standard, file a time-bounded dispensation (`ea-dispensation`), or change the
  standard's lifecycle if it should not have been retired (`ea-standards-base`).
  Suppressing the check, pinning an old EA repository, or dropping `--strict` are not
  exits; they are how governance becomes theatre.
- **The consuming repository maintains no manifest.** `--scope` is the entire
  convention. If you find yourself proposing a mapping file in the product repo, stop:
  that is a deferred decision (AD-09), not an implementation detail.

## Procedure

1. **Establish the scope.** Which element in `model/approved/` *is* this repository?
   Usually an `ApplicationComponent`. If nothing matches, the system is unmodelled —
   route to `ea-model` (and say so; do not check against an approximate neighbour).
2. **Run the check** with `--as-of` pinned in CI configurations so results are
   reproducible, and `--json` when another tool consumes the output.
3. **Read the findings by severity**, not by count:
   - `CHK002` (error): retired standard, no waiver. Propose the three exits above with
     a recommendation, not a menu — usually migration if a successor exists.
   - `CHK003` (warning): deprecated. Ask for a migration date, and offer to record it.
   - `CHK004` (info): covered by a waiver. Report the **expiry** prominently: it is a
     deadline, and after it the same code becomes an error.
   - `CHK005` (warning): the model claims a standard this repository does not evidence.
     Either the model is wrong (route to `ea-model`/`ea-delta-ingest`) or the repository
     drifted off the standard. Say which you believe and why.
   - `CHK006` (info): the repository uses a governed standard the model does not record.
     This is intake material — route to `ea-delta-ingest`, do not "fix" it locally.
   - `CHK000`/`CHK007`: the check could not see what it needed. Never report these as
     compliance; report them as an unchecked repository.
4. **Wire it in** when asked: a CI step calling `check` with `--scope` and `--as-of`,
   failing on exit 1. Warnings should fail (`--strict`) only if the team agrees to it —
   pushing `--strict` on someone else's build without consent is how a governance tool
   gets removed.

## Reporting back

Lead with the verdict and the deadline: how many errors, and the earliest dispensation
expiry that turns into one. Then the findings, grouped by exit route rather than by
rule code — the reader is a product team deciding what to do this sprint, not an
auditor. If the check proved nothing (`CHK007`, or no `detect:` rules matched anything),
say that plainly: an empty report is not a clean bill of health.
