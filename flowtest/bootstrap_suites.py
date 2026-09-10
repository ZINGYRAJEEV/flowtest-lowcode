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
TEMU_SUITE = ROOT / "tests" / "temu" / "ui-coverage" / "suite.json"
TEMU_BASE = "https://www.temu.com"
TEMU_LANDING = (
    "https://www.temu.com/?_x_ns_irclickid=S%3AyQn1WNdxyZWFB3Fm3MDUTQUkr2i%3AwdVWyqxU0"
    "&_x_ads_account=18350&_x_ads_id=1580294"
    "&_x_ns_iradname=Online%20Tracking%20Link&_x_ns_iradsize=&_x_ns_prodsku="
    "&_x_ns_irmptype=mediapartner&_x_ns_sharedid=firefox"
    "&_x_ns_ts=1788865869540&_x_ns_randint=1342093"
    "&_x_ns_adtype=ONLINE_TRACKING_LINK&_p_rfs=1&irgwc=1&afsrc=1"
    "&_x_ns_irmpgroupname=%22Admarketplace%22%2C%22ld%22"
    "&_x_ads_channel=impact&_x_ns_mp_value2=&_x_ns_mp_value3="
    "&_x_ns_irmpname=Firefox%20Browser%20-%20adMarketplace"
    "&_x_ns_irpid=2626476&_bg_fs=1&_p_jump_id=1202"
    "&_x_vst_scene=adg&scene=adg_alliance_exp"
    "&_p_adg_gwid=2979d96e78a54cd0a31862b2dce8f0a7"
)
AI_VERIFY_SUITE = ROOT / "tests" / "flowtest" / "ai-verify" / "suite.json"
EXAMPLE_BASE = "https://example.org"


def ensure_bundled_projects() -> None:
    """Idempotent — safe to call on every app start."""
    _ensure_tui()
    _ensure_temu()
    _ensure_ai_verify()


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


def _ensure_temu() -> None:
    if not TEMU_SUITE.is_file():
        return

    project = next((p for p in list_projects() if p.name.lower() == "temu"), None)
    if not project:
        project = Project(
            id=new_id("prj_"),
            name="Temu",
            description="Temu.com UI automation — homepage cookies, nav, search, components/ids, UTM landing.",
            tags=["web", "temu", "ecommerce", "ui"],
        )
        save_project(project)

    env = next((e for e in list_environments() if e.name == "Temu Prod"), None)
    if not env:
        env = Environment(
            id=new_id("env_"),
            name="Temu Prod",
            base_url=TEMU_BASE,
            variables={"BRAND": "Temu", "LOCALE": "en-US", "LANDING_URL": TEMU_LANDING},
        )
        save_environment(env)
    else:
        env.base_url = TEMU_BASE
        env.variables = {
            **(env.variables or {}),
            "BRAND": "Temu",
            "LOCALE": "en-US",
            "LANDING_URL": TEMU_LANDING,
        }
        save_environment(env)

    existing_by_name = {t.name: t for t in list_tests(project.id)}
    data = load_suite_file(TEMU_SUITE)
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


def _ensure_ai_verify() -> None:
    if not AI_VERIFY_SUITE.is_file():
        return

    project = next((p for p in list_projects() if p.name.lower() == "flowtest"), None)
    if not project:
        project = Project(
            id=new_id("prj_"),
            name="FlowTest",
            description="Built-in AI verification golden paths and Failure Truthfulness demos.",
            tags=["ai-verify", "golden", "meta"],
        )
        save_project(project)

    env = next((e for e in list_environments() if e.name == "Example Org"), None)
    if not env:
        env = Environment(
            id=new_id("env_"),
            name="Example Org",
            base_url=EXAMPLE_BASE,
            variables={"BRAND": "Example"},
        )
        save_environment(env)
    else:
        env.base_url = EXAMPLE_BASE
        env.variables = {**(env.variables or {}), "BRAND": "Example"}
        save_environment(env)

    existing_by_name = {t.name: t for t in list_tests(project.id)}
    data = load_suite_file(AI_VERIFY_SUITE)
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
