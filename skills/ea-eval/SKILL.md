---
name: ea-eval
description: Regression-test the extraction and modelling skills against the golden set. Use after changing ea-intake, ea-model, ea-capability-map or their prompts/conventions, when asked how good the pipeline is, or before releasing skill changes. Scores a pipeline run against gold with precision/recall/F1.
---

# Evaluating the pipeline against the golden set

Skill quality is measured, not felt. The golden set (`eval/golden/`, plus
`eval/example/` as the largest case) pairs raw sources with the fact register and
model they *should* produce.

## Procedure

1. **Set up a scratch repository** containing only a case's inputs:

```bash
# copy ea.config.yaml and facts/sources/ from the case into <scratch>; nothing else
```

2. **Run the pipeline under test** over the scratch repo: `ea-intake` (chunk →
   extract → glean → entities → validate-facts), then the modelling skills, then
   promote to approved. Work as if the gold did not exist -- do not peek at the
   case's register or model; the evaluation is worthless if the answer leaked into
   the run.

3. **Score:**

```bash
python -m easkills score --root <scratch> --gold eval/golden/clinic --json run.json
```

Read the table with the failure modes in mind: **fact recall** falling means
extraction misses content (chunking or gleaning regressed); **element/relationship
precision** falling means invention; **relationship F1** is the historically weakest
number (the research reason this repository exists) -- watch it hardest. The
candidate's own gates run too: a run that matches gold but fails provenance
verification is fabrication that happens to be right, and counts as a failure.

**Read the item lists, not only the ratios.** Every category names what it did not
match: `unmatchedGold` is what the run missed, `unmatchedCandidate` is what it wrote
that gold does not support, and the half-credit lists name both sides of each
disagreement. A relationship credited half says *how* -- `derived DR4 via <element>`
means the run connected the same things through an intermediate element, which is a
granularity disagreement rather than a missing dependency. Diagnose from those lists;
reverse-engineering a number from two YAML trees is how three investigations were
spent before they existed.

4. **Compare against the previous run**, not against perfection. Keep the JSON
   outputs; a skill change is acceptable when no category regresses and the target
   category improves. 100% on these small cases is expected for extraction of
   *stated* facts; judgement categories (element typing, relationship direction)
   are where honest variance lives.

## Discipline

* Run **every** case, not the one that flatters the change.
* Never edit gold to make a run pass. Gold may be corrected when it breaks a rule the
  skills themselves state -- that happened once, and the register was atomized because
  `ea-intake` defines a fact as one atomic statement -- but never because a run
  disagreed with it. Gold changes and skill changes do not land together.
* Nondeterminism is data: run the changed pipeline twice; if scores differ, report
  the spread, not the better number. A median that moves inside a previously measured
  spread is not a finding.

## When an API key is available

Two harnesses automate the loop above, and neither is part of the push gate:

```bash
python eval/harness/run.py --all --runs 3        # scored against the golden set
python eval/harness/contracts.py --runs 3        # governance records vs their own rules
```

`run.py` measures five skills' prose (`ea-intake`; `ea-model` + `ea-capability-map`;
`ea-stakeholders` + `ea-views`) and fails when a median drops below the spread the
committed baseline measured. `contracts.py` gives `ea-adr` and `ea-dispensation` a
scenario and checks properties of the record produced -- there is no gold for a decision
record, but there are rules it must not break. `docs/SKILL-COVERAGE.md` says which
instrument covers which skill, and names the two that nothing mechanical covers.

## Reporting back

Per case: the category table, delta vs the previous run, gate status, and one
sentence on what the change was supposed to improve and whether it did. A regression
you accept knowingly must be named as such.
