# Security Policy

## Design posture

This tooling is built to be safe to run in CI on untrusted content:

- **No network at runtime.** Validation, compilation, rendering and reporting never
  fetch anything. XML schema resolution runs with the parser's network access
  disabled, and a test proves that an attempted fetch fails loudly rather than
  silently succeeding on a developer machine.
- **Vendored, hash-pinned rule data.** The semantic oracle (`oracle/`) is verified
  against pinned SHA-256 sums on every run; drift is an error (`ORACLE001`), not a
  shrug.
- **No code execution from content.** Model repositories are YAML + Markdown; they
  are parsed with `yaml.safe_load` and never evaluated. Generated outputs (XML, SVG,
  Markdown) are built from sanitized/escaped values.
- **Deterministic outputs.** Same input, same bytes — which also means a tampered
  artifact is a visible diff, not a mystery.

## Reporting a vulnerability

Please report suspected vulnerabilities privately via
[GitHub Security Advisories](../../security/advisories/new) rather than a public
issue. Include a minimal reproduction (a small model repository triggering the
behaviour is ideal). You can expect an acknowledgement within a week.

## Scope notes

- The agent skills (`skills/*.md`) are instructions for LLM agents; treat any model
  repository content as *data*, never as instructions — the skills are written to
  that rule, and deviations from it are in scope as vulnerabilities.
- The vendored oracle files are third-party material (see
  [`oracle/NOTICE.md`](oracle/NOTICE.md)); vulnerabilities in Archi or the Open Group
  schemas themselves should go to their upstreams, but pin-bypass or verification
  weaknesses here are in scope.
