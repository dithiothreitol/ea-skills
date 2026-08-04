---
name: Bug report
about: A gate, command or skill behaves differently than documented
title: "[bug] "
labels: bug
---

## What happened

<!-- The command you ran, on which repository (eval/example reproduces best), and
     the output you got. Paste the finding lines verbatim -- codes matter. -->

## What you expected

<!-- Quote docs/RULES.md, docs/CLI.md or a SKILL.md if the documented behaviour
     differs from the observed one. -->

## Minimal reproduction

<!-- Ideally: the smallest model-repository fragment (a few YAML lines) that
     triggers it. If eval/example or eval/fixtures/broken reproduces it, say so
     and skip this. -->

```yaml
```

## Environment

- OS:
- Python:
- Commit / version:

## Checklist

- [ ] `python -m pytest tests -q` passes on my checkout (i.e. the bug is not a local setup issue)
- [ ] Not a security issue (those go to a [private advisory](https://github.com/dithiothreitol/ea-skills/security/advisories/new))
