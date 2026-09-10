# AI-generated code verification (FlowTest)

FlowTest helps close the gap described in analyses like the **1.80× bug multiplier**: AI code often *fails politely* (looks fine, breaks guarantees), while humans skim diffs instead of verifying behavior — and when AI writes both code and tests, you get **generative ratification**.

## Goals

1. **Independent oracles** — golden-path suites humans own (or at least review).
2. **Failure Truthfulness** — reject empty success, soft error banners, HTTP 200 + empty body.
3. **Agent loop** — coding agents must run `verify_suite` / `verify-gate` before claiming done.
4. **Evidence** — Allure/HTML report + gate JSON artifact on every gate run.

## New step types (Test Builder → **AI / Verify**)

| Step | Purpose |
|------|---------|
| `verify.invariant` | JS expression must be truthy |
| `verify.page_truth` | Reject empty shell / soft-error phrases on page |
| `verify.not_empty` | Variable must be non-empty (optional JSON path) |
| `verify.api_truthful` | Success HTTP must carry a real payload / required fields |
| `verify.intent_table` | Table-driven JS cases — catch intent inversion |

Severity `hard` → step **FAIL** (blocks run). Severity `soft` → step **WARN** (run can still PASS; gate reports `PASS_WITH_WARNINGS`).

## Golden suite

Bundled at:

`tests/flowtest/ai-verify/suite.json`

Uses `example.org` (`BASE_URL`) as a stable demo. **Replace / extend** with your product’s critical journeys (login, checkout, core API).

## CLI gate

```bash
python -m flowtest.cli verify-gate --env-name "Example Org"
python -m flowtest.cli verify-gate --path tests/flowtest/ai-verify/suite.json --workers 2 --continue-on-fail
python -m flowtest.cli verify-gate --diff-file pr.diff --scan path/to/changed.py --fail-on-warn
```

Exit codes: `0` = PASS (or warnings unless `--fail-on-warn`), `1` = FAIL, `2` = usage/config error.

## MCP (Cursor agents)

| Tool | Use |
|------|-----|
| `ai_verify_checklist` | Human-in-the-loop checklist |
| `scan_ai_diff` | Heuristic polite-failure scan on diff/files |
| `verify_suite` | Run golden suite + soft-fail scan; returns gate + report paths |

Agent rule of thumb: **implement → `verify_suite` → attach report → only then say done.**

## UI

**AI Verify** page: checklist, soft-fail scan paste, run gate against a suite file or DB suite.

## CI

See `scripts/ci_ai_verify_gate.sh` and `scripts/ci_ai_verify_gate.ps1`.

## Anti-patterns this does *not* replace

- Unit tests for pure domain logic (keep the pyramid — don’t invert it onto E2E only).
- Security review / SAST for path traversal and injection.
- Human ownership of business oracles in regulated environments.
