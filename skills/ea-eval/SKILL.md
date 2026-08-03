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

4. **Compare against the previous run**, not against perfection. Keep the JSON
   outputs; a skill change is acceptable when no category regresses and the target
   category improves. 100% on these small cases is expected for extraction of
   *stated* facts; judgement categories (element typing, relationship direction)
   are where honest variance lives.

## Discipline

* Run **every** case, not the one that flatters the change.
* Never edit gold to make a run pass. If you believe gold is wrong, that is a
  reviewed change with its own justification -- gold changes and skill changes never
  land together.
* Nondeterminism is data: run the changed pipeline twice; if scores differ, report
  the spread, not the better number.

## Reporting back

Per case: the category table, delta vs the previous run, gate status, and one
sentence on what the change was supposed to improve and whether it did. A regression
you accept knowingly must be named as such.
