---
name: ea-views
description: Author model views and render them to SVG. Use when asked to create a diagram, view or visualisation of the architecture, when a concern has no view framing it (ISO003), or after model changes that should be reflected in rendered output. Views declare content only; layout and rendering are computed.
---

# Authoring and rendering views

A view is a *selection* with a *purpose*: which elements to show, for which declared
concern. Everything else -- geometry, colours, arrowheads -- is computed
deterministically, so two runs produce identical bytes and diffs stay about
architecture.

## Authoring

```yaml
views:
  - id: customer-service-gap
    name: Customer Service Gap
    viewpoint: Application Usage
    concerns: [concern-order-status-effort]
    documentation: >
      The three systems a service agent opens to answer "where is my order".
    include: [cap-customer-service, app-order-portal, app-erp-core, app-wms]
```

Rules that keep views honest:

* **Never write coordinates.** There is no field for them; do not ask for one.
* **`concerns` names why the view exists.** A view with no concern draws `ISO005` --
  either it answers a stakeholder question or it is decoration. Get the concern ids
  from the stakeholder register (`ea-stakeholders` owns that loop).
* **Connections are derived, not drawn.** Every relationship whose two endpoints are
  on the view appears automatically; `appliesTo` bindings render dotted. If a
  connection you expected is missing, the *model* is missing the relationship -- fix
  it there (with evidence), never fake it visually.
* **Select, do not dump.** Six to fifteen elements answer a question; forty document
  a database. Prefer several small views over one mural. The whole-model overview is
  one view, not the pattern.
* **Viewpoint names** come from the ArchiMate example viewpoints (Layered, Capability
  Map, Application Usage, Motivation, Implementation and Migration...). They set the
  reader's expectations; do not invent novel viewpoint names when a standard one fits.

## Rendering

```bash
python -m easkills render --root <repo>                 # approved -> docs/views/*.svg
python -m easkills render --root <repo> --zone staging  # preview proposals
python -m easkills docs   --root <repo>                 # views + architecture description
```

Rendering is dependency-free and byte-stable; re-render after any model change that
touches a view's elements, and commit the SVGs together with the model change --
CI treats stale committed views as a failure. The notation is simplified (layer
colours, arrows, dashed realization); for full ArchiMate notation open
`build/model.xml` in Archi via File > Import > Model Exchange File.

## Checking

`validate` covers views: unknown includes (`REF002`), empty views (`REF003`),
unknown concerns (`ISO001`). Render errors on a view naming missing elements --
validate first, render second. Report which concerns now have views, which still do
not, and any element you deliberately left off a view to keep it readable.
