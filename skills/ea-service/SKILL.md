---
name: ea-service
description: Operate the architecture-service layer (Architecture-as-a-Service / on-demand) - maintain the service catalog, intake and fulfil service requests, keep SLA hygiene. Use when someone requests something from EA ("we need a review / context / an exception"), when defining or changing EA's offerings, or when REQ006-REQ008 findings (SLA breaches, retired offerings) need working.
---

# The architecture service layer

EA here is a provider, not a gate: a **catalog** of offerings with owners and SLAs
(`services/`, one per file), and a **demand ledger** of who asked for what
(`governance-log/requests/`). Consumption is recorded, so EA's value is measurable
instead of asserted -- and maintenance follows demand instead of ambition.

## The catalog

```yaml
# services/svc-context-pack.yaml
id: svc-context-pack
name: Agent context pack
description: What the consumer gets, phrased from the consumer's side.
fulfilledBy: ea-context / python -m easkills context --scope <element>
owner: ea@example.test
slaDays: 2
lifecycle: active          # proposed | active | retired
selfService: true
```

Catalog discipline: an offering is a **promise with a number** -- no owner or SLA, no
offering (schema rejects it). Keep the catalog short and true: five offerings people
use beat fifteen that decorate. Retire honestly (`lifecycle: retired`); requests
against retired offerings are flagged (`REQ008`). `selfService: true` marks offerings
the consumer can run themselves -- prefer growing that set; every self-service
fulfilment is an SLA that cannot be breached.

## The request lifecycle

```yaml
# governance-log/requests/req-2026-08-erp-context.yaml
id: req-2026-08-erp-context
service: svc-context-pack
requestedBy: erp-replatforming-team@example.test
requested: 2026-08-01
scope: [app-erp-core]
status: open               # open | fulfilled | declined
```

1. **Intake.** Record the request the moment it arrives, with the offering id and
   the model elements in `scope` (they must exist -- `REQ004`; if the area is
   unmodelled, that is intake work scoped to this request, on-demand, thin-slice:
   never model beyond what the request needs).
2. **Fulfil.** Run the offering's fulfilment path; set `status: fulfilled`,
   `fulfilled:` date and `fulfilledBy:` pointing at the deliverable (`REQ005`
   rejects unevidenced fulfilment). The deliverable carries its own "as of"
   freshness -- never strip it.
3. **Or decline, with a reason** in `notes` (`REQ007`). Declining out-of-scope work
   honestly is part of being a service; silent queues are not.
4. **SLA hygiene.** An open request past its offering's `slaDays` warns (`REQ006`)
   and shows in `kpi` as a breach. The honest responses: fulfil, decline with
   reason, or renegotiate the catalog promise -- never quietly edit dates.

## What demand buys you

* `python -m easkills kpi` -- the Service line: offerings, open/fulfilled/declined,
  SLA breaches, average fulfilment time. This is the AaaS value evidence.
* `python -m easkills staleness` -- every element carries its demand count; review
  what people ask about first, and treat never-requested content as a candidate for
  de-scoping rather than eternal upkeep.

## Reporting back

The request's disposition (fulfilled with what, or declined why), SLA state against
the promise, and anything the request revealed: an unmodelled area, a missing
offering people keep asking for informally, or an offering nobody has requested in
months -- the catalog is maintained by the same evidence discipline as the model.
