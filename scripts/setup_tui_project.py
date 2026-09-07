"""
Bootstrap FlowTest project: TUI (tui.nl) — environment + UI coverage suite.

Note: tui.nl is behind Akamai and often returns 403 to headless crawlers, so
core coverage tests are curated for the public homepage (cookie, brand, nav, search).
Run: python scripts/setup_tui_project.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flowtest.models import Environment, Project, TestCase, TestStep, new_id, utc_now
from flowtest.storage import (
    add_audit,
    init_db,
    list_environments,
    list_projects,
    list_tests,
    save_environment,
    save_project,
    save_test,
)
from flowtest.suite_io import export_suite_to_files

START_URL = (
    "https://www.tui.nl/?utm_source=admarketplace&utm_medium=cpc"
    "&utm_campaign=regular&utm_content=355252386799812608&mfadid=adm"
)
BASE_URL = "https://www.tui.nl"

COOKIE_JS = """
(() => {
  const labels = [
    'accepteer cookies',
    'alles accepteren',
    'accept cookies',
    'accept all',
    'accepteer',
    'accepteren',
    'akkoord',
    'agree',
    'toestaan',
  ];
  const clickMatch = (root) => {
    if (!root) return null;
    const nodes = Array.from(root.querySelectorAll('button, [role="button"], a, input[type="button"], input[type="submit"]'));
    for (const el of nodes) {
      const t = (el.innerText || el.value || el.getAttribute('aria-label') || '')
        .replace(/\\s+/g, ' ')
        .trim()
        .toLowerCase();
      if (!t) continue;
      // Prefer exact-ish accept, never click Weigeren/Refuse
      if (t.includes('weiger') || t.includes('refus') || t.includes('decline') || t.includes('reject')) continue;
      if (labels.some((l) => t === l || t.includes(l))) {
        el.click();
        return 'clicked:' + t.slice(0, 48);
      }
    }
    return null;
  };
  const dialogs = Array.from(
    document.querySelectorAll('[role="dialog"], [aria-modal="true"], [class*="cookie" i], [class*="consent" i], [id*="cookie" i], [id*="consent" i]')
  );
  for (const d of dialogs) {
    const hit = clickMatch(d);
    if (hit) return hit;
  }
  return clickMatch(document.body) || 'no-banner';
})()
"""


def _stp(stype: str, name: str, config: dict, notes: str = "") -> TestStep:
    return TestStep(id=new_id("stp_"), type=stype, name=name, config=config, notes=notes)


def _optional_click_js(label: str) -> str:
    safe = label.replace("\\", "\\\\").replace("'", "\\'")
    return f"""
(() => {{
  const want = '{safe}'.toLowerCase();
  const nodes = Array.from(document.querySelectorAll('a, button, [role="button"], [role="link"]'));
  for (const el of nodes) {{
    const t = (el.innerText || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim();
    if (t && t.toLowerCase().includes(want)) {{
      el.click();
      return 'clicked:' + t.slice(0, 60);
    }}
  }}
  return 'missing';
}})()
"""


def _accept_cookies_steps(prefix: str = "") -> list[TestStep]:
    """Privacy modal: 'Accepteer cookies' / 'Weigeren' — must accept before nav works."""
    p = f"{prefix} " if prefix else ""
    return [
        _stp("ui.wait", f"{p}Wait for cookie dialog".strip(), {"ms": 2800}),
        _stp(
            "util.custom_js",
            f"{p}Click Accepteer cookies".strip(),
            {"script": COOKIE_JS},
            "TUI modal 'We respecteren jouw privacy' — clicks Accepteer cookies, never Weigeren",
        ),
        _stp("ui.wait", f"{p}Settle after consent".strip(), {"ms": 1500}),
    ]


def build_core_smoke() -> list[TestStep]:
    return [
        _stp("ui.goto", "Open TUI homepage", {"url": "{{BASE_URL}}", "timeout_ms": 60000}),
        *_accept_cookies_steps(),
        _stp("assert.title_contains", "Title mentions TUI", {"text": "TUI", "timeout_ms": 20000}),
        _stp(
            "assert.text_contains",
            "Body mentions TUI / vakantie",
            {"selector": "body", "text": "TUI", "timeout_ms": 20000, "ignore_case": True},
        ),
        _stp("util.custom_js", "Scroll below fold", {"script": "window.scrollBy(0, 1000);"}),
        _stp("ui.wait", "Wait after scroll", {"ms": 800}),
        _stp("util.custom_js", "Scroll further", {"script": "window.scrollBy(0, 1000);"}),
        _stp("ui.wait", "Wait after second scroll", {"ms": 600}),
        _stp("assert.element_exists", "Document still responsive", {"selector": "body", "timeout_ms": 10000}),
        _stp("ui.screenshot", "Homepage screenshot", {"name": "tui_home"}),
    ]


def build_nav_coverage() -> list[TestStep]:
    labels = [
        "Vakanties",
        "Vliegtickets",
        "Cruises",
        "Zoeken",
        "Inloggen",
        "Service & Contact",
        "Bestemmingen",
        "Last minute",
    ]
    steps = [
        _stp("ui.goto", "Open TUI homepage", {"url": "{{BASE_URL}}", "timeout_ms": 60000}),
        *_accept_cookies_steps(),
    ]
    for label in labels:
        steps.append(
            _stp(
                "util.custom_js",
                f'Optional click "{label}"',
                {"script": _optional_click_js(label)},
                "Non-fatal if control missing (A-B UI)",
            )
        )
        steps.append(_stp("ui.wait", f"After {label}", {"ms": 700}))
        steps.append(_stp("ui.goto", "Return home", {"url": "{{BASE_URL}}", "timeout_ms": 60000}))
        steps.append(_stp("ui.wait", "Home settle", {"ms": 900}))
        steps.append(_stp("util.custom_js", "Re-dismiss cookies if shown", {"script": COOKIE_JS}))
        steps.append(_stp("ui.wait", "After re-dismiss", {"ms": 400}))
    steps.append(
        _stp(
            "assert.element_exists",
            "Home still loads after nav trail",
            {"selector": "body", "timeout_ms": 10000},
        )
    )
    steps.append(_stp("ui.screenshot", "After nav coverage", {"name": "tui_nav"}))
    return steps


def build_search_coverage() -> list[TestStep]:
    search_js = """
(() => {
  const tryFill = (hints, value) => {
    const inputs = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"]'));
    for (const el of inputs) {
      const meta = [
        el.getAttribute('name') || '',
        el.getAttribute('placeholder') || '',
        el.getAttribute('aria-label') || '',
        el.id || '',
      ].join(' ').toLowerCase();
      if (!hints.some((h) => meta.includes(h))) continue;
      if (el.isContentEditable) { el.textContent = value; }
      else {
        el.focus();
        el.value = value;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      }
      return 'filled:' + meta.slice(0, 40);
    }
    return 'no-field';
  };
  const a = tryFill(['bestemming', 'destination', 'waarheen', 'zoek', 'search', 'stad', 'hotel'], 'Spanje');
  const b = tryFill(['vertrek', 'depart', 'date', 'datum'], '2026-10-01');
  return a + '|' + b;
})()
"""
    return [
        _stp("ui.goto", "Open TUI homepage", {"url": "{{BASE_URL}}", "timeout_ms": 60000}),
        *_accept_cookies_steps(),
        _stp("util.custom_js", "Fill destination / date if present", {"script": search_js}),
        _stp("ui.wait", "After fill", {"ms": 500}),
        _stp("util.custom_js", "Click Zoeken if present", {"script": _optional_click_js("Zoeken")}),
        _stp("ui.wait", "Wait for search reaction", {"ms": 2000}),
        _stp(
            "assert.element_exists",
            "Page responsive after search interaction",
            {"selector": "body", "timeout_ms": 10000},
        ),
        _stp("ui.screenshot", "After search interaction", {"name": "tui_search"}),
    ]


def build_landing_utm_smoke() -> list[TestStep]:
    return [
        _stp(
            "ui.goto",
            "Open campaign landing URL",
            {"url": "{{LANDING_URL}}", "timeout_ms": 60000},
            "Uses LANDING_URL from environment (UTM campaign link)",
        ),
        *_accept_cookies_steps(),
        _stp(
            "assert.element_exists",
            "Landing document loaded",
            {"selector": "body", "timeout_ms": 15000},
        ),
        _stp(
            "assert.text_contains",
            "Page shows TUI",
            {"selector": "body", "text": "TUI", "timeout_ms": 15000, "ignore_case": True},
        ),
        _stp("ui.screenshot", "Landing screenshot", {"name": "tui_landing_utm"}),
    ]


def main() -> int:
    init_db()

    existing = next((p for p in list_projects() if p.name.lower() == "tui"), None)
    if existing:
        project = existing
        print(f"Project exists: {project.id} {project.name}")
    else:
        project = Project(
            id=new_id("prj_"),
            name="TUI",
            description="TUI Netherlands (tui.nl) UI automation — homepage, nav, search coverage.",
            tags=["web", "tui", "travel", "ui"],
        )
        save_project(project)
        add_audit("local", "create", "project", project.id, project.name)
        print(f"Created project: {project.id} {project.name}")

    env = next((e for e in list_environments() if e.name == "TUI Prod"), None)
    if not env:
        env = Environment(
            id=new_id("env_"),
            name="TUI Prod",
            base_url=BASE_URL,
            variables={
                "BRAND": "TUI",
                "LOCALE": "nl-NL",
                "LANDING_URL": START_URL,
            },
        )
        save_environment(env)
        add_audit("local", "create", "environment", env.id, env.name)
        print(f"Created environment: {env.id} {env.name} -> {env.base_url}")
    else:
        env.base_url = BASE_URL
        env.variables = {
            **(env.variables or {}),
            "BRAND": "TUI",
            "LOCALE": "nl-NL",
            "LANDING_URL": START_URL,
        }
        save_environment(env)
        print(f"Updated environment: {env.id} {env.name}")

    # Live assess (often 403 from Akamai) — informational only
    try:
        import monkey_engine as me

        print(f"Assessing {BASE_URL} (may be blocked by bot protection)...")
        assessment = me.assess_webpage_safe(BASE_URL, headless=True, timeout_ms=30000)
        print(
            f"Assessed: title={assessment.title!r} status={assessment.status} "
            f"elements={len(assessment.elements)}"
        )
    except Exception as exc:
        print(f"Assess skipped/failed: {exc}")

    suite = "UI Coverage"

    def upsert(name: str, description: str, steps: list[TestStep], tags: list[str]) -> TestCase:
        prior = next(
            (t for t in list_tests(project.id) if t.name == name and t.suite == suite),
            None,
        )
        if prior:
            prior.steps = steps
            prior.description = description
            prior.tags = tags
            prior.updated_at = utc_now()
            save_test(prior, bump_version=True)
            print(f"Updated test: {prior.id} {prior.name} ({len(steps)} steps)")
            return prior
        test = TestCase(
            id=new_id("tst_"),
            project_id=project.id,
            name=name,
            description=description,
            tags=tags,
            steps=steps,
            suite=suite,
            created_by="setup_tui",
        )
        save_test(test, bump_version=False)
        add_audit("local", "create", "test", test.id, test.name)
        print(f"Created test: {test.id} {test.name} ({len(steps)} steps)")
        return test

    # Remove weak exploratory cases from prior 403 assess run
    for t in list_tests(project.id):
        if t.suite == suite and t.name.startswith("Exploratory:"):
            from flowtest.storage import delete_test

            delete_test(t.id)
            print(f"Removed weak test: {t.name}")

    upsert(
        "Smoke: TUI homepage load & brand",
        "Opens tui.nl, dismisses cookies if present, asserts TUI branding, scrolls, screenshots.",
        build_core_smoke(),
        ["smoke", "ui", "tui", "coverage"],
    )
    upsert(
        "Coverage: TUI navigation & CTAs",
        "Optional clicks on common Dutch nav/CTA labels; returns home between attempts.",
        build_nav_coverage(),
        ["ui", "nav", "tui", "coverage"],
    )
    upsert(
        "Coverage: TUI search / form fields",
        "Best-effort fill of destination/date fields and Zoeken click via resilient JS helpers.",
        build_search_coverage(),
        ["ui", "search", "form", "tui", "coverage"],
    )
    upsert(
        "Smoke: Campaign landing (UTM)",
        "Opens the provided admarketplace landing URL via {{LANDING_URL}} and checks the page loads.",
        build_landing_utm_smoke(),
        ["smoke", "ui", "tui", "utm", "coverage"],
    )

    path = export_suite_to_files(
        project_name=project.name,
        suite=suite,
        tests=[t for t in list_tests(project.id) if t.suite == suite],
        environment_name=env.name,
        project_id=project.id,
    )
    print(f"Exported suite -> {path}")
    print(
        f"\nDone. Open FlowTest -> Project TUI -> suite '{suite}'. "
        f"Run with environment '{env.name}' ({BASE_URL})."
    )
    print(
        "Note: tui.nl often returns HTTP 403 to automated browsers (Akamai). "
        "Run from a normal network/browser context if executions are blocked."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
