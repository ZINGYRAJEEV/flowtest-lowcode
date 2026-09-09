"""
Run a suite of FlowTest cases sequentially or in parallel.

Uses execute_test_safe so each test stays isolated (Playwright subprocess),
which is Streamlit/Windows-safe even with multiple worker threads.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from flowtest.executor import execute_test_safe
from flowtest.models import Environment, TestCase, TestRun


def _run_one(
    test: TestCase,
    env: Environment | None,
    *,
    headed: bool,
    triggered_by: str,
    trigger: str,
    stop_on_fail: bool,
) -> dict[str, Any]:
    run: TestRun = execute_test_safe(
        test,
        env,
        triggered_by=triggered_by,
        trigger=trigger,
        headless=not headed,
        stop_on_fail=stop_on_fail,
    )
    return {
        "test_id": test.id,
        "test_name": test.name,
        "run_id": run.id,
        "status": run.status,
        "duration_ms": run.duration_ms,
        "error": run.error or "",
    }


def run_suite_tests(
    tests: list[TestCase],
    env: Environment | None,
    *,
    workers: int = 1,
    headed: bool = False,
    continue_on_fail: bool = True,
    triggered_by: str = "runner",
    trigger: str = "suite",
    stop_on_fail: bool = True,
    on_result: Any = None,
) -> dict[str, Any]:
    """
    Execute tests and return a summary:
      total / executed / passed / failed / status / results
    """
    selected = list(tests or [])
    workers = max(1, int(workers or 1))
    results: list[dict[str, Any]] = []
    overall_ok = True

    def _handle(entry: dict[str, Any]) -> None:
        nonlocal overall_ok
        results.append(entry)
        if on_result:
            try:
                on_result(entry)
            except Exception:
                pass
        if entry.get("status") != "PASS":
            overall_ok = False

    if workers == 1 or len(selected) <= 1:
        for test in selected:
            entry = _run_one(
                test,
                env,
                headed=headed,
                triggered_by=triggered_by,
                trigger=trigger,
                stop_on_fail=stop_on_fail,
            )
            _handle(entry)
            if not overall_ok and not continue_on_fail:
                break
    else:
        # Parallel: each execute_test_safe already isolates Playwright
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _run_one,
                    test,
                    env,
                    headed=headed,
                    triggered_by=triggered_by,
                    trigger=trigger,
                    stop_on_fail=stop_on_fail,
                ): test
                for test in selected
            }
            for fut in as_completed(futures):
                try:
                    entry = fut.result()
                except Exception as exc:
                    test = futures[fut]
                    entry = {
                        "test_id": test.id,
                        "test_name": test.name,
                        "run_id": "",
                        "status": "ERROR",
                        "duration_ms": 0,
                        "error": str(exc)[:500],
                    }
                _handle(entry)
                if not overall_ok and not continue_on_fail:
                    for other in futures:
                        other.cancel()
                    break

    # Preserve original suite order in results when possible
    order = {t.id: i for i, t in enumerate(selected)}
    results.sort(key=lambda r: order.get(r.get("test_id", ""), 10_000))

    summary = {
        "total": len(selected),
        "executed": len(results),
        "passed": sum(1 for r in results if r.get("status") == "PASS"),
        "failed": sum(1 for r in results if r.get("status") != "PASS"),
        "status": "PASS" if overall_ok and len(results) == len(selected) else "FAIL",
        "workers": workers,
        "results": results,
    }
    return summary
