---
name: Architecture change request (Phase H)
about: This issue IS the change-request record -- ea-change-triage works from it (AD-08)
title: "[change] "
labels: change-request
---

<!-- The git-native change-request form. It ships with the ea-skills template because
     the ids below live in *this* repository: the architecture, not the tooling.
     Fill what you know; triage classifies and routes it. -->

## What should change, and why now

<!-- The demand in the requester's words. Link source material (an email, an export,
     an incident) if it exists -- it becomes intake input under `facts/sources/`. -->

## Affected scope (best guess)

- **Elements / systems:** <!-- ids from `model/approved/` if known, names otherwise -->
- **Standards touched:** <!-- from `standards/`, if any -->
- **Decisions this may contradict:** <!-- from `governance-log/decisions/`, if known -->

## Requested by

- **Who:** 
- **Needed by (date + consequence of missing it):**

<!-- If your organisation runs EA as a service, the corresponding offering and its SLA
     live in `services/`, and the request is also recorded in `governance-log/requests/`. -->

---

### Triage (filled by ea-change-triage)

- **Classification:** simplification / incremental / re-architecting
- **Evidence:** <!-- impacted elements + impacted stakeholder groups; >=2 groups => re-architecting -->
- **Route:** <!-- delta-ingest / compliance assessment / dispensation / full pipeline re-entry -->
- **Recorded decision (if it overturns one):** <!-- new ADR id -->
