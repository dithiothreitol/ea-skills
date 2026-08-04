# Negative consumer fixture

A fake product repository, checked against the worked example's EA repository as
`app-erp-core`. Every dependency here exists to fire one `CHK*` rule, so the test suite
can prove `ea-check` catches what the catalogue says it catches:

| Dependency | Rule |
|---|---|
| `@aurorafoods/dc-agent` in `package.json` | `CHK002` — implements the **retired** on-premise hosting standard (as `app-order-portal`, which no dispensation covers) |
| `@aurorafoods/dc-agent` when checked as `app-erp-core` | `CHK004` — the same use, covered by `disp-onprem-legacy` until its expiry |
| `pg` in `services/api/package.json` | `CHK006` — implements `std-postgresql-16`, which the model does not record for this element |
| `broken/package.json` | `CHK000` — a manifest that cannot be parsed |

Nothing here is a real project: no code, no lockfiles, no license. It is fixture data.
