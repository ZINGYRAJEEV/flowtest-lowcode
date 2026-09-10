"""
AI-generated code verification helpers for FlowTest.

Addresses the "1.80x bug multiplier" risks:
- polite / soft failures (surface success, broken guarantees)
- vanishing human verification (agent must run real checks)
- generative ratification (independent oracles + human checklist)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from flowtest.models import Environment, TestCase, TestRun, utc_now
from flowtest.storage import DATA_DIR, get_run
from flowtest.suite_runner import run_suite_tests

DEFAULT_GOLDEN_SUITE = (
    Path(__file__).resolve().parent.parent / "tests" / "flowtest" / "ai-verify" / "suite.json"
)

# Patterns that often encode "polite" failures in AI-authored Python
SOFT_FAIL_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"except\s*:\s*(?:pass|return\s+(?:None|False|\{\}|\[\]|\"\"|\'\'))",
        "bare_except_swallow",
        "Bare except that swallows errors — classic polite failure.",
    ),
    (
        r"except\s+Exception(?:\s+as\s+\w+)?\s*:\s*(?:pass|return\s+(?:None|False|\{\}|\[\]))",
        "broad_except_swallow",
        "Broad Exception handler returns empty/False — conceals broken guarantees.",
    ),
    (
        r"except\s+Exception(?:\s+as\s+\w+)?\s*:\s*return\s+\{\}",
        "except_return_empty_dict",
        "Exception path returns {} — callers may treat as success.",
    ),
    (
        r"return\s+True\s*(?:#.*)?$",
        "unconditional_true",
        "Unconditional True return can hide failed preconditions (review context).",
    ),
    (
        r"except\s+.*:\s*\n\s*logger\.(?:debug|info|warning)\([^)]*\)\s*\n\s*return",
        "log_and_return",
        "Log-and-return on exception — Failure Truthfulness risk.",
    ),
]


AGENT_VERIFY_INSTRUCTIONS = """
After changing application code with AI assistance:
1. Do NOT mark the task done based on a skimmed diff alone.
2. Run FlowTest MCP `verify_suite` (or CLI `verify-gate`) against the golden-path suite for this app.
3. If you authored new tests in the same turn, have a human (or a second review) confirm assertions/oracles.
4. Attach the Allure/HTML report path from the verification summary to the PR.
5. Soft-fail scan findings (WARN) must be acknowledged; hard FAIL blocks merge.
""".strip()


def verification_checklist() -> list[dict[str, str]]:
    """Human-in-the-loop checklist — independent of AI-authored tests."""
    return [
        {
            "id": "oracle_owned",
            "title": "Oracle ownership",
            "detail": "At least one assertion/oracle was written or edited by a human (not only the coding agent).",
        },
        {
            "id": "intent_table",
            "title": "Intent table",
            "detail": "Critical logic has table-driven or property checks (known inputs → expected outputs).",
        },
        {
            "id": "failure_truth",
            "title": "Failure Truthfulness",
            "detail": "Error paths raise or return explicit failure — no empty success / bare except swallow.",
        },
        {
            "id": "golden_path_run",
            "title": "Golden path run",
            "detail": "FlowTest (or equivalent) ran the real UI/API journey for changed behavior.",
        },
        {
            "id": "no_self_grade",
            "title": "No generative ratification",
            "detail": "Production code and its sole proof were not both invented in one unreviewed agent turn.",
        },
        {
            "id": "reuse_patterns",
            "title": "Reuse over duplication",
            "detail": "Change reuses existing helpers/abstractions instead of inventing near-duplicates.",
        },
    ]


def scan_text_for_soft_fails(text: str, *, source: str = "diff") -> list[dict[str, Any]]:
    """Heuristic scan for polite-failure patterns in a diff or file contents."""
    findings: list[dict[str, Any]] = []
    if not text:
        return findings
    for pattern, code, message in SOFT_FAIL_PATTERNS:
        for m in re.finditer(pattern, text, flags=re.M | re.I):
            line = text.count("\n", 0, m.start()) + 1
            findings.append(
                {
                    "code": code,
                    "severity": "warn",
                    "message": message,
                    "source": source,
                    "line": line,
                    "snippet": (m.group(0) or "")[:160].replace("\n", " "),
                }
            )
    return findings


def scan_paths_for_soft_fails(paths: list[str | Path]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for p in paths:
        path = Path(p)
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        findings.extend(scan_text_for_soft_fails(text, source=str(path)))
    return findings


def summarize_run_truthfulness(run: TestRun) -> dict[str, Any]:
    """Inspect a finished run for soft vs hard outcomes."""
    steps = run.step_results or []
    hard_fails = [s for s in steps if s.status == "FAIL"]
    soft_warns = [s for s in steps if s.status == "WARN"]
    skipped = [s for s in steps if s.status == "SKIP"]
    return {
        "run_id": run.id,
        "test_name": run.test_name,
        "status": run.status,
        "hard_fails": len(hard_fails),
        "soft_warns": len(soft_warns),
        "skipped": len(skipped),
        "passed": sum(1 for s in steps if s.status == "PASS"),
        "failure_truthfulness": "broken" if hard_fails else ("degraded" if soft_warns else "ok"),
        "fail_details": [
            {"step": s.step_name, "type": s.step_type, "detail": (s.detail or "")[:240]}
            for s in hard_fails[:10]
        ],
        "warn_details": [
            {"step": s.step_name, "type": s.step_type, "detail": (s.detail or "")[:240]}
            for s in soft_warns[:10]
        ],
    }


def build_gate_verdict(
    suite_summary: dict[str, Any],
    *,
    soft_findings: list[dict[str, Any]] | None = None,
    runs: list[TestRun] | None = None,
) -> dict[str, Any]:
    """Merge suite execution + static soft-fail scan into a CI/agent verdict."""
    soft_findings = soft_findings or []
    run_truth = [summarize_run_truthfulness(r) for r in (runs or [])]
    hard_failed = suite_summary.get("status") != "PASS" or any(
        t.get("hard_fails", 0) > 0 for t in run_truth
    )
    warn_count = len(soft_findings) + sum(t.get("soft_warns", 0) for t in run_truth)
    if hard_failed:
        gate = "FAIL"
    elif warn_count:
        gate = "PASS_WITH_WARNINGS"
    else:
        gate = "PASS"

    allure_dir = suite_summary.get("allure_dir")
    report_html = suite_summary.get("report_html")
    return {
        "gate": gate,
        "ok_to_merge": gate != "FAIL",
        "suite": suite_summary,
        "soft_fail_findings": soft_findings[:50],
        "soft_fail_count": len(soft_findings),
        "run_truthfulness": run_truth,
        "checklist": verification_checklist(),
        "agent_instructions": AGENT_VERIFY_INSTRUCTIONS,
        "allure_dir": allure_dir,
        "report_html": report_html,
        "generated_at": utc_now(),
    }


def run_verify_gate(
    tests: list[TestCase],
    env: Environment | None,
    *,
    workers: int = 1,
    headed: bool = False,
    continue_on_fail: bool = True,
    diff_text: str = "",
    scan_paths: list[str] | None = None,
    triggered_by: str = "ai-verify",
    trigger: str = "verify-gate",
) -> dict[str, Any]:
    """Execute golden-path suite + optional soft-fail scans; return gate verdict."""
    summary = run_suite_tests(
        tests,
        env,
        workers=workers,
        headed=headed,
        continue_on_fail=continue_on_fail,
        triggered_by=triggered_by,
        trigger=trigger,
    )

    runs: list[TestRun] = []
    for entry in summary.get("results") or []:
        rid = entry.get("run_id")
        if rid:
            r = get_run(rid)
            if r:
                runs.append(r)

    # Suite-level Allure (best effort)
    try:
        from flowtest.allure_report import write_suite_allure

        if runs:
            report_dir = write_suite_allure(
                summary,
                runs,
                label="ai_verify_gate",
            )
            summary["allure_dir"] = str(report_dir)
            summary["report_html"] = str(report_dir / "report.html")
    except Exception as exc:
        summary["allure_error"] = str(exc)[:300]

    soft: list[dict[str, Any]] = []
    if diff_text:
        soft.extend(scan_text_for_soft_fails(diff_text, source="diff"))
    if scan_paths:
        soft.extend(scan_paths_for_soft_fails(scan_paths))

    return build_gate_verdict(summary, soft_findings=soft, runs=runs)


def write_gate_artifact(verdict: dict[str, Any], path: Path | None = None) -> Path:
    """Persist verdict JSON for CI / PR attachments."""
    import json

    out = path or (DATA_DIR / "ai-verify" / f"gate_{utc_now().replace(':', '')}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    return out
