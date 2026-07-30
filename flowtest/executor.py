"""
FlowTest — execution engine for UI (Playwright), API (httpx), and data steps.
Runs in an isolated process when called from Streamlit on Windows.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from flowtest.models import Environment, StepResult, TestCase, TestRun, TestStep, new_id, utc_now
from flowtest.storage import ARTIFACTS_DIR, save_run

_VAR_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")


def _resolve(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):

        def repl(match: re.Match) -> str:
            key = match.group(1)
            if key in variables:
                return str(variables[key])
            return match.group(0)

        return _VAR_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _resolve(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, variables) for v in value]
    return value


def _json_path(data: Any, path: str) -> Any:
    cur = data
    for part in path.split("."):
        if part == "":
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            cur = cur[int(part)]
        else:
            return None
    return cur


def _compare(op: str, left: int, right: int) -> bool:
    return {
        "eq": left == right,
        "gte": left >= right,
        "lte": left <= right,
        "gt": left > right,
        "lt": left < right,
    }.get(op, left == right)


from flowtest.ui_actions import (
    DEFAULT_UI_TIMEOUT_MS,
    settle_page as _settle_page,
    smart_assert_text as _smart_assert_text,
    smart_click as _smart_click,
    smart_click_by_text as _smart_click_by_text,
    smart_fill as _smart_fill,
    smart_select as _smart_select,
    smart_select_by_text as _smart_select_by_text,
    smart_wait_for as _smart_wait_for,
    ui_timeout as _ui_timeout,
)


def _run_sql(dsn: str, sql: str) -> list[dict[str, Any]]:
    if dsn.startswith("sqlite:///"):
        path = dsn.replace("sqlite:///", "", 1)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql)
        if cur.description is None:
            conn.commit()
            conn.close()
            return []
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    # Optional drivers for Postgres/MySQL
    if dsn.startswith("postgresql://") or dsn.startswith("postgres://"):
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(dsn)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql)
        rows = [dict(r) for r in cur.fetchall()] if cur.description else []
        conn.commit()
        cur.close()
        conn.close()
        return rows
    if dsn.startswith("mysql://") or dsn.startswith("mysql+pymysql://"):
        import pymysql

        # mysql://user:pass@host/db
        from urllib.parse import urlparse

        u = urlparse(dsn.replace("mysql+pymysql://", "mysql://"))
        conn = pymysql.connect(
            host=u.hostname or "localhost",
            user=u.username or "root",
            password=u.password or "",
            database=(u.path or "/").lstrip("/"),
            port=u.port or 3306,
            cursorclass=pymysql.cursors.DictCursor,
        )
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = list(cur.fetchall()) if cur.description else []
        conn.commit()
        conn.close()
        return rows
    raise RuntimeError(f"Unsupported DSN scheme: {dsn}")


def execute_test_case(
    test: TestCase,
    environment: Environment | None,
    triggered_by: str = "system",
    trigger: str = "manual",
    headless: bool = True,
    stop_on_fail: bool = True,
) -> TestRun:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    run = TestRun(
        id=new_id("run_"),
        test_id=test.id,
        test_name=test.name,
        project_id=test.project_id,
        environment_id=environment.id if environment else "",
        environment_name=environment.name if environment else "None",
        status="RUNNING",
        triggered_by=triggered_by,
        trigger=trigger,
    )

    variables: dict[str, Any] = {}
    if environment:
        variables.update(environment.variables or {})
        variables["BASE_URL"] = environment.base_url or variables.get("BASE_URL", "")
        if "API_BASE" not in variables and environment.base_url:
            variables["API_BASE"] = environment.base_url

    t0 = time.perf_counter()
    browser = None
    page = None
    context = None
    needs_browser = any(s.type.startswith("ui.") or s.type.startswith("assert.title") or s.type.startswith("assert.element") or s.type.startswith("assert.text") or s.type == "util.custom_js" for s in test.steps if s.enabled)

    try:
        if needs_browser:
            from playwright.sync_api import sync_playwright

            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=headless)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()
            page.set_default_timeout(DEFAULT_UI_TIMEOUT_MS)
            page.set_default_navigation_timeout(DEFAULT_UI_TIMEOUT_MS)
        else:
            pw = None

        for step in test.steps:
            if not step.enabled:
                run.step_results.append(
                    StepResult(step.id, step.name, step.type, "SKIP", "Step disabled")
                )
                continue
            result = _execute_step(step, variables, page)
            run.step_results.append(result)
            if result.status == "FAIL" and stop_on_fail:
                run.status = "FAIL"
                break
        else:
            if any(s.status == "FAIL" for s in run.step_results):
                run.status = "FAIL"
            else:
                run.status = "PASS"

    except Exception as exc:
        run.status = "ERROR"
        run.error = str(exc)[:800]
    finally:
        try:
            if browser:
                browser.close()
            if needs_browser and "pw" in locals() and pw:
                pw.stop()
        except Exception:
            pass

    run.finished_at = utc_now()
    run.duration_ms = int((time.perf_counter() - t0) * 1000)
    save_run(run)
    return run


def _execute_step(step: TestStep, variables: dict[str, Any], page) -> StepResult:
    cfg = _resolve(step.config or {}, variables)
    t0 = time.perf_counter()
    try:
        stype = step.type
        detail = "OK"
        screenshot = ""
        extras: dict[str, Any] = {}

        if stype == "ui.goto":
            url = cfg.get("url") or variables.get("BASE_URL") or ""
            if not url:
                raise RuntimeError("URL is empty")
            if page is None:
                raise RuntimeError("Browser not available")
            timeout = _ui_timeout(cfg)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            _settle_page(page, ms=400)
            detail = f"Opened {page.url}"

        elif stype == "ui.click":
            if page is None:
                raise RuntimeError("Browser not available")
            selector = cfg.get("selector") or ""
            text = cfg.get("text") or ""
            detail = _smart_click(
                page,
                selector=selector,
                text=text,
                timeout=_ui_timeout(cfg),
                cfg=cfg,
                step_name=step.name or "",
            )
            page.wait_for_timeout(150)

        elif stype == "ui.click_by_text":
            if page is None:
                raise RuntimeError("Browser not available")
            detail = _smart_click_by_text(
                page,
                text=str(cfg.get("text") or ""),
                exact=bool(cfg.get("exact", False)),
                role=str(cfg.get("role") or ""),
                within=str(cfg.get("within") or ""),
                timeout=_ui_timeout(cfg),
            )
            page.wait_for_timeout(150)

        elif stype == "ui.fill":
            if page is None:
                raise RuntimeError("Browser not available")
            selector = cfg.get("selector") or ""
            value = str(cfg.get("value", ""))
            clear = bool(cfg.get("clear", True))
            detail = _smart_fill(
                page,
                selector=selector,
                value=value,
                clear=clear,
                timeout=_ui_timeout(cfg),
                cfg=cfg,
                step_name=step.name or "",
            )

        elif stype == "ui.select":
            if page is None:
                raise RuntimeError("Browser not available")
            selector = cfg.get("selector") or ""
            label = cfg.get("label") or ""
            # Prefer label over index when both present (order-safe)
            if label:
                detail = _smart_select_by_text(
                    page,
                    text=str(label),
                    selector=selector,
                    exact=False,
                    timeout=_ui_timeout(cfg),
                )
            else:
                idx = int(cfg.get("index", 1))
                detail = _smart_select(
                    page,
                    selector=selector,
                    label=label,
                    index=idx,
                    timeout=_ui_timeout(cfg),
                    cfg=cfg,
                    step_name=step.name or "",
                )

        elif stype == "ui.select_by_text":
            if page is None:
                raise RuntimeError("Browser not available")
            detail = _smart_select_by_text(
                page,
                text=str(cfg.get("text") or cfg.get("label") or ""),
                selector=str(cfg.get("selector") or ""),
                exact=bool(cfg.get("exact", False)),
                timeout=_ui_timeout(cfg),
            )
            page.wait_for_timeout(150)

        elif stype == "ui.wait":
            ms = int(cfg.get("ms", 1000))
            if page:
                page.wait_for_timeout(ms)
            else:
                time.sleep(ms / 1000)
            detail = f"Waited {ms}ms"

        elif stype == "ui.wait_for":
            if page is None:
                raise RuntimeError("Browser not available")
            selector = cfg.get("selector") or ""
            timeout = _ui_timeout(cfg, default=30000)
            state = (cfg.get("state") or "attached").strip() or "attached"
            detail = _smart_wait_for(
                page,
                selector=selector,
                timeout=timeout,
                state=state,
                cfg=cfg,
                step_name=step.name or "",
            )

        elif stype == "ui.screenshot":
            if page is None:
                raise RuntimeError("Browser not available")
            label = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(cfg.get("label", "shot")))
            path = ARTIFACTS_DIR / f"{label}_{int(time.time())}.png"
            page.screenshot(path=str(path))
            screenshot = str(path)
            detail = f"Saved {path.name}"

        elif stype == "api.request":
            import httpx

            method = (cfg.get("method") or "GET").upper()
            url = cfg.get("url") or ""
            headers = cfg.get("headers") or {}
            if isinstance(headers, str):
                headers = json.loads(headers or "{}")
            body = cfg.get("body") or None
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                resp = client.request(method, url, headers=headers, content=body if body else None)
            save_as = cfg.get("save_as") or "last_response"
            try:
                body_json = resp.json()
            except Exception:
                body_json = None
            variables[save_as] = {
                "status": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp.text[:5000],
                "json": body_json,
            }
            detail = f"{method} {url} → {resp.status_code}"
            extras["status"] = resp.status_code

        elif stype == "assert.title_contains":
            if page is None:
                raise RuntimeError("Browser not available")
            text = str(cfg.get("text", ""))
            title = page.title()
            if text not in title:
                raise AssertionError(f'Title "{title}" does not contain "{text}"')
            detail = f'Title OK: "{title}"'

        elif stype == "assert.element_exists":
            if page is None:
                raise RuntimeError("Browser not available")
            selector = cfg.get("selector") or ""
            timeout = _ui_timeout(cfg)
            detail = _smart_wait_for(
                page,
                selector=selector,
                timeout=timeout,
                state="attached",
                cfg=cfg,
                step_name=step.name or "",
            )

        elif stype == "assert.text_contains":
            if page is None:
                raise RuntimeError("Browser not available")
            selector = cfg.get("selector") or "body"
            text = str(cfg.get("text", ""))
            timeout = _ui_timeout(cfg)
            ignore_case = bool(cfg.get("ignore_case", True))
            detail = _smart_assert_text(
                page,
                text=text,
                selector=selector,
                timeout=timeout,
                ignore_case=ignore_case,
            )

        elif stype == "assert.api_status":
            save_as = cfg.get("save_as") or "last_response"
            expected = int(cfg.get("status", 200))
            resp = variables.get(save_as)
            if not isinstance(resp, dict):
                raise AssertionError(f"No response stored as {save_as}")
            actual = int(resp.get("status", 0))
            if actual != expected:
                raise AssertionError(f"Expected status {expected}, got {actual}")
            detail = f"Status {actual}"

        elif stype == "assert.json_path":
            save_as = cfg.get("save_as") or "last_response"
            path = cfg.get("path") or ""
            expected = str(cfg.get("equals", ""))
            resp = variables.get(save_as)
            if not isinstance(resp, dict):
                raise AssertionError(f"No response stored as {save_as}")
            data = resp.get("json")
            actual = _json_path(data, path)
            if str(actual) != expected:
                raise AssertionError(f"Path {path}: expected '{expected}', got '{actual}'")
            detail = f"{path} == {expected}"

        elif stype == "data.sql_query":
            dsn = cfg.get("dsn") or ""
            sql = cfg.get("sql") or ""
            rows = _run_sql(dsn, sql)
            save_as = cfg.get("save_as") or "query_rows"
            variables[save_as] = rows
            detail = f"{len(rows)} row(s) saved as {save_as}"
            extras["row_count"] = len(rows)

        elif stype == "assert.row_count":
            save_as = cfg.get("save_as") or "query_rows"
            rows = variables.get(save_as) or []
            count = len(rows) if isinstance(rows, list) else 0
            expected = int(cfg.get("count", 0))
            op = cfg.get("op") or "eq"
            if not _compare(op, count, expected):
                raise AssertionError(f"Row count {count} not {op} {expected}")
            detail = f"Row count {count} {op} {expected}"

        elif stype == "data.compare_counts":
            source = variables.get(cfg.get("source") or "") or []
            target = variables.get(cfg.get("target") or "") or []
            sc = len(source) if isinstance(source, list) else 0
            tc = len(target) if isinstance(target, list) else 0
            if sc != tc:
                raise AssertionError(f"Source count {sc} != target count {tc}")
            detail = f"Counts match ({sc})"

        elif stype == "flow.set_var":
            name = cfg.get("name") or "var"
            variables[name] = cfg.get("value", "")
            detail = f"Set {name}"

        elif stype == "util.comment":
            detail = str(cfg.get("text", ""))[:200] or "Comment"

        elif stype == "util.custom_js":
            if page is None:
                raise RuntimeError("Browser not available")
            script = cfg.get("script") or "null"
            result = page.evaluate(script)
            save_as = cfg.get("save_as") or "js_result"
            variables[save_as] = result
            detail = f"JS → {str(result)[:120]}"

        else:
            raise RuntimeError(f"Unknown step type: {stype}")

        # Auto screenshot on UI assert failure handled below
        return StepResult(
            step_id=step.id,
            step_name=step.name,
            step_type=step.type,
            status="PASS",
            detail=detail,
            duration_ms=int((time.perf_counter() - t0) * 1000),
            screenshot=screenshot,
            extras=extras,
        )
    except Exception as exc:
        shot = ""
        if page is not None:
            try:
                path = ARTIFACTS_DIR / f"fail_{step.id}_{int(time.time())}.png"
                page.screenshot(path=str(path))
                shot = str(path)
            except Exception:
                pass
        return StepResult(
            step_id=step.id,
            step_name=step.name,
            step_type=step.type,
            status="FAIL",
            detail=str(exc)[:500],
            duration_ms=int((time.perf_counter() - t0) * 1000),
            screenshot=shot,
        )


def _execute_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Picklable entrypoint for process pool."""
    from flowtest.models import Environment, TestCase, TestStep

    test_data = payload["test"]
    steps = [TestStep(**s) for s in test_data["steps"]]
    test = TestCase(
        id=test_data["id"],
        project_id=test_data["project_id"],
        name=test_data["name"],
        description=test_data.get("description", ""),
        tags=test_data.get("tags", []),
        steps=steps,
        suite=test_data.get("suite", "Default"),
        version=test_data.get("version", 1),
        created_by=test_data.get("created_by", ""),
    )
    env = None
    if payload.get("environment"):
        e = payload["environment"]
        env = Environment(e["id"], e["name"], e.get("base_url", ""), e.get("variables", {}))
    run = execute_test_case(
        test,
        env,
        triggered_by=payload.get("triggered_by", "system"),
        trigger=payload.get("trigger", "manual"),
        headless=payload.get("headless", True),
        stop_on_fail=payload.get("stop_on_fail", True),
    )
    return run.to_dict()


def execute_test_safe(
    test: TestCase,
    environment: Environment | None,
    triggered_by: str = "system",
    trigger: str = "manual",
    headless: bool = True,
    stop_on_fail: bool = True,
    timeout: int = 300,
) -> TestRun:
    """Execute in a subprocess (Streamlit/Windows safe — avoids re-importing app.py)."""
    import json
    import os
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    payload = {
        "test": test.to_dict(),
        "environment": environment.to_dict() if environment else None,
        "triggered_by": triggered_by,
        "trigger": trigger,
        "headless": headless,
        "stop_on_fail": stop_on_fail,
    }

    with tempfile.TemporaryDirectory(prefix="flowtest_run_") as tmp:
        tmp_path = Path(tmp)
        in_path = tmp_path / "in.json"
        out_path = tmp_path / "out.json"
        in_path.write_text(json.dumps(payload), encoding="utf-8")
        env = dict(os.environ)
        py_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(root) + ((";" + py_path) if py_path else "")
        proc = subprocess.run(
            [sys.executable, "-m", "flowtest.executor_job", str(in_path), str(out_path)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if not out_path.exists():
            raise RuntimeError((proc.stderr or proc.stdout or f"exit {proc.returncode}").strip())
        data = json.loads(out_path.read_text(encoding="utf-8"))
        if data.get("error") and "id" not in data:
            raise RuntimeError(data.get("error") or "Execution failed")

    from flowtest.storage import get_run

    saved = get_run(data["id"])
    if saved:
        return saved
    steps = [StepResult(**s) for s in data.get("step_results", [])]
    return TestRun(
        id=data["id"],
        test_id=data["test_id"],
        test_name=data["test_name"],
        project_id=data["project_id"],
        environment_id=data.get("environment_id", ""),
        environment_name=data.get("environment_name", ""),
        status=data["status"],
        triggered_by=data.get("triggered_by", ""),
        started_at=data.get("started_at", ""),
        finished_at=data.get("finished_at", ""),
        duration_ms=data.get("duration_ms", 0),
        step_results=steps,
        error=data.get("error", ""),
        trigger=data.get("trigger", "manual"),
    )
