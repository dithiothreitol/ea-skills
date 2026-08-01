---
name: ea-validate
description: Run and interpret the deterministic EA model validation gate. Use when asked to check, validate, review or lint an architecture model, when a model build fails, before promoting content from staging to approved, or when investigating ArchiMate relationship errors, provenance failures or model quality findings.
---

# Validating the model

```bash
python -m easkills validate --root <repo> --zone approved     # default zone
python -m easkills validate --root <repo> --zone staging
python -m easkills validate --root <repo> --json report.json  # machine-readable
python -m easkills validate --root <repo> --strict            # warnings fail too
```

Exit code 0 means no errors; 1 means errors (or, under `--strict`, warnings). The
compiler refuses to run on a model with errors, so this gate is what stands between a
proposal and a published model.

Zone semantics: `staging` validates as an **overlay on approved** -- staging is a
proposed delta, so its relationships may reference approved elements and a same-id
concept is an update proposal. The promotion gate (`python -m easkills promote
--dry-run`) validates the merged result by approved-zone standards instead; content
that merely warns in staging can block there (ownership, review dates).

The full rule catalogue with severities is in `docs/RULES.md`. Read it rather than
guessing what a code means.

## How to work a failing report

Fix in this order -- earlier layers cause spurious findings in later ones:

1. `SCHEMA*` -- structural problems. A file that does not parse produces no concepts, so
   everything downstream looks empty.
2. `ID*` / `REF*` -- identifiers and references. A dangling endpoint suppresses the
   semantic check for that relationship, so `REL001` may be hiding behind `REF001`.
3. `PROV*` -- traceability.
4. `GOV*` -- ownership and review metadata.
5. `REL*`, `NAME*`, `SMELL*` -- semantics and quality.

**Cap the repair loop at three iterations.** Beyond three passes, fixes stop converging;
what follows is invented remedies and churn. If findings survive three attempts, stop and
report precisely what is unresolved, which rule fires, and what you think the underlying
modelling question is. An escalated open question is a useful outcome; a model bludgeoned
into passing is not.

## Interpreting the findings that matter

**`REL001` -- relationship not permitted.** The ArchiMate 3.2 matrix has spoken; it is
vendored from Archi's own rule table, not recalled from memory. The message lists what is
permitted between those two element types, and says explicitly when the relationship is
legal in the *opposite* direction, which is the usual cause. Two honest fixes: swap the
endpoints, or pick a permitted type. A third, sometimes correct, fix: the element types
are wrong -- if you find yourself wanting `Node --Assignment--> ApplicationComponent`, the
model is missing an Artifact.

Never "fix" this by editing the oracle.

**`PROV003` -- quote not found.** Treat this as a factual error, not a formatting nit. It
means the model asserts a source says something it does not say. Either locate the real
sentence and quote it verbatim, or -- if the claim genuinely is not in the sources --
convert the concept to `assumed: true` with a rationale. Do not go looking for a different
document that happens to contain similar words.

**`PROV004` -- approximate match.** Someone paraphrased. Replace with the verbatim
sentence.

**`ORACLE001` -- oracle drift.** A vendored rule file no longer matches its pinned hash.
Do not re-pin to make it green. Find out what changed: `git diff oracle/`. Re-pinning
(`python -m easkills pin-oracle`) is correct only when the change is a deliberate,
reviewed oracle update -- for example moving to a newer Archi revision.

**`GOV001` / `GOV002` in `approved`.** Ownership is not paperwork; unowned content is the
documented mechanism by which EA repositories rot. Find the accountable team, do not
invent an address.

**`SMELL001` -- isolated element.** Usually one of three real things: the element is
genuinely unused and should be retired, its dependencies were never captured (go back to
the sources), or it was modelled speculatively and should not exist.

**`REL002` -- structural cycle.** Composition and aggregation express containment;
containment cannot be circular. Something in that chain is a different relationship --
often serving, association or flow.

## Before promoting staging to approved

Run `python -m easkills promote --root <repo> --dry-run` -- it validates the merged
result by approved-zone standards, which is the actual bar. Confirm: zero errors,
`GOV001`/`GOV002` resolved (warnings in staging, errors at the gate), every `PROV006`
assumption either confirmed into evidence or consciously accepted, and every warning
either fixed or explained. The promotion itself is the `ea-approve` skill's job and
requires an explicit human decision.

Then compile, because passing validation and producing an openable model are different
claims:

```bash
python -m easkills compile --root <repo> --zone approved
```

## Reporting back

Lead with the verdict and the counts, then the findings that need a human decision --
grouped by underlying cause rather than listed rule by rule. Ten `SMELL001` warnings from
one unfinished modelling session are one finding, not ten. State clearly what you fixed,
what you could not, and what you deliberately left. Do not describe a model as validated
when warnings remain unexplained.
