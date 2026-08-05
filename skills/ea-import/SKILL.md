---
name: ea-import
description: Import an existing architecture model (ArchiMate Open Exchange XML from Archi, LeanIX, Bizzdesign or any conforming tool) into model/staging/ for brownfield adoption. Use when a repository does not start empty - when asked to "migrate our model", "import from Archi", or bring an existing landscape under this discipline.
---

# Brownfield import: an existing model, brought under the rules

```bash
python -m easkills import --root <repo> --file <export>.xml
```

Reads an Open Group ArchiMate Model Exchange file and writes one YAML proposal into
`model/staging/`. From Archi: *File → Export → Model To Open Exchange File*. Most
commercial tools export the same format.

## What the import does on its own

* **Everything lands in staging.** Promotion is still the only write path into
  `approved/`, and still runs the gate. An import never overwrites an existing file.
* **Everything arrives as a claim, not evidence.** Concepts are marked
  `assumed: true` with an import rationale; a `provenance` property from a previous
  export is kept as information, never trusted as verification. Evidence is built
  *after* import, through `ea-intake` and the fact register.
* **Owner and review metadata are lifted** from exported properties (`owner`,
  `lastReviewed`, `appliesTo`, `standards`) back into DSL fields — with `appliesTo`
  references renamed together with the elements they bind.
* **Geometry is discarded** (layout is computed at render time), junctions are mapped
  to the one `Junction` concept, identifiers become readable slugs derived from names
  (`--ids identifiers` keeps the export's own), and every rename, skip and mapping is
  in the report. Nothing is dropped silently.
* **The import never judges the model.** A relationship the previous tool allowed and
  the 3.2 matrix forbids is imported as-is and left for `validate` to report — that
  finding is the migration surfacing what the old tool never checked.

## Your job after the import

Run `python -m easkills validate --root <repo> --zone staging`. The findings are not
noise — **they are the adoption backlog**, already itemised:

| Finding | Meaning | Work |
|---|---|---|
| `GOV001`/`GOV002` warnings | No owner / no review date | Assign owners before promoting; promotion turns these into errors |
| `PROV006` info | Everything is assumed | Evidence what matters via `ea-intake`; drop what nobody defends |
| `REL001` errors | The old tool allowed what the matrix forbids | Fix the relationship type — this is real modelling debt made visible |
| `STD001`/`STD002` errors | Standards claims with no SIB, or retired ones | Migrate the standards base too (`ea-standards-base`), or drop the claim |

**Promote in slices, not wholesale.** A 400-element import promoted in one move signs
off 400 unreviewed claims. Promote the slice someone actually vouches for (owner
assigned, reviewed date set), leave the rest in staging as the visible backlog — an
honest architecture repository is allowed to know less than the old tool claimed.

**Do not chase a clean import of a dirty model.** If the export names two systems
identically, the import suffixes the second (`crm-suite-2`) and moves on; deciding
whether they are one system is intake work, with the people who run them.

## Reporting back

State the counts, where the file landed, what was skipped or renamed (with reasons),
and the validation summary of the staging zone as the adoption backlog. Recommend the
first promotion slice: the elements that already have an owner and a defensible
review date.
