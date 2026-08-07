---
name: ea-health
description: Run and interpret the model-health reports - EA debt register, staleness report and KPIs. Use when asked how healthy, current or trustworthy the model is, for an EA debt review, portfolio metrics, obsolescence exposure, or a periodic (e.g. quarterly) model health check.
---

# Model health: debt, staleness, KPIs

```bash
python -m easkills debt      --root <repo>   # EA-smell queries -> debt register
python -m easkills staleness --root <repo>   # review-age per element
python -m easkills kpi       --root <repo>   # one-screen metrics
python -m easkills roadmap   --root <repo>   # plateaus, gaps, and decided-but-unscheduled
# each takes --json for machine-readable output and --as-of for reproducible runs
```

All three read the approved zone and are deterministic given a date. None of them
gates: their job is to make rot visible early, because repository staleness is the
canonical way EA initiatives die.

## Reading the debt register

Each item is a deterministic graph query, and each kind has a characteristic honest
response:

* `isolated-element` -- retire it, capture its missing relationships from sources,
  or accept that it was speculative and remove it.
* `unsupported-capability` -- either a real gap (an investment conversation, like
  the worked example's customer service) or missing modelling. Decide which; both
  are useful, but only if named.
* `hub-element` -- concentration risk; a candidate for a decision record about its
  availability and change control, not necessarily for decomposition.
* `stale-content` / `dead-standard-reference` -- feed the review queue below.
* `duplicate-name` -- merge or rename; duplicate names silently corrupt every view
  and conversation downstream.

Three of the kinds are about the portfolio doing one job twice, and they read
differently from the rest: none of them is a defect on its face.

* `rationalization-candidate` -- a capability realized by two or more application
  components, printed with each realizer's `timeDisposition`, `lifecycle` and any
  other property the portfolio records against it.
* `overlapping-applications` -- an application pair realizing the same capabilities
  more than once. The pair is the merge conversation; the candidates above are its
  symptoms.
* `duplicate-service` -- one service name offered by *different* providers. (A
  service realizing an identically named service one layer up is idiomatic and is
  not reported; so is one component publishing two same-named services, which is a
  naming slip for `duplicate-name`.)

Redundancy is often deliberate -- resilience, data residency, a strangler running
beside what it replaces. The tooling cannot tell that from drift, so the honest
response is to record which one it is: **deliberate redundancy gets an ADR**, and
undecided overlap goes to the board (`ea-board`) or through triage
(`ea-change-triage`) as a re-architecting item. An overlap that survives two health
reviews without a record is the finding.

Debt items are worked through `ea-delta-ingest` (model corrections, as staged
proposals) or accepted explicitly in the report -- never fixed by deleting the
evidence of the problem.

## Reading the cost section

It only appears when `ea.config.yaml` carries a `costModel`. **The tool computed the
exposure, the operator priced it** -- the register prints that sentence because it is
the only honest thing to say about the number underneath it. Never present a total
without it, and never present one as an estimate the tooling produced.

* **Read the total as a floor, not a figure.** The section lists every exposure it
  could not price and every element it could not measure; both are underneath the
  total, and both mean the real number is larger. If the list is long, the useful
  output of this run is *the list*, not the sum.
* **The rates are the organisation's, and they are arguable.** When a total is
  challenged, the argument is about a rate, not about the tool -- which is the point
  of the split. Bring the rate line, not the arithmetic.
* **Movement beats level.** One total means little; the same rates run monthly show
  whether exposure is accruing or being worked off. Keep the `--json` alongside the
  KPI history.
* **Never set a rate to make a number look right.** A rate exists to be defended in
  the meeting where someone asks where it came from. If nobody can source one, leave
  it unset -- "not priced" is a true statement and a plausible guess is not.
* **`--as-of` is not optional for anything quoted.** Two of the exposures accrue
  daily; a figure without the date it was computed for cannot be reproduced or
  compared.

## Reading staleness

The report lists every element past `stalenessDays` or never reviewed, with owners
-- and each element's **demand** (how many service requests named it in scope).
The output is a *review queue grouped by owner, ordered by demand*: review what
consumers actually ask about first. Elements with zero demand and long staleness
are de-scoping candidates, not just review debt. Record outcomes by updating
`lastReviewed` (a real review, not a bump; bumping the date without looking is
worse than staleness because it forges freshness).

## Reading KPIs

Trends matter more than snapshots: run with `--json`, keep the outputs (e.g. in
`governance-log/metrics/`), and compare. The ones that predict trouble:

* **evidenced share falling** -- assumptions accumulating faster than confirmation;
* **stale share rising** -- the review habit is decaying;
* **obsolescence exposure growing** -- retirements outpacing migrations (check the
  matching dispensations exist and have credible expiry dates);
* **unframed/unheld concerns** -- the documentation loop is reopening.

## Reading the roadmap

`roadmap` reads the Implementation & Migration layer as a plan. Three things on it
are worth a human every time:

* **Intent with no plan** -- an element decided `Migrate` or `Eliminate` that no
  plateau carries (`PLAT005`). This is the most common finding and the most
  actionable: either schedule it or stop claiming the disposition, because a
  portfolio decision nobody scheduled quietly becomes a portfolio decision nobody
  made.
* **A horizon in the past** (`PLAT006`) -- every plateau already reached. The plan
  has expired; close it or extend it, and do not let the reports keep reporting it.
* **A gap with no funding decision behind it.** The tooling cannot see budgets, but
  it can show you the gap next to the constraint or dispensation that explains why
  it is still open. If nothing explains it, that is the finding.

## Reporting back

One paragraph of verdict, then the four lists that need a human: debt items with a
proposed disposition each, the review queue by owner, the KPI movements since the
last run, and anything decided but unscheduled on the roadmap. A health report that ends without owners and dates is a weather
forecast, not maintenance.
