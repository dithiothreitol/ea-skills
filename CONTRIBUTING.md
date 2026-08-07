# Contributing to ea-skills

Thanks for considering a contribution. The conventions here are strict but few, and
almost all of them are enforced by a test rather than a review comment — if the suite
is green and the gates pass, you are most of the way to merged.

## Development setup

```bash
git clone https://github.com/dithiothreitol/ea-skills.git && cd ea-skills
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt    # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # POSIX

.venv/Scripts/python -m pytest tests -q          # the suite, ~20 s
.venv/Scripts/python -m easkills oracle-info     # oracle version + pin status
```

Python ≥ 3.11; CI runs the suite on 3.11/3.12/3.13 across Linux and Windows. Three
runtime dependencies (`pyyaml`, `jsonschema`, `lxml`) — adding a fourth needs a strong
argument in the PR description; GPL-licensed dependencies and anything that fetches
from the network at runtime are rejected on principle (see
[BLUEPRINT AD-05](docs/BLUEPRINT.md)).

The tooling is used from a clone (`python -m easkills …`): the oracle and the generated
schemas are repository data, so there is no wheel to install and no PyPI release.

## Measuring a change to a skill

The gate below proves the *core*. It cannot prove the skills, which are prose an agent
follows -- so a change to `skills/*/SKILL.md` is measured instead:

```bash
pip install -r requirements-eval.txt
export ANTHROPIC_API_KEY=...          # or .env, which is gitignored
python eval/harness/run.py --all --runs 3      # scored against the golden set
python eval/harness/contracts.py --runs 3      # governance records against their own rules
```

The first runs the skills blind against the golden cases and compares the result to
`eval/harness/baseline.json`, failing when a median drops below the spread the baseline
itself measured. The second gives `ea-adr` and `ea-dispensation` a scenario and checks
deterministic properties of the record they produce. Both call an API, so neither is in the
gate: see [`eval/harness/README.md`](eval/harness/README.md) for what the numbers mean, and
[`docs/SKILL-COVERAGE.md`](docs/SKILL-COVERAGE.md) for which skills they cover and which
nothing does.

Their *logic* is in the gate even though their runs are not:
`tests/test_contract_harness.py` proves each contract passes a hand-written reference answer
and fails the mutation it exists to catch, and `tests/test_harness_quarantine.py` pins the
measured-skill list to the README and keeps the network out of `easkills/`.

## Run the full gate before pushing

Every `easkills` invocation CI runs is in this block, and a test
(`test_contributing_pre_push_gate_mirrors_ci`) fails if the two ever drift — so a green
run here predicts a green CI:

```bash
python -m easkills oracle-info
python -m pytest tests -q
python -m easkills validate       --root eval/example --strict
python -m easkills validate-facts --root eval/example --strict
python -m easkills validate-gov   --root eval/example --strict
python -m easkills coverage       --root eval/example --min-coverage 100
python -m easkills readiness      --root eval/example --strict
python -m easkills align          --root eval/example --strict
python -m easkills dora-register  --root eval/fixtures/finco --as-of 2026-07-30 --strict
python -m easkills propose --root eval/example --from align --as-of 2026-07-30 --dry-run
python -m easkills propose --root eval/example --from readiness --as-of 2026-07-30 --dry-run
python -m easkills propose --root eval/example --from overlap --as-of 2026-07-30 --dry-run
python -m easkills compile        --root eval/example
python -m easkills docs           --root eval/example && git diff --exit-code eval/example/docs
python -m easkills conformance    --root eval/example --strict --as-of 2026-07-30
python -m easkills validate       --root eval/golden/clinic --strict
python -m easkills validate-facts --root eval/golden/clinic --strict
python -m easkills score --root eval/golden/clinic --gold eval/golden/clinic --min-f1 100
python -m easkills validate       --root eval/golden/contested --strict
python -m easkills validate-facts --root eval/golden/contested --strict
python -m easkills coverage       --root eval/golden/contested --min-coverage 100
python -m easkills score --root eval/golden/contested --gold eval/golden/contested --min-f1 100
python -m easkills score --root eval/example --gold eval/example --min-f1 100
python -m easkills check --root eval/example --repo eval/fixtures/consumer-clean --scope app-order-portal --as-of 2026-07-30 --strict
python -m easkills check --root eval/example --repo eval/fixtures/consumer --scope app-order-portal --as-of 2026-07-30   # must FAIL (exit 1)
python -m easkills validate       --root eval/fixtures/broken   # must FAIL (exit 1)
python -m easkills validate-facts --root eval/fixtures/broken   # must FAIL (exit 1)
python -m easkills validate-gov   --root eval/fixtures/broken   # must FAIL (exit 1)
python -m easkills align          --root eval/fixtures/broken   # must FAIL (exit 1)
python -m easkills dora-register  --root eval/fixtures/finco-broken --as-of 2026-07-30   # must FAIL (exit 1)
```

## The conventions that are actually load-bearing

**1. Every new validator rule ships as a triple.** A rule without proof it fires is
decoration, so the test suite enforces the pattern:

- the check itself (in `easkills/validate.py`, `facts.py` or `govern.py`);
- a case in `eval/fixtures/broken/` that violates it (annotated with the rule code) —
  including the reference packs under `eval/fixtures/broken/reference/`, one per `ALN`
  failure mode, each with its own valid `SHA256SUMS` so the pack under test is the one
  the rule is about;
- a row in [`docs/RULES.md`](docs/RULES.md) and an entry in the parametrized
  expected-codes list in the matching test module.

**2. Generated artifacts regenerate in the same commit.** Every schema under `schema/`
(`python -m easkills gen-schema` — all twelve are freshness-tested) and the example's
generated documentation (`python -m easkills docs --root eval/example`, i.e.
`eval/example/docs/`) are committed *and* freshness-checked — a stale artifact fails
CI, so regenerate alongside the change that invalidated it.

**3. Gold's *authored* content never changes with skill changes.** The golden set
(`eval/golden/`, `eval/example/`) is the measuring stick; a commit that moves both the
stick and the thing being measured proves nothing. If gold is wrong, fix it in its own
PR with its own justification. The one carve-out is convention 2: `eval/example/docs/`
is *generated* output, so a renderer or docgen change regenerates it in the same
commit — that is the freshness check working, not a gold edit.

**4. The worked example stays at zero findings, warnings included.** It is the
documented "0 errors, 0 warnings" claim, gated with `--strict` in CI. If your change
makes the example warn, either the example needs a legitimate update or your rule is
too noisy — decide which, explicitly.

**5. Never edit the oracle to make something pass.** `oracle/` is vendored,
hash-pinned primary-source data. Re-pinning (`pin-oracle`) is only for deliberate,
reviewed upgrades (e.g. a newer Archi revision), never for silencing `ORACLE001`.

**6. Determinism is a feature.** Outputs are byte-stable: same input, same bytes.
Write generated files with `newline="\n"`; no wall-clock timestamps in artifacts
(dates derive from model content); stable sort orders everywhere. There are tests
that will catch you.

**7. Colour is display, never data.** Terminal styling goes through `easkills/ui.py`
and must degrade to the exact plain text in pipes and CI. Never branch logic on
whether styling is active.

## Adding or changing a skill

Skills live in `skills/<name>/SKILL.md` — frontmatter (`name`, `description` with
concrete triggers) plus instructions. The house style: non-negotiables first, then
procedure, then "reporting back". A skill instructs judgement and defers proof to the
CLI gates; a skill that asks the model to recall ArchiMate semantics from memory will
be rejected — that is what the oracle is for.

If the change affects extraction or modelling quality, run the golden-set evaluation
(see [`eval/golden/README.md`](eval/golden/README.md)) and put the before/after score
table in the PR.

## Commit and PR style

- One logical change per commit; imperative-ish summary line, body explains *why*.
- PRs fill the template checklist — it mirrors the conventions above.
- CI must be green. A red negative-fixture step means the validator stopped catching
  violations — that is the highest-severity failure this repo has.

## Where to start

Good first contributions: a new EA-smell as a debt-register query, a golden case that
exercises something the set does not (a contradiction between sources, a messier
document format), or a rule from the "Not yet implemented" section of
[`docs/RULES.md`](docs/RULES.md). Open an issue first for anything that touches the
DSL or the oracle.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Be excellent to
each other; argue about evidence, not people.
