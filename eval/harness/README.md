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
3. `ea-model`'s prose → `model/staging/` → `validate --zone staging` → same repair loop
4. `promote` → `score --gold <case>`

Every gate is the real command, run as a subprocess exactly as a user would run it.

## What the number means, and what it does not

It measures **agreement with one gold repository**, which is a regression signal for the
skill text — not an absolute grade. A candidate that models at finer granularity than
gold scores low on precision while being defensible architecture; read the categories,
not the headline.

It measures **two skills**: `ea-intake` and `ea-model`, whose prose is what the harness
puts in front of the model. Everything else in `skills/` is unmeasured — including
`ea-capability-map`, even though the modelling phase produces capabilities, because
`ea-model` is the file the run actually reads. Widening the harness means widening that
list deliberately, not assuming coverage it does not have.

It does **not** measure a host like Claude Code executing the same skills with its own
tools, planning and multi-turn behaviour. This harness scripts the loop; a real agent
decides it. Treat the two as different instruments: this one is repeatable and cheap,
the other is faithful and manual (the end-to-end runs recorded in BLUEPRINT §8a).

Runs use the API default temperature, so `--runs 3` is the default and the report shows
**min / median / max** per category. A single run tells you almost nothing about the
skills and quite a lot about that particular sample.

## Regression gate

`baseline.json` holds the committed medians. A plain run compares against it and exits
1 if any category's median falls. Rewrite it with `--baseline` only when the new numbers
are understood and deliberate — the point of a baseline is that moving it is a decision.

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
**derived-relationship gap** already listed in [RULES.md](../../docs/RULES.md) as not
implemented: ArchiMate's derivation rules (DR1–DR8) are exactly the machinery that would
say "gold's edge is this candidate's two-hop path". Until that exists, relationship F1
compares direct edges between models of different granularity, and two such models share
none. Read it as *"the candidate did not draw the same edges"*, never as *"the candidate
connected nothing"* — `rel-structural`, the label-independent diagnostic, cascades the
same way and cannot separate them either.

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
