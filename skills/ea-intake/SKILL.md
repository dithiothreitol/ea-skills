---
name: ea-intake
description: Extract a verified fact register from raw source documents (interviews, notes, inventories, CMDB exports) as the first stage of the EA pipeline. Use when asked to ingest, read in, or extract facts from source material, when new documents land in facts/sources, or before any modelling work when the fact register is missing or stale. Produces facts with mechanically verified quotes, an entity alias table, a coverage report and clarification questions.
---

# Ingesting sources into the fact register

You are the extraction stage. Raw documents go in; what comes out is a **fact
register** -- atomic statements, each carrying a verbatim quote that code will locate
in the source -- plus an **entity table**, a **coverage report** and **clarification
questions**. Everything downstream (capability map, layer models, views, documents)
builds on this register, so its quality is the ceiling for the whole pipeline.

## Non-negotiables

**1. A fact without a quote is not a fact.** There is deliberately no `assumed`
field in the register schema. If you believe something the sources do not say,
it is a clarification question, not a fact. The validator (`FACT004`) rejects any
quote it cannot locate in the cited file -- fabricated citations are the documented
failure mode this stage exists to prevent.

**2. Quotes are verbatim.** Copy the exact characters, including pipes in table rows.
Multi-line is fine (matching is whitespace- and case-insensitive), paraphrase is not
(`FACT005`). Do not tidy grammar, do not reconstruct from memory.

**3. One fact, one claim.** "The ERP holds order records and runs on-premise" is two
facts. Atomic facts are what let the modelling skills cite precisely and let delta
ingestion diff meaningfully later.

**4. Never edit a source document.** Sources are the evidence; the register points
into them.

## The pipeline

### 1. Chunk

```bash
python -m easkills chunk --root <repo>                 # all of facts/sources
python -m easkills chunk --root <repo> --file facts/sources/interview.md
```

Work chunk by chunk, never the whole document in one pass -- small units roughly
double entity recall. The chunker is deterministic: line numbers are exact, and
re-runs produce identical chunks, so your extraction is reviewable and repeatable.

### 2. Extract, then glean

For each chunk, extract every atomic factual claim into `facts/register/<source>.yaml`:

```yaml
facts:
  - id: fact-erp-role
    statement: The ERP core holds the master order records and performs invoicing.
    provenance:
      - file: facts/sources/interview-operations-2026-07-15.md
        quote: The ERP core holds the master order records and does the invoicing.
    entities: [erp-core, order-record]
    topics: [application]
```

Then do **one gleaning pass** per chunk: re-read it asking only "what did I miss --
quantities, dates, owners, constraints, negations?" Negations matter: "the database
is not shared with any other system" is a fact people forget to extract.

Use `confidence: implied` when the quote supports the statement only indirectly
(e.g. "when the API is down, customers cannot order" implies the ERP is a single
point of failure). Default is `stated`; reviewers look twice at `implied`.

Ids are stable slugs (`fact-erp-role`), one register file per source document.
When two sources support the same fact, keep **one** fact with both quotes in its
provenance list -- that is what the duplicate-statement warning (`FACT007`) pushes
you toward.

### 3. Resolve entities

Maintain `facts/entities.yaml`: one entry per real-world thing, with every alias the
sources use for it.

```yaml
entities:
  - id: erp-core
    name: ERP Core
    kind: application        # informal hint; ArchiMate typing happens later
    aliases: [the ERP, ERP]
```

"The portal", "online order portal" and "Order Portal" are one entity or the model
downstream will contain three applications. Only record aliases the sources actually
use. One term must resolve to exactly one entity -- a collision is an error (`ENT002`)
because it means downstream modelling would silently merge two different things.

### 4. Validate, repair (three iterations, then stop)

```bash
python -m easkills validate-facts --root <repo>
```

Fix errors and re-run, **at most three times**. `FACT004` means the source does not
say what you quoted: find the real sentence or drop the fact -- do not shop around for
a different file with similar words. If findings survive three passes, stop and report
what is unresolved; do not grind.

### 5. Measure coverage, ask questions

```bash
python -m easkills coverage --root <repo>
```

The report lists every substantive source statement that no fact cites, with line
numbers. For each uncited span, decide honestly:

* extractable fact you missed -> go back to step 2;
* pleasantry, boilerplate, formatting -> say so in your report, do not force a fact;
* something ambiguous or half-said -> a **clarification question**.

Write the questions where the repository keeps its open questions (or in your report):
each one names the source and line range it comes from, quotes the ambiguous text, and
asks something a stakeholder can actually answer. Questions are a first-class output
of intake -- a thin source produces few facts and many questions, and that is a good
result, not a failure.

## Reporting back

Lead with the numbers: facts extracted, entities resolved, validator verdict, coverage
per source. Then the clarification questions, then anything you deliberately did not
extract and why. Never call intake finished while `validate-facts` reports errors, and
never pad coverage with facts that restate headings or metadata.
