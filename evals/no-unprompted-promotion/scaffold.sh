#!/usr/bin/env bash
# Seeds the empty eval workspace from this repository's own committed cases, so the
# fixture can never drift from the golden set it is copied out of. Runs only under
# `claude plugin eval --scaffold`, as the operator, before the agent starts.
set -euo pipefail
case_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$case_dir/../.." && pwd)"
gold="$root/eval/golden/clinic"
cp "$gold/ea.config.yaml" .
cp -r "$gold/facts" facts
mkdir -p model/staging model/approved
cp "$gold"/model/approved/*.yaml model/staging/
