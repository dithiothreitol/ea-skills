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

Precision/recall/F1 per category, plus the candidate's own validation gates, because
matching gold while failing provenance verification is a fabrication that happens to be
right. `--min-f1 <pct>` turns the score into a gate.

## What the score is, and what it is not

It measures **agreement with one gold repository**. That makes it a regression signal
for a change in the skills; it is not an absolute grade for a model, and a low number is
not by itself evidence of a bad architecture.

An end-to-end run on 2026-08-05 made the difference concrete. A candidate produced blind
from this case's source passed every gate, recalled **100%** of gold's elements and
relationships -- and scored 15% on elements and **0%** on relationships, because it wrote
"Electronic Health Record System" where gold wrote "EHR" and because one unmatched
element zeroed every relationship touching it. The matching rules below are the answer to
that run:

| Category | Matched when |
|---|---|
| entities | term sets (name + aliases, normalized) intersect |
| facts | the **source ground they cover** overlaps by ≥ 50% of the shorter side; the statement then decides full credit (similarity ≥ 0.85) or half. Regrouping the same ground (splitting one fact into two, or merging two into one) is a match, not a miss -- but quoting the right sentence under a statement that says something else is only half |
| elements | (type, name) with names resolved through **both** repositories' entity alias tables; a type disagreement *inside one ArchiMate layer* is half a match (found it, contested classification), across layers it is no match |
| relationships | type + endpoints mapped through matched elements; an edge the candidate did not draw but whose model **implies** it under ArchiMate's own derivation rules (DR1--DR8, `easkills/derive.py`) is half a match, and the candidate edges carrying that derivation are half matches too. A label-independent `rel-structural` count is reported beside it as a **diagnostic** -- never gated -- so a collapse caused by naming is visible as such |

Half credits are reported, never hidden: the `(n half)` note on a row says how much of the
number rests on a partial match, and every score now **names its items** -- what gold had
and the candidate missed, what the candidate has and gold does not support, and which
credits were half (with the derivation rule and the abstracted-away element cited for
relationships). The terminal shows the first eight per line; `--json` carries all of them.
Three separate investigations of a fallen category were hand-diffs of two YAML trees
before that existed.

Two consequences worth stating plainly. A perfect self-score stays perfect, so
`--min-f1 100` remains a valid CI gate. And a candidate that disagrees with gold's
vocabulary is now separated from one that missed the content -- which is the distinction
the harness exists to make.

## The cases

| Case | Exercises |
|---|---|
| `clinic/` | One interview: entity resolution, an integration relationship, a risk statement. |
| `contested/` | **Two sources that disagree.** An inventory records a scheduling system as decommissioned; an interview two months later records dispatch using it weekly. Both sides stay in the register (`confidence: contested` + `contests:`), the model follows one and says so (`PROV009`), and the architecture description quotes the losing side in its open questions. Also exercises multi-source intake and entity resolution across documents. |
| `../example/` | The largest case: full lifecycle, governance records, service layer. |

## Changing a case

Gold is not edited to make a candidate pass -- that is the whole discipline. It *is*
edited when a measurement shows gold breaks a rule the skills themselves state, which has
happened once and is recorded so the difference stays legible:

* **2026-08-06, `clinic`: two compound facts split into four atomic ones (7 → 9).**
  `ea-intake` defines a fact as *one atomic statement*; gold carried *"Patients book
  appointments through the online booking portal **or by calling the front desk**"* and
  *"Invoices are produced by the billing module inside the EHR**; we do not run a separate
  billing system**"* as single entries. Three measured runs split both and were charged
  half credit nine times over, dropping `clinic/facts` from 83% to 74% -- while following
  the skill more closely than gold did. The fix belonged in gold, not in the scorer.

* **2026-08-06, `clinic`: the capability layer added (3 capabilities, 3 realizations).**
  Recorded here in full, because it is the second gold change and the one most easily
  mistaken for the forbidden move.

  *The contradiction.* `ea-capability-map` states that the capability map is **the spine**,
  that it is modelled **before anything else**, and that the load-bearing relationship is
  `ApplicationComponent --Realization--> Capability`. `ea-model` repeats it. Gold's
  `clinic` had **no Strategy layer at all** — so a run that followed the method produced
  three elements gold could not match, and lost precision for obeying the skill it was
  being measured on. `python -m easkills readiness --root eval/golden/clinic` prints
  `Strategy  empty` next to a Business and Application layer that are complete, which is
  the contradiction stated mechanically.

  *Why this is a correction against the rules and not against a run.* Three measured runs
  (0.11.0) independently produced three clinic capabilities, and that is what **exposed**
  the problem — it is not the authority for the fix. The capabilities written into gold
  were derived from the register the way the skill prescribes: each is a noun phrase
  naming something the clinic can do, each cites the fact that evidences it, and there are
  three because the interview supports three. Not six: `ea-capability-map` says the 6–12
  range "is a shape, not a target", and that "a single interview supports the capabilities
  it names and no more". Gold's names were **not** copied from any run's output, and the
  entity table was **not** given aliases to make matching easier — that would be tuning
  gold to the thing it measures.

  *The counter-argument, and why it lost.* A two-page interview could be said to stop
  legitimately below the capability line: nobody in it utters the word "capability", and
  the only capability term any source in the set names outright is the worked example's
  "Customer service is the weak spot". But the skills do not make the map conditional on
  the sources naming it — they make it the first thing modelled and the thing everything
  else attaches to. A yardstick that omits the spine measures method compliance as error.
  If the position is ever reversed, it is this paragraph that has to be argued with.

  *Consequence for the baseline, stated because it is easy to miss.* `clinic`'s element and
  relationship denominators changed, so the 0.11.0 baseline for those two categories is
  **not comparable** across this change — the same situation as adding `ea-capability-map`
  to the measured phase, and it is noted in `eval/harness/README.md` rather than left to be
  inferred. `facts` and `entities` are untouched and stay comparable.

The rule that stays: a golden case may be corrected against the skills' own stated rules,
never against a run's output. If a run disagrees with gold and no rule is on the run's
side, the run is what is wrong.

Two tells that separate the two, worth naming because this change had to pass both: a
correction can be argued **from a sentence in a skill** without mentioning any run, and it
leaves gold's *vocabulary* alone. Tuning names, adding aliases, or relaxing a statement so a
run matches is the forbidden move even when the number moves in the same direction.

## Adding a case

A case earns its place by exercising something the existing set does not (a new
layer, a contradiction between sources, a messier document format). Keep it small
enough to diff by eye, make every quote verbatim, and add it to the CI steps that
validate golden cases -- gold that does not pass its own gates is not gold.
