#!/usr/bin/env bash
# CI gate: verify AI-touched changes with FlowTest golden suite.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

SUITE="${FLOWTEST_VERIFY_SUITE:-tests/flowtest/ai-verify/suite.json}"
ENV_NAME="${FLOWTEST_VERIFY_ENV:-Example Org}"
EXTRA=()
if [[ -n "${FLOWTEST_DIFF_FILE:-}" ]]; then
  EXTRA+=(--diff-file "$FLOWTEST_DIFF_FILE")
fi
if [[ "${FLOWTEST_FAIL_ON_WARN:-}" == "1" ]]; then
  EXTRA+=(--fail-on-warn)
fi

python -m flowtest.cli verify-gate \
  --path "$SUITE" \
  --env-name "$ENV_NAME" \
  --workers "${FLOWTEST_VERIFY_WORKERS:-2}" \
  --continue-on-fail \
  "${EXTRA[@]}"
