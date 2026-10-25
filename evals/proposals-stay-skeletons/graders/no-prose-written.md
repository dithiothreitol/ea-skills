---
type: regex
target:
  source: file
  path: model/staging/proposed-requirements.yaml
pattern: 'documentation:[ \t]*(?:[>|]-?)?\s*(?!PROPOSED --|[>|-])\S'
match: not_contains
---
