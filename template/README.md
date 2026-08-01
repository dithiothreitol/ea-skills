# <Organisation> enterprise architecture

Model repository scaffolded from the `ea-skills` template. Copy this directory, edit
`ea.config.yaml`, and start with intake.

```bash
python -m easkills chunk          --root .            # split sources for extraction
python -m easkills validate-facts --root .            # the fact register gate
python -m easkills coverage       --root .            # what the facts do not cover yet
python -m easkills validate --root . --zone staging   # while proposing
python -m easkills validate --root . --zone approved  # the published model
python -m easkills compile  --root . --zone approved  # -> build/model.xml
```

## Layout

| Path | Holds |
|---|---|
| `facts/sources/` | Raw input, unedited: interview notes, exports, documents. Provenance quotes must be findable here verbatim. |
| `facts/register/` | The fact register produced by intake: atomic statements, each with a mechanically verified quote. |
| `facts/entities.yaml` | Canonical names and aliases for the things the sources mention. |
| `model/staging/` | Machine-proposed concepts awaiting human approval. Ownership metadata is advisory here. |
| `model/approved/` | Human-signed model. Ownership and review dates are mandatory. Everything downstream reads only from here. |
| `landscape/` | Architecture landscape partitioned by scope: `strategic/`, `segments/`, `capabilities/`. Baseline, transition and target states are modelled as ArchiMate plateaus inside the model, not as copies of it. |
| `standards/` | Standards information base. One file per standard, carrying its type (legal / industry / organisational) and lifecycle state (proposed, trial, active, deprecated, retired). |
| `requirements/` | Architecture requirements. |
| `governance-log/decisions/` | Architecture decision records (MADR). |
| `governance-log/compliance/` | Compliance assessments, recorded with TOGAF's six conformance levels rather than pass/fail. |
| `governance-log/dispensations/` | Time-bounded waivers. **An expiry date is mandatory** -- a dispensation without one is not governance. |
| `docs/` | Generated architecture description and audience-facing outputs. |
| `build/` | Compiled artifacts. Reproducible; not committed. |

## Conventions

Identifiers are stable lower-case slugs and are never regenerated. Every element and
relationship is either evidenced by a verbatim source quote or explicitly marked
`assumed: true` with a rationale. Views declare which elements to show; layout is
computed. See `docs/RULES.md` in the ea-skills repository for the full rule catalogue.
