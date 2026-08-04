---
name: Validator rule proposal
about: Propose a new deterministic check (model, facts or governance)
title: "[rule] "
labels: enhancement, rule
---

## The defect this rule catches

<!-- What real modelling/governance mistake does it detect? A rule that cannot
     point at a concrete failure it prevents will not be added. -->

## Proposed contract

- **Validator:** `validate` / `validate-facts` / `validate-gov`
- **Severity:** error / warning / info — and why that severity
- **Fires when:** <!-- precise, deterministic condition; no LLM judgement involved -->
- **Message should say:** <!-- what the author needs to fix it, incl. hints -->

## Evidence / grounding

<!-- Spec clause, EA-smells catalogue entry, research finding, or a war story.
     Rules grounded in primary sources get priority (see BLUEPRINT AD-05). -->

## Fixture sketch

<!-- A few YAML lines for eval/fixtures/broken/ that would trigger it. Every rule
     ships as a triple: check + fixture case + RULES.md row (see CONTRIBUTING). -->

```yaml
```

## Checklist

- [ ] Deterministic — decidable from repository content alone, no network, no model judgement
- [ ] Not already covered (checked [docs/RULES.md](../../docs/RULES.md), including "Not yet implemented")
