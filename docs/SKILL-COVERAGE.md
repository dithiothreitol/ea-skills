# What measures which skill

The core has a test per rule. The product is 24 files of prose, and prose cannot be
executed by pytest — so for a long time the honest answer to "how do you know the skills
work?" was *an end-to-end run and my judgement*. This page is the answer that replaced it,
including the parts where the answer is still "nothing does".

Four instruments, in descending order of what they can catch:

| Instrument | What it measures | Where |
|---|---|---|
| **Score against gold** | agreement with a golden repository, per category, over N runs | `eval/harness/run.py` |
| **Contract** | properties the skill's own text or the tooling states, on the artifact a run produced | `eval/harness/run.py` (apparatus), `eval/harness/contracts.py` (governance) |
| **Deterministic path test** | the commands the skill prescribes, run in the order it prescribes, on committed fixtures | `tests/test_adoption_path.py` and the per-command tests |
| **Manual end-to-end run** | a real host (Claude Code) executing the skill with its own planning and tools | recorded in `docs/BLUEPRINT.md` §8a |

The first two need an API key and cost tokens; they are never in the default gate. The
third is in every CI run. The fourth is a human sitting down and doing it.

## Every skill, and what would catch a defect in it

| Skill | Instrument | A defect in its prose is caught by |
|---|---|---|
| `ea-intake` | scored | fact and entity F1 against gold, 3 runs per case |
| `ea-model` | scored | element and relationship F1 against gold, 3 runs per case |
| `ea-capability-map` | scored | element F1 (the capability layer is part of the modelling phase) |
| `ea-stakeholders` | contract | ISO 42010 clauses 6.3/6.4 — stakeholders identified, every concern held |
| `ea-views` | contract | ISO 42010 clauses 6.5/6.6 — every view governed by a viewpoint, every concern framed |
| `ea-adr` | contract | MADR fields, rejected options with pros *and* cons, binding to real elements; and the three-move supersession contract (`CORR001`) |
| `ea-dispensation` | contract | mandatory bounded expiry, a real standard waived, tight scope, a named grantor |
| `ea-import` | path test | the adoption path: sliceable output, reference-closed element files, everything `assumed`, the gate refusing what the previous tool allowed |
| `ea-approve` | path test | promotion of one vouched-for slice while the rest stays a proposal |
| `ea-validate` | path test | the three-layer validator's own tests (141 rule codes in the catalogue) plus the gate steps of every harness run |
| `ea-align` | path test | `align` on the worked example's reference pack (clean under `--strict`) and on `eval/fixtures/broken/reference/`, where every `ALN` rule has a provoking pack |
| `ea-docs` | path test | the architecture description generated from the approved zone only |
| `ea-change-triage` | path test | `impact` in both zones, including the staging-versus-approved blast radius; the `debt` overlap queries it reads before classifying, including the three exclusions that keep them out of noise |
| `ea-context` | path test | context-pack tests (scope expansion, freshness label, binding closure) |
| `ea-check` | path test | consuming-repository lint fixtures (`eval/fixtures/consumer*`) |
| `ea-compliance` | path test | `validate-gov` COMP rules, including "non-conformant with no follow-up" |
| `ea-standards-base` | path test | `validate-gov` SIB/STD rules and the dispensation interaction |
| `ea-service` | path test | service-layer validation and the worked example's service records |
| `ea-regulatory` | path test | `dora-register` on `eval/fixtures/finco` (clean, and carrying `REG003` on purpose) and on `eval/fixtures/finco-broken`, where every `REG` code has a provoking element; plus the register's own gap section, asserted field by field |
| `ea-board` | path test | the reports it assembles (`kpi`, `staleness`, `conformance`, `debt`) |
| `ea-health` | path test | the same reports, plus every debt kind — a test pins that each one this skill can print is explained here |
| `ea-delta-ingest` | path test | `delta` — unmodelled entities and unused facts |
| `ea-run` | **manual only** | nothing mechanical. It routes between skills; its failure mode is choosing the wrong order, which only a real host exercises |
| `ea-eval` | **manual only** | nothing mechanical. It describes how to use the harnesses; a defect here shows up as somebody drawing the wrong conclusion from a number |

## What "path test" does and does not claim

It claims: every command this skill tells you to run is under deterministic test, on
committed fixtures, including the sequence and the artifacts. It does **not** claim the
prose is right. A skill could prescribe the right commands in the wrong order for the wrong
reason and pass — which is exactly why widening the scored and contract-checked rows is the
standing direction of travel, and why the two `manual only` rows are printed rather than
quietly rounded up.

## The limits that stay

* **Absolute quality is not measured.** A score is agreement with one gold repository. A
  candidate that models better than gold scores lower, and reading the category listings
  (which now name the unmatched items) is the only way to tell the two apart.
* **Host behaviour is measured by hand.** Both harnesses script the loop the skills
  describe; a real agent decides it, and that difference has produced findings twice
  (`ea-import`'s single file, the scorer's vocabulary blindness). The manual run stays an
  instrument, with its procedure in `eval/golden/README.md` and its results in BLUEPRINT §8a.
* **Contracts check properties, not taste.** Two architects write different ADRs for one
  decision and both are right; what neither may do is file one that breaks its own rules.
