#!/usr/bin/env bash
# Seeds the empty eval workspace from this repository's own committed cases, so the
# fixture can never drift from the golden set it is copied out of. Runs only under
# `claude plugin eval --scaffold`, as the operator, before the agent starts.
set -euo pipefail
case_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$case_dir/../.." && pwd)"
# The worked example with its reference mappings removed: every leaf of the pack becomes a
# named gap (ALN004), which is what `propose --from align` turns into skeletons.
cp -r "$root/eval/example/." .
rm -f reference/wholesale-core/mappings.yaml
# An architecture repository is a git repository (the commit is the approval record), and
# the end-of-turn gate check compares the working tree with HEAD.
if command -v git >/dev/null 2>&1; then
  git init -q && git add -A && git -c user.name=eval -c user.email=eval@example.invalid commit -qm "scaffold"
fi
