"""
Ensure bundled suite projects (e.g. TUI) exist in the local SQLite DB.

Used on app startup so Streamlit Cloud / fresh clones get Git-exported suites.
"""

from __future__ import annotations

import json
from pathlib import Path

from flowtest.models import Environment, Project, TestCase, TestStep, new_id
from flowtest.storage import (
    get_project,
    list_environments,
    list_projects,
    list_tests,
    save_environment,
    save_project,
    save_test,
)
from flowtest.suite_io import load_suite_file, suite_file_to_test_cases

ROOT = Path(__file__).resolve().parent.parent
TUI_SUITE = ROOT / "tests" / "tui" / "ui-coverage" / "suite.json"
TUI_BASE = "https://www.tui.nl"
TUI_LANDING = (
    "https://www.tui.nl/?utm_source=admarketplace&utm_medium=cpc"
    "&utm_campaign=regular&utm_content=355252386799812608&mfadid=adm"
)


def ensure_bundled_projects() -> None:
    """Idempotent — safe to call on every app start."""
    _ensure_tui()


def _ensure_tui() -> None:
    if not TUI_SUITE.is_file():
        return

    project = next((p for p in list_projects() if p.name.lower() == "tui"), None)
    if not project:
        project = Project(
            id=new_id("prj_"),
            name="TUI",
            description="TUI Netherlands (tui.nl) UI automation — homepage, nav, search coverage.",
            tags=["web", "tui", "travel", "ui"],
        )
        save_project(project)

    env = next((e for e in list_environments() if e.name == "TUI Prod"), None)
    if not env:
        env = Environment(
            id=new_id("env_"),
            name="TUI Prod",
            base_url=TUI_BASE,
            variables={"BRAND": "TUI", "LOCALE": "nl-NL", "LANDING_URL": TUI_LANDING},
        )
        save_environment(env)
    else:
        env.base_url = TUI_BASE
        env.variables = {
            **(env.variables or {}),
            "BRAND": "TUI",
            "LOCALE": "nl-NL",
            "LANDING_URL": TUI_LANDING,
        }
        save_environment(env)

    existing_by_name = {t.name: t for t in list_tests(project.id)}
    data = load_suite_file(TUI_SUITE)
    cases = suite_file_to_test_cases(data, project_id=project.id)
    for case in cases:
        prior = existing_by_name.get(case.name)
        if prior:
            prior.steps = case.steps
            prior.description = case.description
            prior.tags = case.tags
            prior.suite = case.suite
            save_test(prior, bump_version=True)
            continue
        case.project_id = project.id
        case.id = new_id("tst_")
        for s in case.steps:
            if not s.id:
                s.id = new_id("stp_")
        save_test(case, bump_version=False)
