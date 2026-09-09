"""Quick smoke checks for selectors + allure (plan verification)."""
from __future__ import annotations

from flowtest.allure_report import find_run_report_dir, write_run_allure, zip_report
from flowtest.models import StepResult, TestRun, new_id, utc_now
from flowtest.ui_actions import _parse_alternates, selector_candidates


def main() -> None:
    c = selector_candidates("", {"testid": "login-btn"})
    assert c[0] == '[data-testid="login-btn"]', c
    assert '[data-test="login-btn"]' in c
    assert '[data-qa="login-btn"]' in c

    alts = _parse_alternates({"alternates": "#a\n#b, #c"})
    assert alts == ["#a", "#b", "#c"], alts
    c2 = selector_candidates("#primary", {"alternates": "#fallback"})
    assert "#primary" in c2 and "#fallback" in c2

    c3 = selector_candidates("", {"name": "email", "aria_label": "Email"})
    assert '[name="email"]' in c3
    assert '[aria-label="Email"]' in c3
    print("selector_candidates OK")

    run = TestRun(
        id=new_id("run_"),
        test_id="tst_demo",
        test_name="Demo selectors report",
        project_id="prj_x",
        environment_id="",
        environment_name="Staging",
        status="PASS",
        triggered_by="verify",
        trigger="unit",
        started_at=utc_now(),
        finished_at=utc_now(),
        duration_ms=42,
        step_results=[
            StepResult("s1", "Click login", "ui.click", "PASS", "matched", 10),
            StepResult("s2", "Assert", "assert.element_exists", "PASS", "ok", 5),
        ],
    )
    d = write_run_allure(run)
    assert (d / "report.html").is_file(), d
    assert list(d.glob("*-result.json")), list(d.iterdir())
    z = zip_report(d)
    assert z.is_file() and z.stat().st_size > 100
    assert find_run_report_dir(run.id) == d
    print("allure_report OK", d)

    # Recorder alternates ranking (Python mirror of JS logic via events_to_steps)
    from flowtest.recorder import events_to_steps

    steps = events_to_steps(
        [
            {
                "type": "click",
                "selector": '[data-testid="ok"]',
                "alternates": ["#ok", '[aria-label="OK"]'],
                "text": "OK",
                "label": "OK",
            }
        ]
    )
    click = next(s for s in steps if s.type == "ui.click")
    assert click.config.get("selector") == '[data-testid="ok"]'
    assert click.config.get("alternates") == ["#ok", '[aria-label="OK"]']
    print("recorder alternates OK")

    from flowtest.suite_runner import run_suite_tests  # noqa: F401

    print("ALL VERIFY PASS")


if __name__ == "__main__":
    main()
