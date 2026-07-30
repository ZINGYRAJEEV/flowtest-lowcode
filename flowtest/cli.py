"""
Minimal webhook/CLI trigger helper for CI/CD (FR-7).

Usage:
  python -m flowtest.cli run --test-id tst_xxx --env-name Staging --user runner
  python -m flowtest.cli run-suite --suite Smoke --env-name Staging
  python -m flowtest.cli export-suite --suite Smoke --project-name "My App"
  python -m flowtest.cli run-suite-file --path tests/my-app/smoke/suite.json --env-name Staging
  python -m flowtest.cli list-tests
  python -m flowtest.cli list-suites
"""

from __future__ import annotations

import argparse
import json
import sys

from flowtest.executor import execute_test_case
from flowtest.storage import (
    get_environment,
    get_project,
    get_test,
    init_db,
    list_environments,
    list_projects,
    list_tests,
)
from flowtest.suite_io import (
    export_suite_to_files,
    load_suite_file,
    suite_file_to_test_cases,
)


def _resolve_env(args) -> object | None:
    if getattr(args, "env_id", None):
        return get_environment(args.env_id)
    if getattr(args, "env_name", None):
        return next((e for e in list_environments() if e.name == args.env_name), None)
    return None


def main(argv: list[str] | None = None) -> int:
    init_db()
    parser = argparse.ArgumentParser(prog="flowtest", description="FlowTest CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list-tests", help="List tests")
    p_list.add_argument("--project-id", default=None)
    p_list.add_argument("--suite", default=None, help="Filter by suite name")

    p_suites = sub.add_parser("list-suites", help="List suites (optionally per project)")
    p_suites.add_argument("--project-id", default=None)

    p_run = sub.add_parser("run", help="Run a test by id")
    p_run.add_argument("--test-id", required=True)
    p_run.add_argument("--env-name", default=None)
    p_run.add_argument("--env-id", default=None)
    p_run.add_argument("--user", default="cli")
    p_run.add_argument("--headed", action="store_true")

    p_suite = sub.add_parser("run-suite", help="Run all tests in a suite")
    p_suite.add_argument("--suite", required=True, help="Suite name (exact match)")
    p_suite.add_argument("--project-id", default=None, help="Limit to one project")
    p_suite.add_argument("--project-name", default=None, help="Limit by project name")
    p_suite.add_argument("--env-name", default=None)
    p_suite.add_argument("--env-id", default=None)
    p_suite.add_argument("--user", default="runner")
    p_suite.add_argument("--headed", action="store_true")
    p_suite.add_argument(
        "--continue-on-fail",
        action="store_true",
        help="Run remaining tests even if one fails (default: stop on first failure)",
    )

    p_export = sub.add_parser(
        "export-suite",
        help="Export suite test steps to tests/<project>/<suite>/suite.json for Git/CI",
    )
    p_export.add_argument("--suite", required=True)
    p_export.add_argument("--project-id", default=None)
    p_export.add_argument("--project-name", default=None)
    p_export.add_argument("--env-name", default="", help="Stored as environment_hint in suite.json")

    p_file = sub.add_parser(
        "run-suite-file",
        help="Run suite from suite.json (Git-friendly; no DB required for steps)",
    )
    p_file.add_argument("--path", required=True, help="Path to suite.json or its folder")
    p_file.add_argument("--env-name", default=None)
    p_file.add_argument("--env-id", default=None)
    p_file.add_argument("--user", default="runner")
    p_file.add_argument("--headed", action="store_true")
    p_file.add_argument("--continue-on-fail", action="store_true")

    p_envs = sub.add_parser("list-envs", help="List environments")

    args = parser.parse_args(argv)

    if args.cmd == "list-tests":
        tests = list_tests(args.project_id)
        if args.suite:
            tests = [t for t in tests if t.suite == args.suite]
        for t in tests:
            print(f"{t.id}\t{t.suite}\t{t.name}\t({len(t.steps)} steps)")
        return 0

    if args.cmd == "list-suites":
        tests = list_tests(args.project_id)
        projects = {p.id: p.name for p in list_projects()}
        suites: dict[tuple[str, str], int] = {}
        for t in tests:
            key = (t.project_id, t.suite)
            suites[key] = suites.get(key, 0) + 1
        for (pid, suite), count in sorted(suites.items(), key=lambda x: (projects.get(x[0][0], ""), x[0][1])):
            print(f"{pid}\t{projects.get(pid, '')}\t{suite}\t{count} tests")
        return 0

    if args.cmd == "list-envs":
        for e in list_environments():
            print(f"{e.id}\t{e.name}\t{e.base_url}")
        return 0

    if args.cmd == "run":
        test = get_test(args.test_id)
        if not test:
            print(f"Test not found: {args.test_id}", file=sys.stderr)
            return 2
        env = _resolve_env(args)
        run = execute_test_case(
            test,
            env,
            triggered_by=args.user,
            trigger="cli",
            headless=not args.headed,
        )
        print(json.dumps({"run_id": run.id, "status": run.status, "duration_ms": run.duration_ms}, indent=2))
        return 0 if run.status == "PASS" else 1

    if args.cmd == "run-suite":
        project_id = args.project_id
        if args.project_name and not project_id:
            match = next((p for p in list_projects() if p.name == args.project_name), None)
            if not match:
                print(f"Project not found: {args.project_name}", file=sys.stderr)
                return 2
            project_id = match.id

        tests = list_tests(project_id)
        selected = [t for t in tests if t.suite == args.suite]
        if not selected:
            print(f"No tests found for suite '{args.suite}'", file=sys.stderr)
            return 2

        env = _resolve_env(args)
        results = []
        overall_ok = True
        for test in selected:
            run = execute_test_case(
                test,
                env,
                triggered_by=args.user,
                trigger="cli",
                headless=not args.headed,
            )
            entry = {
                "test_id": test.id,
                "test_name": test.name,
                "run_id": run.id,
                "status": run.status,
                "duration_ms": run.duration_ms,
            }
            results.append(entry)
            print(json.dumps(entry))
            if run.status != "PASS":
                overall_ok = False
                if not args.continue_on_fail:
                    break

        summary = {
            "suite": args.suite,
            "project_id": project_id,
            "environment": getattr(env, "name", None),
            "total": len(selected),
            "executed": len(results),
            "passed": sum(1 for r in results if r["status"] == "PASS"),
            "failed": sum(1 for r in results if r["status"] != "PASS"),
            "status": "PASS" if overall_ok and len(results) == len(selected) else "FAIL",
            "results": results,
        }
        print(json.dumps(summary, indent=2))
        return 0 if summary["status"] == "PASS" else 1

    if args.cmd == "export-suite":
        project_id = args.project_id
        project_name = args.project_name or ""
        if args.project_name and not project_id:
            match = next((p for p in list_projects() if p.name == args.project_name), None)
            if not match:
                print(f"Project not found: {args.project_name}", file=sys.stderr)
                return 2
            project_id = match.id
            project_name = match.name
        elif project_id:
            proj = get_project(project_id)
            project_name = proj.name if proj else project_name or project_id

        tests = list_tests(project_id)
        selected = [t for t in tests if t.suite == args.suite]
        if not selected:
            print(f"No tests found for suite '{args.suite}'", file=sys.stderr)
            return 2

        path = export_suite_to_files(
            project_name=project_name or "project",
            suite=args.suite,
            tests=selected,
            environment_name=args.env_name or "",
            project_id=project_id or "",
        )
        print(json.dumps({"exported": str(path), "tests": len(selected)}, indent=2))
        return 0

    if args.cmd == "run-suite-file":
        data = load_suite_file(args.path)
        selected = suite_file_to_test_cases(data)
        if not selected:
            print(f"No tests in suite file: {args.path}", file=sys.stderr)
            return 2

        env = _resolve_env(args)
        if env is None and data.get("environment_hint"):
            env = next(
                (e for e in list_environments() if e.name == data["environment_hint"]),
                None,
            )

        results = []
        overall_ok = True
        for test in selected:
            run = execute_test_case(
                test,
                env,
                triggered_by=args.user,
                trigger="cli-file",
                headless=not args.headed,
            )
            entry = {
                "test_id": test.id,
                "test_name": test.name,
                "run_id": run.id,
                "status": run.status,
                "duration_ms": run.duration_ms,
            }
            results.append(entry)
            print(json.dumps(entry))
            if run.status != "PASS":
                overall_ok = False
                if not args.continue_on_fail:
                    break

        summary = {
            "suite": data.get("suite"),
            "path": args.path,
            "environment": getattr(env, "name", None),
            "total": len(selected),
            "executed": len(results),
            "passed": sum(1 for r in results if r["status"] == "PASS"),
            "failed": sum(1 for r in results if r["status"] != "PASS"),
            "status": "PASS" if overall_ok and len(results) == len(selected) else "FAIL",
            "results": results,
        }
        print(json.dumps(summary, indent=2))
        return 0 if summary["status"] == "PASS" else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
