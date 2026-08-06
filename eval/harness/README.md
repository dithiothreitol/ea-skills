# The golden-set harness

```bash
pip install -r requirements-eval.txt
export ANTHROPIC_API_KEY=...        # or put it in .env, which is gitignored
python eval/harness/run.py --case clinic --runs 3
python eval/harness/run.py --all --runs 3 --baseline    # rewrite baseline.json
```

Runs the extraction and modelling skills against a golden case and scores the result,
so a change to skill *prose* stops being something we argue about and starts being
something we measure.

## What it does

A scratch repository is created holding **only** the case's `ea.config.yaml` and
`facts/sources/`. Gold's fact register and model never enter it — a leaked answer makes
the number meaningless, and a test asserts that the harness copies nothing else.

Then the pipeline the skills describe, driven by the model:

1. `chunk` (deterministic), then `ea-intake`'s prose → `facts/register/` + `entities.yaml`
2. `validate-facts` → repair → revalidate, **three iterations then stop** (the cap the
   skills prescribe, and the research they cite)
3. `ea-model` + `ea-capability-map` → `model/staging/` → `validate --zone staging` → same
   repair loop
4. `ea-stakeholders` + `ea-views` → the ISO 42010 apparatus → same gate, same repair loop
5. `promote` → `score --gold <case>` + `conformance` for the apparatus

Every gate is the real command, run as a subprocess exactly as a user would run it.

## What the number means, and what it does not

It measures **agreement with one gold repository**, which is a regression signal for the
skill text — not an absolute grade. A candidate that models at finer granularity than
gold scores low on precision while being defensible architecture; read the categories,
not the headline. Since 0.11.0 the score also **names** what it did not match, so reading
the categories no longer means diffing two YAML trees by hand.

It measures the prose of **5 of the 22 skills**, declared in `MEASURED_SKILLS` in
`run.py` and pinned to this file by a test:

| Phase | Skills | Judged by |
|---|---|---|
| intake | `ea-intake` | score against gold (facts, entities) |
| modelling | `ea-model`, `ea-capability-map` | score against gold (elements, relationships) |
| apparatus | `ea-stakeholders`, `ea-views` | **contract**: ISO 42010 conformance clauses |

The apparatus phase is judged differently on purpose. Gold holds no stakeholders, concerns
or views, and inventing them would turn the number into a similarity to one author's
documentation taste. What is checkable is whether the loop closes — concerns held by
someone, views governed by a viewpoint, every concern framed — so the measurement is the
`conformance` checklist the core already computes, reported and never gated. An unframed
concern is an honest finding about a repository, not a skill regression.

Everything else in `skills/` is unmeasured by this harness; `docs/SKILL-COVERAGE.md` says
which instrument covers which skill, and where nothing does.

It does **not** measure a host like Claude Code executing the same skills with its own
tools, planning and multi-turn behaviour. This harness scripts the loop; a real agent
decides it. Treat the two as different instruments: this one is repeatable and cheap,
the other is faithful and manual (the end-to-end runs recorded in BLUEPRINT §8a).

Runs use the API default temperature, so `--runs 3` is the default and the report shows
**min / median / max** per category. A single run tells you almost nothing about the
skills and quite a lot about that particular sample.

## Regression gate

`baseline.json` holds the committed spread — min, median and max per category. A plain run
compares against it and exits 1 when a median falls **below the baseline's own minimum**,
which is a move outside the variation the baseline itself measured. A median that falls but
stays inside that spread is printed as a *movement*, not a failure: with three runs at API
default temperature a three-point median move says nothing, and the first comparison duly
flagged one such (`contested/entities` 83% → 80%, baseline spread 77–83) beside a real one.
A gate that cries wolf gets ignored, which costs more than the noise it reports.

Rewrite the baseline with `--baseline` only when the new numbers are understood and
deliberate — the point of a baseline is that moving it is a decision. `--from-records`
rebuilds it from a saved `--out` file, so accepting a number never costs another run.

## Why it lives here and not in `easkills/`

The core is offline by design (SECURITY.md: "no network at runtime") and no check in it
consults a language model. This harness is the only code in the repository that calls
an API, so the separation is enforced structurally, not by convention:
`tests/test_harness_quarantine.py` fails if any core module imports an HTTP client or
this SDK, if the core imports the harness, or if the SDK reaches `requirements.txt`.

It is never part of the default gate. It costs tokens, it is non-deterministic, and a
gate that is both would be neither trustworthy nor affordable.

## The first baseline, and what it says (2026-08-06, claude-sonnet-5, 3 runs/case)

| Case | facts | entities | elements | relationships |
|---|---|---|---|---|
| `clinic` | 83% | 44% | 25% | **0%** |
| `contested` | 67% | 83% | 39% | **0%** |

All six runs passed their own gates, most with zero or one repair. Three findings, and
the difference between them matters:

**1. Extraction works; entity resolution under-delivers.** `ea-intake`'s entity step
says "one entry per real-world thing", and every example around it is an application.
The `clinic` runs produced three entities — all applications — where gold has six,
including an actor, an integration and a server. The alias table is what lets the
scorer see past vocabulary differences, so a thin table costs element matching too.

**2. The models are elaborate beyond their evidence.** 19–23 elements from a
seven-fact source, inventing services, processes and capabilities nothing states.
Element *recall* reaches 92%; *precision* sits at 25%. Gold is deliberately minimal, so
part of this is granularity rather than error — but "Current State — Manual Weekend
Planning" as a modelled element, from a source that states no plan, is not granularity.

**3. Relationships score 0% for a reason the number cannot show.** In the run with 92%
element recall, every gold relationship's endpoints were matched — and no relationship
matched, because the candidate connects those same elements *through intermediate
behaviour it invented*: `SchedPro → Weekend Run Planning` where gold has
`SchedPro → Dispatch`. Every gold edge is derivable from the candidate's chain; none is
present as a direct edge.

That last one is not a scoring bug and was checked before being reported. It is the
**derived-relationship gap** then listed in [RULES.md](../../docs/RULES.md) as not
implemented: ArchiMate's derivation rules (DR1–DR8) are exactly the machinery that would
say "gold's edge is this candidate's two-hop path". Read it as *"the candidate did not draw
the same edges"*, never as *"the candidate connected nothing"* — `rel-structural`, the
label-independent diagnostic, cascades the same way and cannot separate them either.

*(Since 0.11.0 those rules exist — `easkills/derive.py` — and this measured case is
literally an instance of DR4. A gold edge the candidate's model implies is now half a
match, with the rule and the abstracted-away element printed beside the number.)*

The first two are actionable against skill prose. The third is a measurement limit,
recorded rather than papered over — and rewriting the scorer a third time to make a
number look better would be exactly the wrong response to it.

## What the prose fixes did (same day, same harness)

`ea-intake`'s entity step now names the kinds of thing that get entries instead of
illustrating only applications; `ea-model` gained a *Granularity* rule against inserting
intermediate behaviour to make a picture look complete.

| Case | facts | entities | elements | relationships |
|---|---|---|---|---|
| `clinic` | 83% → **74%** | 44% → **71%** | 25% → **50%** | 0% → **25%** |
| `contested` | 67% → 67% | 83% → 80% | 39% → **50%** | 0% → 0% (max 12%) |

Elements doubled on both cases and relationships came off the floor on `clinic`. Two
numbers fell, and the gate flagged both — which is the point of having one:

- **`contested/entities` 83% → 80%** is noise. The baseline spread was 77–83, the new
  one 67–86; with three runs a 3-point median move says nothing.
- **`clinic/facts` 83% → 74%** is systematic (all three runs identical, both times) and
  worth understanding. The candidate now writes **ten** facts where gold has seven,
  because it splits gold's compound statements: gold has *"Patients book appointments
  through the online booking portal **or by calling the front desk**"* as one fact, the
  candidate as two. The scorer treats a split as a match on covered source ground but
  gives **half credit** on the statement, so nine partial credits drag F1 down.

That leaves an honest question pointing at gold rather than at the run: `ea-intake` says
a fact is **one atomic statement**, and gold's clinic register carries two compound ones.
The candidate is arguably following the skill more closely than gold does. Changing a
golden case is a separate decision from changing a skill, so it is recorded here and not
taken quietly — but it is the reason this baseline was accepted with a category lower
than before, which is exactly the kind of trade-off a baseline exists to make visible.

**That question was answered in the next release, in gold's favour of the run:** the two
compound facts were split into four atomic ones (`clinic` now has nine), and
`eval/golden/README.md` records the rule it establishes — a case may be corrected against a
rule the skills state, never against a run's output.

## The second baseline (2026-08-06, claude-sonnet-5, 3 runs/case, harness v2)

Three things changed at once, so read the table with the caveat that follows it: gold's
facts are atomic, the scorer credits derived relationships, and the modelling phase now
also reads `ea-capability-map`.

| Case | facts | entities | elements | relationships | apparatus |
|---|---|---|---|---|---|
| `clinic` | 74% → **87%** | 71% → 67% | 50% → 43% | 25% → 20% | 3 stakeholders, 3 concerns, 3 views; 7 ISO clauses pass |
| `contested` | 67% → 67% | 80% → 71% | 50% → **56%** | 0% → **11%** | 2 stakeholders, 3 concerns, 2 views; 7 ISO clauses pass |

All six runs green on their own gates; two needed one repair, none needed three.

**What is comparable, and what is not.** `facts` is: +13 points on `clinic`, exactly the
nine half credits the compound statements were costing. `relationships` on `contested` is:
0% → 11%, and the derivation rules are why — a `Serving` edge gold draws directly is now
recognised in a candidate's two-hop chain (`derived DR4 via <element>`), which is printed
beside the number. Everything touching **element counts is not comparable**: adding
`ea-capability-map` to the measured phase changed the prose the run reads, and the runs
duly produced a capability layer — three capabilities per `clinic` run, against a gold
model that has none. That is the whole of `clinic/elements` 50% → 43% and most of
`clinic/relationships` 25% → 20%, and the gate flagged the latter as a regression because
it fell below the old baseline's minimum.

**It was re-baselined rather than "fixed", and the reason is the honest one:** the harness
now measures a different, larger surface of prose, so the old numbers are not a yardstick
for the new ones. Moving a baseline because the instrument changed is legitimate; moving it
because the result was disappointing is not, and the difference has to be written down each
time — which is what this section is.

**The open question this leaves, pointing at gold again.** Three independent runs each
produced the same three capabilities from the clinic interview (appointment scheduling,
patient records, billing), and gold's `clinic` model has no Strategy layer at all — while
`ea-model` says to build the capability map **first** and treat it as the spine. Either the
runs are inventing a layer the source does not support, or the golden case contradicts the
method the skills teach. It is recorded here and **not** acted on in the same release that
measured it: the last time a question pointed at gold, answering it in the next release,
with the rule stated, is what kept the correction from looking like a number being tuned.

## Across model tiers (2026-08-06, `clinic`, 3 runs each, informational)

The baseline is defined for the default model; these runs answer a different question —
does the prose carry across tiers, or is it tuned to one?

| Model | facts | entities | elements | relationships | repair loops | tokens in/out |
|---|---|---|---|---|---|---|
| `claude-haiku-4-5` | 79% | 60% | **55%** | 9% | **two runs used all three** | 200k / 38k |
| `claude-sonnet-5` | **87%** | **67%** | 43% | 20% | at most one | 79k / 61k |
| `claude-opus-5` | 77% | 57% | 44% | **30%** | at most one | 90k / 57k |

Every run of every tier passed its own gates. Three things worth reading off this:

- **No tier dominates**, so the prose is not tuned to one model. Extraction is best on
  sonnet, relationships improve monotonically with tier, elements are highest on the
  *weakest* model.
- **That element result is not a paradox, it is the granularity effect again.** Two of the
  three haiku runs produced no capability layer at all, and gold's `clinic` has none — so
  restraint scores well and elaboration is punished, whichever model does the elaborating.
- **Repairs are where a weaker model spends its budget**: haiku used 2.5× the input tokens
  of sonnet for less than two-thirds of the output, because every repair resends the
  conversation. The three-iteration cap is what keeps that bounded, and the gate output is
  what a weaker model has instead of recall.

Informational, not a gate: `--min-f1` thresholds and `baseline.json` stay defined against
the default model, and a run under `--model` something-else compares against a baseline it
was not measured with (the harness will happily print a "regression" that is a tier
difference — read the model line in the header).

## The governance contracts (2026-08-06, claude-sonnet-5, 2 runs each)

| Contract | Runs holding every check | Notes |
|---|---|---|
| `decision` (`ea-adr`) | 2/2 | MADR fields, three options with pros *and* cons, bound to `app-wms` only |
| `dispensation` (`ea-dispensation`) | 2/2 | bounded expiry, a real standard waived, the board named as grantor |
| `supersede` (`ea-adr`) | 2/2 | all three moves, including the elements carried over — no `CORR001` |

Cheap (≈25k in / 8k out for six runs) and, so far, uneventful: the governance prose produces
records that satisfy their own rules, including the supersession paragraph that exists
because `CORR001` catches what happens when the third move is forgotten. One run needed a
single repair against `validate-gov`. A contract harness that never fails is only evidence
if the contracts can fail — which is why `tests/test_contract_harness.py` proves each one
rejects the mutation it targets.
