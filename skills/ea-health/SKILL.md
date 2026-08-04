---
name: ea-health
description: Run and interpret the model-health reports - EA debt register, staleness report and KPIs. Use when asked how healthy, current or trustworthy the model is, for an EA debt review, portfolio metrics, obsolescence exposure, or a periodic (e.g. quarterly) model health check.
---

# Model health: debt, staleness, KPIs

```bash
python -m easkills debt      --root <repo>   # EA-smell queries -> debt register
python -m easkills staleness --root <repo>   # review-age per element
python -m easkills kpi       --root <repo>   # one-screen metrics
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

Debt items are worked through `ea-delta-ingest` (model corrections, as staged
proposals) or accepted explicitly in the report -- never fixed by deleting the
evidence of the problem.

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

## Reporting back

One paragraph of verdict, then the three lists that need a human: debt items with a
proposed disposition each, the review queue by owner, and the KPI movements since
the last run. A health report that ends without owners and dates is a weather
forecast, not maintenance.
