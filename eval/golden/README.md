# The golden set

Each directory here is a complete, deliberately small model repository: raw sources,
the gold fact register, and the gold approved model -- all passing every validator
with zero findings. The worked example (`eval/example/`) doubles as the largest
golden case.

## What it is for

Skill changes are evaluated, not eyeballed. To regression-test the extraction and
modelling skills:

1. Copy a case's `facts/sources/` (and `ea.config.yaml`) into a scratch repository.
2. Run the pipeline skills over it (`ea-intake`, then the modelling skills, then
   promotion) so the scratch repository gains a fact register and an approved model.
3. Score the result:

```bash
python -m easkills score --root <scratch-repo> --gold eval/golden/clinic
python -m easkills score --root <scratch-repo> --gold eval/example
```

Precision/recall/F1 per category -- entities (term-set overlap), facts
(normalized-statement similarity ≥ 0.85), elements (ArchiMate type + normalized
name), relationships (type + matched endpoints) -- plus the candidate's own
validation gates, because matching gold while failing provenance verification is a
fabrication that happens to be right. `--min-f1 <pct>` turns the score into a gate.

## Adding a case

A case earns its place by exercising something the existing set does not (a new
layer, a contradiction between sources, a messier document format). Keep it small
enough to diff by eye, make every quote verbatim, and add it to the CI steps that
validate golden cases -- gold that does not pass its own gates is not gold.
