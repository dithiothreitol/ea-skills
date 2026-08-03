---
name: ea-delta-ingest
description: Ingest new or changed source material and propose model updates as a diff against the approved model - continuous ingestion, not one-shot generation. Use when new interviews, CMDB exports or drift reports land in facts/sources, when the delta report shows unmodelled entities or unused facts, or when asked to "update the model from" new information.
---

# Delta ingestion

The model is maintained, not regenerated. New information becomes *proposed changes
against approved*, never a fresh model -- stable ids and the staging overlay exist
precisely so a re-run produces a reviewable diff.

## Pipeline

1. **Intake first.** New documents go through `ea-intake` like any source: chunks,
   facts with verbatim quotes, entity resolution against the *existing*
   `facts/entities.yaml` (this is where "the new WMS" gets recognised as `wms`
   rather than becoming a twin), `validate-facts`, coverage.

2. **Ask the tooling what is new:**

```bash
python -m easkills delta --root <repo>
```

Two mechanical lists: entities with no model counterpart (candidate additions) and
facts no model concept cites (unused evidence). They are candidates, not defects --
your judgement decides which are in scope.

3. **Propose the delta in staging.** For each accepted candidate: new elements and
   relationships in `model/staging/`, citing facts (`provenance: [{fact: ...}]`).
   For changed reality, re-propose the existing id with updated content -- the
   overlay treats it as an update. For things the sources say are *gone*
   (decommissioned, replaced): propose the retirement explicitly -- set
   `properties.lifecycle: end-of-life` (or remove the element in the staged copy of
   its file) and say so in the report; silent disappearance is how models and
   reality drift apart.

4. **Validate and hand over.** `validate --zone staging`, three-repair cap, then
   report. Promotion stays human (`ea-approve`).

## Contradictions are findings, not merge conflicts

When a new source contradicts approved content ("the portal now holds stock levels"
vs the approved claim it does not), do not quietly pick a winner. Propose the update
in staging citing the new fact, and flag the contradiction explicitly in your report
with both quotes -- the human promoting decides which reality is current. If the old
claim came from an older document, that is expected drift; if both sources are
current, that is a clarification question for the owners.

## Reporting back

Lead with the diff shape: N additions, M updates, K proposed retirements, and the
contradictions needing a ruling. List what you deliberately did not model and why.
The unused-facts list that remains is fine -- not every fact becomes architecture.
