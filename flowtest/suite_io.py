"""
Export / load test suites as JSON files for Git + CI (Azure/Jenkins).

Canonical layout:
  tests/<project_slug>/<suite_slug>/suite.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from flowtest.models import TestCase, TestStep, new_id, utc_now

ROOT = Path(__file__).resolve().parent.parent
TESTS_ROOT = ROOT / "tests"


def slugify(value: str) -> str:
    value = (value or "untitled").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "untitled"


def suite_dir(project_name: str, suite: str) -> Path:
    return TESTS_ROOT / slugify(project_name) / slugify(suite)


def suite_file(project_name: str, suite: str) -> Path:
    return suite_dir(project_name, suite) / "suite.json"


def test_to_portable(test: TestCase) -> dict[str, Any]:
    return {
        "id": test.id,
        "name": test.name,
        "description": test.description,
        "tags": test.tags,
        "suite": test.suite,
        "version": test.version,
        "steps": [s.to_dict() for s in test.steps],
    }


def export_suite_to_files(
    project_name: str,
    suite: str,
    tests: list[TestCase],
    environment_name: str = "",
    project_id: str = "",
) -> Path:
    """
    Write suite.json (and per-test JSON copies) under tests/.
    Returns the path to suite.json — this is what Azure should run.
    """
    out_dir = suite_dir(project_name, suite)
    out_dir.mkdir(parents=True, exist_ok=True)

    portable_tests = [test_to_portable(t) for t in tests]
    payload = {
        "format": "flowtest-suite/v1",
        "exported_at": utc_now(),
        "project_id": project_id,
        "project_name": project_name,
        "suite": suite,
        "environment_hint": environment_name,
        "tests": portable_tests,
    }

    suite_path = out_dir / "suite.json"
    suite_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Optional per-test files for easier Git review/diffs
    cases_dir = out_dir / "cases"
    cases_dir.mkdir(exist_ok=True)
    for t in portable_tests:
        safe = slugify(t["name"])
        (cases_dir / f"{safe}.json").write_text(json.dumps(t, indent=2), encoding="utf-8")

    readme = out_dir / "README.md"
    readme.write_text(
        f"""# FlowTest suite: {suite}

Project: **{project_name}**

## Run locally / in Azure Pipelines

```bash
python -m flowtest.cli run-suite-file --path "{suite_path.relative_to(ROOT).as_posix()}" --env-name "{environment_name or "Staging"}"
```

Commit this folder to Git. The pipeline picks up `suite.json` (test steps live here).
""",
        encoding="utf-8",
    )
    return suite_path


def load_suite_file(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        # Allow passing the suite directory
        candidate = p / "suite.json" if p.is_dir() else None
        if candidate and candidate.is_file():
            p = candidate
        else:
            raise FileNotFoundError(f"Suite file not found: {path}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if "tests" not in data:
        raise ValueError("Invalid suite file: missing 'tests'")
    return data


def suite_file_to_test_cases(data: dict[str, Any], project_id: str = "file") -> list[TestCase]:
    suite = data.get("suite") or "Default"
    cases: list[TestCase] = []
    for raw in data.get("tests", []):
        steps = [TestStep(**s) if isinstance(s, dict) else s for s in raw.get("steps", [])]
        for s in steps:
            if not getattr(s, "id", None):
                s.id = new_id("stp_")
        cases.append(
            TestCase(
                id=raw.get("id") or new_id("tst_"),
                project_id=data.get("project_id") or project_id,
                name=raw.get("name") or "Unnamed test",
                description=raw.get("description") or "",
                tags=raw.get("tags") or [],
                steps=steps,
                suite=raw.get("suite") or suite,
                version=int(raw.get("version") or 1),
                created_by=raw.get("created_by") or "git",
            )
        )
    return cases
