"""
Pure helpers used by the FlowTest MCP server (easy to unit-test without MCP runtime).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flowtest.executor import execute_test_safe
from flowtest.models import TestCase, TestStep, new_id, utc_now
from flowtest.recording_import import parse_recording_payload, parse_recording_text
from flowtest.storage import (
    add_audit,
    get_environment,
    get_project,
    get_run,
    get_test,
    init_db,
    list_environments,
    list_projects,
    list_runs,
    list_tests,
    save_test,
)
from flowtest.suite_io import export_suite_to_files


def _ensure_db() -> None:
    init_db()


def tool_list_projects() -> list[dict[str, Any]]:
    _ensure_db()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "tags": p.tags,
        }
        for p in list_projects()
    ]


def tool_list_environments() -> list[dict[str, Any]]:
    _ensure_db()
    return [
        {
            "id": e.id,
            "name": e.name,
            "base_url": e.base_url,
            "variables": e.variables,
        }
        for e in list_environments()
    ]


def tool_list_tests(project_id: str | None = None, suite: str | None = None) -> list[dict[str, Any]]:
    _ensure_db()
    tests = list_tests(project_id or None)
    if suite:
        tests = [t for t in tests if t.suite == suite]
    projects = {p.id: p.name for p in list_projects()}
    return [
        {
            "id": t.id,
            "name": t.name,
            "suite": t.suite,
            "project_id": t.project_id,
            "project_name": projects.get(t.project_id, ""),
            "steps": len(t.steps),
            "tags": t.tags,
            "version": t.version,
            "updated_at": t.updated_at,
        }
        for t in tests
    ]


def tool_list_suites(project_id: str | None = None) -> list[dict[str, Any]]:
    _ensure_db()
    tests = list_tests(project_id or None)
    projects = {p.id: p.name for p in list_projects()}
    counts: dict[tuple[str, str], int] = {}
    for t in tests:
        key = (t.project_id, t.suite)
        counts[key] = counts.get(key, 0) + 1
    return [
        {
            "project_id": pid,
            "project_name": projects.get(pid, ""),
            "suite": suite,
            "test_count": count,
        }
        for (pid, suite), count in sorted(counts.items(), key=lambda x: (projects.get(x[0][0], ""), x[0][1]))
    ]


def tool_get_test(test_id: str) -> dict[str, Any]:
    _ensure_db()
    test = get_test(test_id)
    if not test:
        return {"error": f"Test not found: {test_id}"}
    project = get_project(test.project_id)
    data = test.to_dict()
    data["project_name"] = project.name if project else ""
    return data


def tool_list_runs(limit: int = 20, project_id: str | None = None) -> list[dict[str, Any]]:
    _ensure_db()
    runs = list_runs(limit=max(1, min(int(limit), 100)), project_id=project_id or None)
    return [
        {
            "id": r.id,
            "test_id": r.test_id,
            "test_name": r.test_name,
            "status": r.status,
            "environment_name": r.environment_name,
            "duration_ms": r.duration_ms,
            "started_at": r.started_at,
            "error": r.error,
            "trigger": r.trigger,
        }
        for r in runs
    ]


def tool_get_run(run_id: str) -> dict[str, Any]:
    _ensure_db()
    run = get_run(run_id)
    if not run:
        return {"error": f"Run not found: {run_id}"}
    return run.to_dict()


def tool_run_test(
    test_id: str,
    env_name: str | None = None,
    env_id: str | None = None,
    headless: bool = True,
    triggered_by: str = "mcp",
) -> dict[str, Any]:
    _ensure_db()
    test = get_test(test_id)
    if not test:
        return {"error": f"Test not found: {test_id}"}

    env = None
    if env_id:
        env = get_environment(env_id)
    elif env_name:
        env = next((e for e in list_environments() if e.name == env_name), None)
        if env_name and not env:
            return {"error": f"Environment not found: {env_name}"}

    run = execute_test_safe(
        test,
        env,
        triggered_by=triggered_by,
        trigger="mcp",
        headless=headless,
    )
    add_audit(triggered_by, "run", "test", test.id, f"mcp → {run.status}")
    return {
        "id": run.id,
        "test_id": run.test_id,
        "test_name": run.test_name,
        "status": run.status,
        "duration_ms": run.duration_ms,
        "error": run.error,
        "environment_name": run.environment_name,
        "step_results": [
            {
                "step_id": s.step_id,
                "step_name": s.step_name,
                "step_type": s.step_type,
                "status": s.status,
                "detail": s.detail,
                "duration_ms": s.duration_ms,
            }
            for s in run.step_results
        ],
    }


def tool_import_recording(
    recording_json: str,
    project_id: str,
    test_name: str = "Imported recording",
    suite: str = "Recorded",
    mode: str = "create",
    test_id: str | None = None,
    replace_base_url: str | None = None,
) -> dict[str, Any]:
    """
    Import Chrome-extension / recorder JSON into a FlowTest case.

    mode:
      - create: always create a new test
      - append: append steps to existing test_id
      - replace: replace steps on existing test_id
    """
    _ensure_db()
    project = get_project(project_id)
    if not project:
        return {"error": f"Project not found: {project_id}"}

    try:
        steps = parse_recording_text(recording_json, replace_base_url=replace_base_url)
    except Exception as exc:
        # Allow raw object already parsed as string of events/steps
        try:
            data = json.loads(recording_json)
            steps = parse_recording_payload(data, replace_base_url=replace_base_url)
        except Exception:
            return {"error": f"Invalid recording JSON: {exc}"}

    if not steps:
        return {"error": "No steps found in recording"}

    mode = (mode or "create").lower().strip()
    if mode in ("append", "replace"):
        if not test_id:
            return {"error": "test_id is required for append/replace"}
        existing = get_test(test_id)
        if not existing:
            return {"error": f"Test not found: {test_id}"}
        if mode == "replace":
            existing.steps = steps
        else:
            existing.steps.extend(steps)
        existing.updated_at = utc_now()
        save_test(existing, bump_version=True)
        add_audit("mcp", "import_recording", "test", existing.id, f"{mode} {len(steps)} steps")
        return {
            "ok": True,
            "mode": mode,
            "test_id": existing.id,
            "name": existing.name,
            "steps": len(existing.steps),
            "imported_steps": len(steps),
        }

    test = TestCase(
        id=new_id("tst_"),
        project_id=project_id,
        name=test_name or "Imported recording",
        description="Imported via FlowTest MCP from Chrome extension / recorder JSON.",
        tags=["recorded", "mcp"],
        steps=steps,
        suite=suite or "Recorded",
        created_by="mcp",
    )
    save_test(test, bump_version=False)
    add_audit("mcp", "import_recording", "test", test.id, f"create {len(steps)} steps")
    return {
        "ok": True,
        "mode": "create",
        "test_id": test.id,
        "name": test.name,
        "suite": test.suite,
        "steps": len(test.steps),
        "imported_steps": len(steps),
    }


def tool_export_suite(
    suite: str,
    project_id: str | None = None,
    project_name: str | None = None,
    env_name: str = "",
) -> dict[str, Any]:
    _ensure_db()
    projects = list_projects()
    project = None
    if project_id:
        project = get_project(project_id)
    elif project_name:
        project = next((p for p in projects if p.name == project_name), None)
    if not project and len(projects) == 1:
        project = projects[0]
    if not project:
        return {"error": "Specify project_id or project_name (or keep a single project)."}

    selected = [t for t in list_tests(project.id) if t.suite == suite]
    if not selected:
        return {"error": f"No tests found for suite '{suite}' in project '{project.name}'"}

    path = export_suite_to_files(
        project_name=project.name,
        suite=suite,
        tests=selected,
        environment_name=env_name or "",
        project_id=project.id,
    )
    return {
        "ok": True,
        "path": str(path),
        "project_id": project.id,
        "project_name": project.name,
        "suite": suite,
        "tests": len(selected),
    }


def tool_list_suite_files() -> list[dict[str, Any]]:
    """List suite.json files under tests/."""
    root = Path(__file__).resolve().parent.parent / "tests"
    if not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(root.rglob("suite.json")):
        rel = path.relative_to(root).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append(
                {
                    "path": str(path),
                    "relative": rel,
                    "project": data.get("project") or data.get("project_name") or "",
                    "suite": data.get("suite") or "",
                    "tests": len(data.get("tests") or []),
                }
            )
        except Exception as exc:
            out.append({"path": str(path), "relative": rel, "error": str(exc)})
    return out
