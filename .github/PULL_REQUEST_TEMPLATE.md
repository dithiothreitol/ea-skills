## What this changes and why

<!-- One paragraph. Link the issue if there is one. -->

## Checklist

The conventions below are enforced by tests/CI — this list is here so the round-trip
is short (details: [CONTRIBUTING.md](../CONTRIBUTING.md)):

- [ ] `python -m pytest tests -q` is green locally
- [ ] New/changed validator rule ships as a **triple**: check + `eval/fixtures/broken/` case + `docs/RULES.md` row (+ expected-codes test entry)
- [ ] Generated artifacts regenerated in this PR if invalidated: `gen-schema`, `docs --root eval/example`
- [ ] Worked example still at **zero findings** under `--strict` (all three validators)
- [ ] Gold's *authored* content untouched (`eval/golden/**`, `eval/example/**` — **except** generated `eval/example/docs/`, which regenerates per the checkbox above) — or this PR changes *only* gold, with justification
- [ ] No new runtime dependency / no network at runtime / no oracle edits
- [ ] Outputs remain byte-stable (no wall-clock timestamps, `newline="\n"`, stable ordering)
- [ ] Skill changes: golden-set `score` before/after table included below (if extraction/modelling quality is affected)

## Score impact (skill changes only)

<!-- paste `python -m easkills score ... --json` summaries for each golden case, or "n/a" -->
