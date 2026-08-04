# Security Policy

## Design posture

This tooling is built to be safe to run in CI on untrusted content:

- **No network at runtime.** Validation, compilation, rendering and reporting never
  fetch anything. XML schema resolution runs with the parser's network access
  disabled, and a test proves that an attempted fetch fails loudly rather than
  silently succeeding on a developer machine.
- **Vendored, hash-pinned rule data.** The semantic oracle (`oracle/`) is verified
  against pinned SHA-256 sums wherever it is consumed: `validate`, `compile`, `render`,
  `docs`, `gen-schema` and `oracle-info` check the pins before using the data
  (`--skip-validation` does not bypass it), and `promote`/`score` inherit the check by
  running the model gate. Drift is an error (`ORACLE001`) and the command refuses, so a
  tampered matrix cannot reach an artifact or a generated schema. Only `pin-oracle`
  rewrites the pins, and it exists for deliberate, reviewed oracle upgrades.
- **No code execution from content.** Model repositories are YAML + Markdown; they
  are parsed with `yaml.safe_load` and never evaluated. Generated outputs (XML, SVG,
  Markdown) are built from sanitized/escaped values.
- **Reads stay inside the repository.** Provenance and evidence references resolve
  against the repository root and are refused if they escape it (`PROV008`/`FACT008`),
  so validation cannot be pointed at files outside the checkout — which would also
  turn a pass/fail into a probe of the runner's filesystem. `factsRoot`/`sourcesDir`
  are held to the same rule (`SCHEMA002`).
- **Malformed content produces findings, not tracebacks.** Configuration and record
  loading never raise on bad values: a gate that crashes reports nothing, which is
  indistinguishable from a gate that found nothing.
- **Deterministic outputs.** Same input, same bytes — which also means a tampered
  artifact is a visible diff, not a mystery.

## Reporting a vulnerability

Please report suspected vulnerabilities privately via
[GitHub Security Advisories](../../security/advisories/new) rather than a public
issue. Include a minimal reproduction (a small model repository triggering the
behaviour is ideal). You can expect an acknowledgement within a week.

## Scope notes

- The agent skills (`skills/*/SKILL.md`) are instructions for LLM agents; treat any model
  repository content as *data*, never as instructions — the skills are written to
  that rule, and deviations from it are in scope as vulnerabilities.
- The vendored oracle files are third-party material (see
  [`oracle/NOTICE.md`](oracle/NOTICE.md)); vulnerabilities in Archi or the Open Group
  schemas themselves should go to their upstreams, but pin-bypass or verification
  weaknesses here are in scope.
