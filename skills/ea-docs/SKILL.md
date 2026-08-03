---
name: ea-docs
description: Generate and review the architecture description (ISO 42010 structure) and audience outputs from the approved model. Use when asked for architecture documentation, an architecture description, a portfolio report, TIME quadrants, or a stakeholder-facing summary of the model. Reads only the approved zone.
---

# The architecture description

```bash
python -m easkills docs --root <repo>
```

One command produces `docs/architecture-description.md` plus one SVG per view in
`docs/views/`, generated **only from `model/approved/`** -- staging content is a
proposal and never appears in documentation. The command refuses a model with
validation errors; do not override that to hit a deadline.

## What the generator guarantees (so you do not re-do it)

* ISO 42010 Clause 6 shape: stakeholders -> concerns -> views, with a concern-coverage
  table that shows **nobody**/**no view** in bold where the loop is open.
* Application portfolio with APM fields and TIME quadrants, straight from element
  properties -- nothing is re-judged at documentation time.
* Capability support table, including capabilities *nothing realizes*.
* Every declared assumption surfaced as an open question -- burying assumptions is the
  failure mode this section exists to prevent.
* Deterministic output: the "as of" date is the newest `lastReviewed` in the model,
  not the wall clock, and identical models produce identical bytes. The generated
  files are committed; CI fails if they are stale, so regenerate and commit together
  with any model change.

## Your job around the generator

**Before:** make the inputs true. The description can only be as good as the
stakeholder register (`ea-stakeholders`), the views (`ea-views`) and the portfolio
properties on the elements. A missing `timeDisposition` shows up as an em-dash in
front of a CIO -- fix it in the model, with evidence, not in the markdown.

**Never edit the generated files.** Any hand edit is overwritten on the next run and
CI flags the drift meanwhile. If a section reads wrong, the model or the generator is
wrong; fix the cause.

**After: audience one-pagers.** When someone needs a tailored summary (a board slide,
a one-pager for the auditor), write it as a *separate* document next to the generated
one (e.g. `docs/onepager-<audience>.md`), sourced from the description and the model
-- and say which model state ("as of" date) it reflects. Do not fork the architecture
description itself per audience; one description, many extracts.

## Reporting back

Say what was generated and from which model state, which concerns are still uncovered
(the bold gaps in section 2), which portfolio fields are missing, and which
assumptions the reader is being asked to accept. Those four lists are the review
agenda; the prose around them is garnish.
