# Positive consumer fixture

A fake product repository that passes `ea-check` as `app-order-portal`: nothing it
declares implements a deprecated or retired standard, and its one governed dependency
(`pg` → `std-postgresql-16`, active) is reported as `CHK006` — information the model
should absorb, not a violation.

Checked as `app-erp-core` instead, the same repository fires `CHK005`: that element
*claims* the on-premise hosting standard, and nothing here evidences it.
