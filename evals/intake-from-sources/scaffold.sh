#!/usr/bin/env bash
# Seeds the empty eval workspace from this repository's own committed cases, so the
# fixture can never drift from the golden set it is copied out of. Runs only under
# `claude plugin eval --scaffold`, as the operator, before the agent starts.
set -euo pipefail
case_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$case_dir/../.." && pwd)"
gold="$root/eval/golden/clinic"
mkdir -p facts/sources
cp "$gold/ea.config.yaml" .
cp "$gold"/facts/sources/* facts/sources/
