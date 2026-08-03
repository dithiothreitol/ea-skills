---
name: ea-dispensation
description: File, renew or close a time-bounded dispensation (waiver) from a standard or rule. Use when a system cannot comply yet (STD002 blocking), when a compliance assessment is non-conformant, when DISP003/DISP006 findings appear (expired or expiring waivers), or when asked for an exception, waiver or dispensation.
---

# Dispensations: exceptions with an expiry

A dispensation says: *this system may deviate from that standard, until this date,
because a named person accepted the risk*. It is the mechanism that keeps exceptions
governed instead of silent.

```yaml
# governance-log/dispensations/disp-onprem-legacy.yaml
id: disp-onprem-legacy
title: ERP Core and WMS may remain on-premise pending replatforming
waives:
  standard: std-onprem-hosting
appliesTo: [app-erp-core, app-wms]
rationale: >
  Why compliance is not possible now, and what has to happen before it is.
grantedBy: architecture-board@example.test
granted: 2026-07-01
expires: 2027-06-30
status: open
```

## The rules that make it real governance

* **`expires` is mandatory** -- the schema rejects a waiver without it (`DISP001`).
  A dispensation without an expiry is the tell of fake governance.
* **Expiry is loud.** Once the date passes, `validate-gov` fails with `DISP003`
  until a human renews or closes the record; `DISP006` warns 30 days ahead so the
  review can be scheduled. Never fix `DISP003` by pushing the date out silently --
  renewal is a *new decision*: re-confirm the rationale with the grantor, or close
  the record and let `STD002` state the truth.
* **`grantedBy` is a real authority**, not you. Filing the record is your job;
  granting it is a human's. Prepare the record with a proposed expiry and rationale,
  and present it for sign-off -- same discipline as `ea-approve`.
* **Scope tightly.** One standard, the specific elements, the shortest defensible
  window. A waiver for "everything, two years" is a policy change wearing a
  waiver's clothes -- route that to a decision record instead.

## Lifecycle

File → (grant) → open → reviewed before expiry → **renewed** (new or updated record,
re-granted) or **closed** (`status: closed`) → the underlying `STD002` either returns
(driving migration) or is gone because the system migrated. Closed records stay in
git; do not delete them.

## Reporting back

Say what is waived, for which elements, until when, on whose authority, and what has
to be true for the waiver not to be needed again. When closing or renewing, connect
it to the compliance assessment or migration that triggered the review.
