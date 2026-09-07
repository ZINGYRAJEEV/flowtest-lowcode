"""
FlowTest MCP server — expose list/get/run/import/export tools to Cursor (and other MCP clients).

Run (stdio):
  pip install -r requirements-mcp.txt
  python -m flowtest.mcp_server

Cursor: see .cursor/mcp.json in this repo.
"""

from __future__ import annotations

import json
from typing import Any

from flowtest import mcp_api


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Missing dependency: mcp. Install with: pip install -r requirements-mcp.txt"
        ) from exc

    mcp = FastMCP(
        "FlowTest",
        instructions=(
            "FlowTest is a low-code web/API test automation tool. "
            "Use these tools to list projects/tests, inspect steps, run tests, "
            "import Chrome-extension recordings, and export suites to tests/ for Git/CI."
        ),
    )

    @mcp.tool()
    def list_projects() -> str:
        """List FlowTest projects (id, name, description)."""
        return _json(mcp_api.tool_list_projects())

    @mcp.tool()
    def list_environments() -> str:
        """List environments (name, base_url, variables)."""
        return _json(mcp_api.tool_list_environments())

    @mcp.tool()
    def list_tests(project_id: str = "", suite: str = "") -> str:
        """List tests. Optional filters: project_id, suite name."""
        return _json(
            mcp_api.tool_list_tests(
                project_id=project_id or None,
                suite=suite or None,
            )
        )

    @mcp.tool()
    def list_suites(project_id: str = "") -> str:
        """List suites with test counts, optionally filtered by project_id."""
        return _json(mcp_api.tool_list_suites(project_id=project_id or None))

    @mcp.tool()
    def get_test(test_id: str) -> str:
        """Get full test definition including steps and configs."""
        return _json(mcp_api.tool_get_test(test_id))

    @mcp.tool()
    def list_runs(limit: int = 20, project_id: str = "") -> str:
        """List recent test runs (status, duration, errors)."""
        return _json(mcp_api.tool_list_runs(limit=limit, project_id=project_id or None))

    @mcp.tool()
    def get_run(run_id: str) -> str:
        """Get a run report including per-step results."""
        return _json(mcp_api.tool_get_run(run_id))

    @mcp.tool()
    def run_test(
        test_id: str,
        env_name: str = "",
        env_id: str = "",
        headless: bool = True,
    ) -> str:
        """
        Execute a saved FlowTest by id (Playwright/httpx via FlowTest executor).
        Prefer env_name (e.g. Staging) when available.
        """
        return _json(
            mcp_api.tool_run_test(
                test_id=test_id,
                env_name=env_name or None,
                env_id=env_id or None,
                headless=headless,
            )
        )

    @mcp.tool()
    def import_recording(
        recording_json: str,
        project_id: str,
        test_name: str = "Imported recording",
        suite: str = "Recorded",
        mode: str = "create",
        test_id: str = "",
        replace_base_url: str = "",
    ) -> str:
        """
        Import Chrome extension / recorder JSON into a FlowTest case.

        mode: create | append | replace
        For append/replace, pass test_id.
        recording_json: full JSON string with steps and/or events.
        """
        return _json(
            mcp_api.tool_import_recording(
                recording_json=recording_json,
                project_id=project_id,
                test_name=test_name,
                suite=suite,
                mode=mode,
                test_id=test_id or None,
                replace_base_url=replace_base_url or None,
            )
        )

    @mcp.tool()
    def export_suite(
        suite: str,
        project_id: str = "",
        project_name: str = "",
        env_name: str = "",
    ) -> str:
        """Export a suite to tests/<project>/<suite>/suite.json for Git/CI."""
        return _json(
            mcp_api.tool_export_suite(
                suite=suite,
                project_id=project_id or None,
                project_name=project_name or None,
                env_name=env_name,
            )
        )

    @mcp.tool()
    def list_suite_files() -> str:
        """List suite.json files already present under tests/."""
        return _json(mcp_api.tool_list_suite_files())

    return mcp


def main() -> None:
    server = build_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
