"""
Low-code monkey testing engine.

Assesses a live webpage, generates intent-style monkey test cases,
and executes them with Playwright.
"""

from __future__ import annotations

import json
import random
import re
import string
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

SCREENSHOT_DIR = Path(__file__).resolve().parent / "monkey_artifacts"
SCREENSHOT_DIR.mkdir(exist_ok=True)


def _run_in_browser_process(func: Callable, *args, timeout: int = 180, **kwargs):
    """
    Legacy name — prefer subprocess helpers below.
    Kept for compatibility; routes assess/execute through monkey_job.
    """
    raise RuntimeError("Use assess_webpage_safe / execute_selected_cases_safe")


def _subprocess_json_job(mode: str, payload: dict, timeout: int = 180) -> dict:
    import json
    import os
    import subprocess
    import sys
    import tempfile

    root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="monkey_job_") as tmp:
        tmp_path = Path(tmp)
        in_path = tmp_path / "in.json"
        out_path = tmp_path / "out.json"
        in_path.write_text(json.dumps(payload), encoding="utf-8")
        env = dict(os.environ)
        py_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(root) + ((";" + py_path) if py_path else "")
        proc = subprocess.run(
            [sys.executable, "-m", "monkey_job", mode, str(in_path), str(out_path)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if not out_path.exists():
            raise RuntimeError((proc.stderr or proc.stdout or f"exit {proc.returncode}").strip())
        data = json.loads(out_path.read_text(encoding="utf-8"))
        if data.get("error") and mode == "assess" and "url" not in data:
            raise RuntimeError(data["error"])
        if data.get("error") and mode == "execute" and "test_id" not in data:
            raise RuntimeError(data["error"])
        return data


def format_exception(exc: BaseException) -> str:
    msg = str(exc).strip()
    name = type(exc).__name__
    if not msg:
        if name == "NotImplementedError":
            return (
                "Playwright could not start inside Streamlit on Windows "
                "(asyncio subprocess limitation). Retry after refresh — "
                "browser work now runs in an isolated process."
            )
        return name
    return f"{name}: {msg}"

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class PageElement:
    index: int
    tag: str
    role: str
    text: str
    selector: str
    element_type: str
    href: str = ""
    name: str = ""
    placeholder: str = ""
    input_type: str = ""
    visible: bool = True


@dataclass
class PageAssessment:
    url: str
    title: str
    final_url: str
    status: str
    load_ms: int
    elements: list[PageElement] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    screenshot_path: str = ""
    assessed_at: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


@dataclass
class MonkeyStep:
    action: str
    target: str
    selector: str
    value: str = ""
    description: str = ""


@dataclass
class MonkeyTestCase:
    id: str
    name: str
    description: str
    priority: str
    steps: list[MonkeyStep]
    tags: list[str] = field(default_factory=list)
    enabled: bool = True
    objective: str = ""
    coverage: str = ""
    expected_result: str = ""
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_low_code_script(self) -> str:
        lines = [
            f"# {self.id}: {self.name}",
            f"# Priority: {self.priority}",
            f"# Tags: {', '.join(self.tags) if self.tags else 'none'}",
            "",
            "## Objective",
            self.objective or self.description,
            "",
            "## What this covers",
            self.coverage or "Interactive UI elements discovered on the target page.",
            "",
            "## Why it matters",
            self.rationale or "Monkey interactions surface crashes, dead clicks, and unstable UI states.",
            "",
            "## Expected result",
            self.expected_result or "Page remains responsive with no uncaught page crash.",
            "",
            "## Detailed description",
            self.description,
            "",
            "## Low-code steps",
        ]
        for i, step in enumerate(self.steps, 1):
            lines.append(f"{i}. [{step.action}] {step.description}")
            if step.selector:
                lines.append(f"   - selector: {step.selector}")
            if step.value:
                lines.append(f"   - value: {step.value}")
        return "\n".join(lines)

    def detailed_summary(self) -> str:
        return (
            f"**{self.id} — {self.name}**\n\n"
            f"**Objective:** {self.objective or self.description}\n\n"
            f"**Coverage:** {self.coverage}\n\n"
            f"**Why it matters:** {self.rationale}\n\n"
            f"**Expected result:** {self.expected_result}\n\n"
            f"**Description:** {self.description}\n\n"
            f"**Priority:** {self.priority} · **Steps:** {len(self.steps)} · "
            f"**Tags:** {', '.join(self.tags) if self.tags else '—'}"
        )


@dataclass
class StepResult:
    step_index: int
    description: str
    status: str
    detail: str = ""
    duration_ms: int = 0


@dataclass
class TestRunResult:
    test_id: str
    test_name: str
    status: str
    started_at: str
    finished_at: str
    duration_ms: int
    steps: list[StepResult]
    screenshot_path: str = ""
    console_errors: list[str] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    final_url: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_JS_DISCOVER_ELEMENTS = """
() => {
  const isVisible = (el) => {
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden'
      && style.display !== 'none'
      && style.opacity !== '0'
      && rect.width > 0
      && rect.height > 0;
  };

  const cssPath = (el) => {
    if (el.id) return `#${CSS.escape(el.id)}`;
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 5) {
      let part = node.tagName.toLowerCase();
      if (node.id) {
        parts.unshift(`#${CSS.escape(node.id)}`);
        break;
      }
      const parent = node.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(c => c.tagName === node.tagName);
        if (siblings.length > 1) {
          const idx = siblings.indexOf(node) + 1;
          part += `:nth-of-type(${idx})`;
        }
      }
      parts.unshift(part);
      node = parent;
      if (node && node.tagName && node.tagName.toLowerCase() === 'body') break;
    }
    return parts.join(' > ');
  };

  const candidates = Array.from(document.querySelectorAll(
    'a[href], button, input, select, textarea, [role="button"], [onclick], [tabindex]'
  ));

  const results = [];
  let index = 0;
  for (const el of candidates) {
    if (!isVisible(el)) continue;
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role') || '';
    const text = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim().slice(0, 80);
    const href = el.getAttribute('href') || '';
    const name = el.getAttribute('name') || '';
    const placeholder = el.getAttribute('placeholder') || '';
    const inputType = (el.getAttribute('type') || '').toLowerCase();

    let elementType = tag;
    if (tag === 'a') elementType = 'link';
    else if (tag === 'button' || role === 'button') elementType = 'button';
    else if (tag === 'input') {
      if (['submit', 'button', 'reset', 'image'].includes(inputType)) elementType = 'button';
      else if (['checkbox', 'radio'].includes(inputType)) elementType = inputType;
      else elementType = 'input';
    } else if (tag === 'select') elementType = 'select';
    else if (tag === 'textarea') elementType = 'textarea';

    results.push({
      index: index++,
      tag,
      role,
      text,
      selector: cssPath(el),
      element_type: elementType,
      href,
      name,
      placeholder,
      input_type: inputType,
      visible: true,
    });
    if (results.length >= 250) break;
  }
  return results;
}
"""


def _random_string(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def _random_email() -> str:
    return f"monkey_{_random_string(6).lower()}@example.com"


def _random_phone() -> str:
    return "".join(random.choices(string.digits, k=10))


def _safe_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value)[:80]


def _ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && playwright install chromium"
        ) from exc


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("URL is required")
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError("Invalid URL")
    return url


# ---------------------------------------------------------------------------
# Assess
# ---------------------------------------------------------------------------


def assess_webpage(
    url: str,
    timeout_ms: int = 30000,
    headless: bool = True,
) -> PageAssessment:
    _ensure_playwright()
    from playwright.sync_api import sync_playwright

    url = normalize_url(url)
    console_errors: list[str] = []
    page_errors: list[str] = []
    started = time.perf_counter()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)

        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        response = page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(800)

        load_ms = int((time.perf_counter() - started) * 1000)
        title = page.title()
        final_url = page.url
        status = str(response.status) if response else "unknown"

        raw_elements = page.evaluate(_JS_DISCOVER_ELEMENTS)
        elements = [PageElement(**el) for el in raw_elements]

        shot = SCREENSHOT_DIR / f"assess_{_safe_filename(urlparse(url).netloc)}_{int(time.time())}.png"
        page.screenshot(path=str(shot), full_page=False)

        counts = {}
        for el in elements:
            counts[el.element_type] = counts.get(el.element_type, 0) + 1

        assessment = PageAssessment(
            url=url,
            title=title,
            final_url=final_url,
            status=status,
            load_ms=load_ms,
            elements=elements,
            console_errors=console_errors[:20],
            page_errors=page_errors[:20],
            screenshot_path=str(shot),
            assessed_at=datetime.now().isoformat(timespec="seconds"),
            meta={
                "element_counts": counts,
                "interactive_count": len(elements),
                "domain": urlparse(final_url).netloc,
            },
        )
        browser.close()
        return assessment


# ---------------------------------------------------------------------------
# Generate monkey cases
# ---------------------------------------------------------------------------


def _fill_value_for(element: PageElement) -> str:
    hint = f"{element.name} {element.placeholder} {element.input_type} {element.text}".lower()
    if element.input_type == "email" or "email" in hint:
        return _random_email()
    if element.input_type == "tel" or "phone" in hint or "mobile" in hint:
        return _random_phone()
    if element.input_type == "number":
        return str(random.randint(1, 9999))
    if element.input_type == "password" or "password" in hint:
        return f"Monkey!{_random_string(6)}"
    if element.input_type in ("date",):
        return "2026-07-30"
    if element.input_type in ("url",):
        return "https://example.com"
    return f"monkey_{_random_string(6)}"


def _clickable(elements: list[PageElement]) -> list[PageElement]:
    return [e for e in elements if e.element_type in ("button", "link", "checkbox", "radio")]


def _fillable(elements: list[PageElement]) -> list[PageElement]:
    return [e for e in elements if e.element_type in ("input", "textarea")]


def _selectable(elements: list[PageElement]) -> list[PageElement]:
    return [e for e in elements if e.element_type == "select"]


def _element_label(el: PageElement) -> str:
    return el.text or el.placeholder or el.name or el.href or el.selector


def _next_case_id(used_ids: set[str], next_id: list[int]) -> str:
    while f"TC-M{next_id[0]:03d}" in used_ids:
        next_id[0] += 1
    case_id = f"TC-M{next_id[0]:03d}"
    next_id[0] += 1
    used_ids.add(case_id)
    return case_id


def recommend_coverage_count(assessment: PageAssessment) -> int:
    """Suggest how many cases are needed for broad interactive coverage."""
    elements = assessment.elements
    if not elements:
        return 1
    clickables = _clickable(elements)
    fillables = _fillable(elements)
    selects = _selectable(elements)
    # Baseline suites + one case per interactive control + keyboard/scroll + random walks
    baseline = 3
    per_element = len(clickables) + len(fillables) + len(selects)
    extras = 4 + max(3, len(elements) // 5)
    return max(baseline + per_element + extras, 8)


def generate_monkey_test_cases(
    assessment: PageAssessment,
    count: int | None = None,
    steps_per_case: int = 6,
    seed: int | None = None,
    max_coverage: bool = True,
) -> list[MonkeyTestCase]:
    """
    Generate low-code monkey cases.

    When max_coverage=True (default) or count is None, generates as many cases as
    needed to cover discovered interactive elements (buttons, links, inputs, selects),
    plus stability / keyboard / scroll / random-walk suites.
    """
    if seed is not None:
        random.seed(seed)

    elements = assessment.elements
    domain = assessment.meta.get("domain") or urlparse(assessment.url).netloc
    page_title = assessment.title or domain or assessment.url

    if not elements:
        return [
            MonkeyTestCase(
                id="TC-M001",
                name="Smoke: open page and wait",
                description=(
                    f"The assessment of '{page_title}' ({assessment.url}) found no visible "
                    "interactive controls (buttons, links, inputs, or selects). This smoke case "
                    "still opens the page, waits for settle time, and confirms the document remains "
                    "responsive — useful for detecting hard load failures or blank-page crashes."
                ),
                priority="High",
                steps=[
                    MonkeyStep("goto", assessment.url, "", "", f"Open {assessment.url}"),
                    MonkeyStep("wait", "", "", "1000", "Wait 1 second for render settle"),
                    MonkeyStep("assert_no_crash", "", "", "", "Confirm page is still responsive"),
                ],
                tags=["smoke", "stability", "no-controls"],
                objective="Verify the page loads and stays alive even without interactive controls.",
                coverage="Page load / document readiness only (no UI controls detected).",
                expected_result="document.readyState is interactive or complete; no page crash.",
                rationale="Even static pages can fail to load or throw fatal script errors.",
            )
        ]

    clickables = _clickable(elements)
    fillables = _fillable(elements)
    selects = _selectable(elements)
    buttons = [e for e in clickables if e.element_type == "button"]
    links = [e for e in clickables if e.element_type == "link"]
    toggles = [e for e in clickables if e.element_type in ("checkbox", "radio")]

    target_count = recommend_coverage_count(assessment) if (max_coverage or count is None) else int(count)
    if count is not None and not max_coverage:
        target_count = max(1, int(count))
    elif count is not None and max_coverage:
        # User asked for a specific floor/ceiling while still preferring coverage
        target_count = max(recommend_coverage_count(assessment), int(count))

    cases: list[MonkeyTestCase] = []
    used_ids: set[str] = set()
    next_id = [1]

    def add_case(**kwargs) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _next_case_id(used_ids, next_id)
        else:
            used_ids.add(kwargs["id"])
        cases.append(MonkeyTestCase(**kwargs))

    # --- Baseline: smoke / stability ---
    add_case(
        id=_next_case_id(used_ids, next_id),
        name="Smoke: load, scroll & stability check",
        description=(
            f"Opens '{page_title}' at {assessment.url}, waits for the network/DOM to settle, "
            "scrolls the viewport to exercise lazy content and sticky headers, then asserts the "
            "page is still responsive. This is the minimum health gate before deeper monkey chaos."
        ),
        priority="High",
        steps=[
            MonkeyStep("goto", assessment.url, "", "", f"Open {assessment.url}"),
            MonkeyStep("wait", "", "", "1500", "Wait for network/DOM settle (1.5s)"),
            MonkeyStep("scroll", "", "", "400", "Scroll down 400px to reveal below-fold UI"),
            MonkeyStep("scroll", "", "", "400", "Scroll down another 400px"),
            MonkeyStep("assert_no_crash", "", "", "", "Confirm page is still responsive"),
        ],
        tags=["smoke", "stability", "scroll"],
        objective="Confirm the target URL loads and remains stable after light scrolling.",
        coverage=f"Page load + scroll on {domain}; {len(elements)} interactive elements in inventory (not exercised yet).",
        expected_result="Page remains on a valid document state with no fatal crash during scroll.",
        rationale="Many defects only appear after scroll (lazy widgets, infinite lists, sticky nav).",
    )

    # --- Full form fuzz (chunked if many fields) ---
    if fillables:
        chunk_size = 6
        for chunk_i in range(0, len(fillables), chunk_size):
            chunk = fillables[chunk_i : chunk_i + chunk_size]
            form_steps = [MonkeyStep("goto", assessment.url, "", "", f"Open {assessment.url}")]
            labels = []
            for el in chunk:
                value = _fill_value_for(el)
                label = _element_label(el)
                labels.append(label)
                form_steps.append(
                    MonkeyStep(
                        "fill",
                        label,
                        el.selector,
                        value,
                        f'Fill "{label}" ({el.element_type}/{el.input_type or "text"}) with "{value}"',
                    )
                )
            if buttons:
                btn = buttons[0]
                blabel = _element_label(btn)
                form_steps.append(
                    MonkeyStep("click", blabel, btn.selector, "", f'Click primary-ish button "{blabel}"')
                )
            form_steps.append(MonkeyStep("wait", "", "", "1000", "Wait 1s for validation / navigation"))
            form_steps.append(MonkeyStep("assert_no_crash", "", "", "", "Confirm page is still responsive"))
            field_list = ", ".join(f'"{x}"' for x in labels[:8])
            if len(labels) > 8:
                field_list += f", … (+{len(labels) - 8} more)"
            add_case(
                id=_next_case_id(used_ids, next_id),
                name=f"Form fuzz batch {chunk_i // chunk_size + 1}: fill {len(chunk)} field(s)",
                description=(
                    f"Monkey form fuzz for '{page_title}'. Fills discovered editable fields with "
                    f"realistic-random values (email/phone/password-aware): {field_list}. "
                    "Optionally clicks a visible button afterward to trigger submit/validation. "
                    "Goal is to catch client-side exceptions, broken validation UX, and crashes "
                    "from unexpected input — not to assert business correctness."
                ),
                priority="High",
                steps=form_steps,
                tags=["form", "fuzz", "input", "monkey"],
                objective="Stress input fields with generated data and observe UI stability.",
                coverage=f"{len(chunk)} input/textarea control(s): {field_list}",
                expected_result="No page crash; form may show validation errors (acceptable for monkey).",
                rationale="Invalid/random input frequently exposes unhandled exceptions in form handlers.",
            )

    # --- Per-control click coverage ---
    for el in buttons:
        label = _element_label(el)
        add_case(
            id=_next_case_id(used_ids, next_id),
            name=f"Click coverage: button “{label[:48]}”",
            description=(
                f"Isolated click coverage for button '{label}' on '{page_title}'. "
                f"Selector: `{el.selector}`. Opens the page, clicks this single control, waits briefly, "
                "and checks the page is still responsive. Useful to pinpoint which button triggers a crash "
                "when broader random-click suites fail."
            ),
            priority="High",
            steps=[
                MonkeyStep("goto", assessment.url, "", "", f"Open {assessment.url}"),
                MonkeyStep("click", label, el.selector, "", f'Click button "{label}"'),
                MonkeyStep("wait", "", "", "700", "Wait 0.7s for UI reaction"),
                MonkeyStep("assert_no_crash", "", "", "", "Confirm page is still responsive"),
            ],
            tags=["click", "button", "coverage"],
            objective=f'Verify clicking button "{label}" does not crash the page.',
            coverage=f"Single button control — tag={el.tag}, selector={el.selector}",
            expected_result="Click succeeds or fails softly; page document remains usable.",
            rationale="Per-control cases make failures actionable (exact control that broke).",
        )

    for el in links:
        label = _element_label(el)
        href_note = f" (href: {el.href})" if el.href else ""
        add_case(
            id=_next_case_id(used_ids, next_id),
            name=f"Click coverage: link “{label[:48]}”",
            description=(
                f"Isolated navigation/click coverage for link '{label}'{href_note} on '{page_title}'. "
                f"Selector: `{el.selector}`. Monkey testing does not assert the destination content — "
                "it only checks that activating the link does not hard-crash the browsing context."
            ),
            priority="Medium",
            steps=[
                MonkeyStep("goto", assessment.url, "", "", f"Open {assessment.url}"),
                MonkeyStep("click", label, el.selector, "", f'Click link "{label}"{href_note}'),
                MonkeyStep("wait", "", "", "800", "Wait 0.8s after navigation attempt"),
                MonkeyStep("assert_no_crash", "", "", "", "Confirm page is still responsive"),
            ],
            tags=["click", "link", "coverage", "navigation"],
            objective=f'Verify activating link "{label}" does not crash the page.',
            coverage=f"Single link control{href_note} — selector={el.selector}",
            expected_result="Page remains responsive after click (same or new URL is fine).",
            rationale="Broken href handlers and JS onclick errors often surface only on activation.",
        )

    for el in toggles:
        label = _element_label(el)
        add_case(
            id=_next_case_id(used_ids, next_id),
            name=f"Toggle coverage: {el.element_type} “{label[:48]}”",
            description=(
                f"Toggles {el.element_type} '{label}' on '{page_title}' via click to exercise "
                "state-change handlers (show/hide panels, enable submit, etc.)."
            ),
            priority="Medium",
            steps=[
                MonkeyStep("goto", assessment.url, "", "", f"Open {assessment.url}"),
                MonkeyStep("click", label, el.selector, "", f'Toggle {el.element_type} "{label}"'),
                MonkeyStep("wait", "", "", "500", "Wait 0.5s"),
                MonkeyStep("assert_no_crash", "", "", "", "Confirm page is still responsive"),
            ],
            tags=["toggle", el.element_type, "coverage"],
            objective=f'Verify toggling {el.element_type} "{label}" is safe.',
            coverage=f"{el.element_type} — selector={el.selector}",
            expected_result="Toggle interaction does not crash the page.",
            rationale="Checkbox/radio handlers frequently mutate DOM and can throw.",
        )

    # --- Per-input focused fill ---
    for el in fillables:
        label = _element_label(el)
        value = _fill_value_for(el)
        add_case(
            id=_next_case_id(used_ids, next_id),
            name=f"Input coverage: “{label[:48]}”",
            description=(
                f"Focused field coverage for '{label}' ({el.element_type}"
                f"{'/' + el.input_type if el.input_type else ''}) on '{page_title}'. "
                f"Enters generated value '{value}' using selector `{el.selector}`. "
                "Isolates field-level listeners (masking, autosuggest, oninput validation)."
            ),
            priority="Medium",
            steps=[
                MonkeyStep("goto", assessment.url, "", "", f"Open {assessment.url}"),
                MonkeyStep(
                    "fill",
                    label,
                    el.selector,
                    value,
                    f'Fill "{label}" with "{value}"',
                ),
                MonkeyStep("keypress", "", "", "Tab", "Press Tab to blur / move focus"),
                MonkeyStep("assert_no_crash", "", "", "", "Confirm page is still responsive"),
            ],
            tags=["input", "coverage", "fuzz"],
            objective=f'Verify typing into "{label}" and blurring does not crash the page.',
            coverage=f"Single field — name={el.name or '—'}, placeholder={el.placeholder or '—'}, selector={el.selector}",
            expected_result="Field accepts input; page stays responsive after blur.",
            rationale="Per-field cases localize which input listener throws.",
        )

    for el in selects:
        label = _element_label(el)
        add_case(
            id=_next_case_id(used_ids, next_id),
            name=f"Select coverage: “{label[:48]}”",
            description=(
                f"Changes dropdown '{label}' on '{page_title}' to option index 1 to exercise "
                f"onchange handlers. Selector: `{el.selector}`."
            ),
            priority="Medium",
            steps=[
                MonkeyStep("goto", assessment.url, "", "", f"Open {assessment.url}"),
                MonkeyStep(
                    "select",
                    label,
                    el.selector,
                    "1",
                    f'Select option index 1 on "{label}"',
                ),
                MonkeyStep("wait", "", "", "500", "Wait 0.5s for dependent UI updates"),
                MonkeyStep("assert_no_crash", "", "", "", "Confirm page is still responsive"),
            ],
            tags=["select", "coverage"],
            objective=f'Verify changing select "{label}" does not crash the page.',
            coverage=f"Single select — selector={el.selector}",
            expected_result="Selection applies (or soft-fails); page remains usable.",
            rationale="Dependent dropdowns and cascading filters often throw on change.",
        )

    # --- Keyboard & deep scroll suites ---
    add_case(
        id=_next_case_id(used_ids, next_id),
        name="Keyboard chaos: Tab / Escape / Arrow navigation",
        description=(
            f"Sends keyboard navigation keys (Tab, Escape, ArrowDown, Enter) on '{page_title}' "
            "without targeting a specific control. This exercises focus traps, modal dismiss handlers, "
            "and global key listeners that click-only suites miss."
        ),
        priority="Medium",
        steps=[
            MonkeyStep("goto", assessment.url, "", "", f"Open {assessment.url}"),
            MonkeyStep("keypress", "", "", "Tab", "Press Tab"),
            MonkeyStep("keypress", "", "", "Tab", "Press Tab again"),
            MonkeyStep("keypress", "", "", "ArrowDown", "Press ArrowDown"),
            MonkeyStep("keypress", "", "", "Escape", "Press Escape"),
            MonkeyStep("keypress", "", "", "Enter", "Press Enter"),
            MonkeyStep("assert_no_crash", "", "", "", "Confirm page is still responsive"),
        ],
        tags=["keyboard", "accessibility", "monkey"],
        objective="Exercise global keyboard handlers and focus movement safely.",
        coverage="Keyboard events: Tab×2, ArrowDown, Escape, Enter on the loaded page.",
        expected_result="No fatal error from key handlers; page remains responsive.",
        rationale="Keyboard paths are under-tested vs mouse and often hide focus-trap bugs.",
    )

    add_case(
        id=_next_case_id(used_ids, next_id),
        name="Deep scroll stress",
        description=(
            f"Performs repeated scroll deltas on '{page_title}' to stress lazy-loading, "
            "infinite scroll, and parallax/sticky components that only activate deep in the page."
        ),
        priority="Low",
        steps=[
            MonkeyStep("goto", assessment.url, "", "", f"Open {assessment.url}"),
            MonkeyStep("scroll", "", "", "800", "Scroll down 800px"),
            MonkeyStep("wait", "", "", "400", "Wait 0.4s"),
            MonkeyStep("scroll", "", "", "800", "Scroll down 800px"),
            MonkeyStep("wait", "", "", "400", "Wait 0.4s"),
            MonkeyStep("scroll", "", "", "1200", "Scroll down 1200px"),
            MonkeyStep("scroll", "", "", "-600", "Scroll up 600px"),
            MonkeyStep("assert_no_crash", "", "", "", "Confirm page is still responsive"),
        ],
        tags=["scroll", "lazy-load", "monkey"],
        objective="Stress scroll-triggered rendering and listeners.",
        coverage="Multi-step vertical scroll path (± deltas) on the target page.",
        expected_result="Scrolling completes without crashing the page.",
        rationale="Lazy widgets and infinite lists commonly throw during rapid scroll.",
    )

    # --- Mixed click trail using many clickables ---
    if clickables:
        trail = clickables if len(clickables) <= 12 else random.sample(clickables, 12)
        nav_steps = [MonkeyStep("goto", assessment.url, "", "", f"Open {assessment.url}")]
        trail_labels = []
        for el in trail:
            label = _element_label(el)
            trail_labels.append(f"{el.element_type}:{label}")
            nav_steps.append(
                MonkeyStep("click", label, el.selector, "", f'Click "{label}" ({el.element_type})')
            )
            nav_steps.append(MonkeyStep("wait", "", "", "500", "Wait 0.5s after interaction"))
        nav_steps.append(MonkeyStep("assert_no_crash", "", "", "", "Confirm page is still responsive"))
        add_case(
            id=_next_case_id(used_ids, next_id),
            name="UI chaos: multi-control click trail",
            description=(
                f"Sequential click trail across {len(trail)} visible controls on '{page_title}': "
                + "; ".join(trail_labels[:10])
                + ("…" if len(trail_labels) > 10 else "")
                + ". Order may navigate away; the oracle only checks that the browsing context survives."
            ),
            priority="High",
            steps=nav_steps,
            tags=["click", "trail", "monkey", "integration"],
            objective="Survive a longer chain of heterogeneous UI clicks.",
            coverage=f"{len(trail)} clickable controls in one session.",
            expected_result="No hard crash across the full click sequence.",
            rationale="Sequence bugs (state pollution) appear only when controls are chained.",
        )

    # --- Random walks to fill up to target_count ---
    while len(cases) < target_count:
        case_id = _next_case_id(used_ids, next_id)
        steps: list[MonkeyStep] = [
            MonkeyStep("goto", assessment.url, "", "", f"Open {assessment.url}")
        ]
        action_summary: list[str] = []
        for _ in range(max(2, steps_per_case - 1)):
            pool = []
            if fillables:
                pool.append("fill")
            if clickables:
                pool.append("click")
            if selects:
                pool.append("select")
            pool.extend(["scroll", "wait", "keypress"])
            action = random.choice(pool)

            if action == "fill" and fillables:
                el = random.choice(fillables)
                value = _fill_value_for(el)
                label = _element_label(el)
                steps.append(MonkeyStep("fill", label, el.selector, value, f'Fill "{label}" with "{value}"'))
                action_summary.append(f'fill "{label}"')
            elif action == "click" and clickables:
                el = random.choice(clickables)
                label = _element_label(el)
                steps.append(MonkeyStep("click", label, el.selector, "", f'Click "{label}"'))
                action_summary.append(f'click "{label}"')
            elif action == "select" and selects:
                el = random.choice(selects)
                label = _element_label(el)
                steps.append(
                    MonkeyStep("select", label, el.selector, "1", f'Select option index 1 on "{label}"')
                )
                action_summary.append(f'select "{label}"')
            elif action == "scroll":
                delta = random.choice([200, 400, 800, -200])
                steps.append(
                    MonkeyStep(
                        "scroll",
                        "",
                        "",
                        str(delta),
                        f"Scroll {'down' if delta > 0 else 'up'} {abs(delta)}px",
                    )
                )
                action_summary.append(f"scroll {delta}")
            elif action == "keypress":
                key = random.choice(["Tab", "Enter", "Escape", "ArrowDown"])
                steps.append(MonkeyStep("keypress", "", "", key, f"Press key {key}"))
                action_summary.append(f"key {key}")
            else:
                steps.append(MonkeyStep("wait", "", "", "500", "Wait 0.5s"))
                action_summary.append("wait")

        steps.append(MonkeyStep("assert_no_crash", "", "", "", "Confirm page is still responsive"))
        summary = "; ".join(action_summary)
        add_case(
            id=case_id,
            name=f"Monkey random walk #{case_id}",
            description=(
                f"Stochastic low-code walk on '{page_title}' built from the live element inventory. "
                f"Action mix: {summary}. Random walks increase odds of hitting rare state combinations "
                "that structured per-control cases do not cover. Failures here should be triaged by "
                "replaying the step list — not treated as functional assertions."
            ),
            priority=random.choice(["Low", "Medium", "High"]),
            steps=steps,
            tags=["monkey", "random", "exploratory"],
            objective="Explore uncommon interaction sequences for crash discovery.",
            coverage=f"Random mix of discovered controls — actions: {summary}",
            expected_result="Browsing context survives the random sequence.",
            rationale="Exploratory chaos finds edge-case state bugs missed by linear coverage.",
        )

    return cases


def cases_to_dataframe(cases: list[MonkeyTestCase]):
    import pandas as pd

    rows = []
    for c in cases:
        rows.append(
            {
                "ID": c.id,
                "Name": c.name,
                "Priority": c.priority,
                "Steps": len(c.steps),
                "Tags": ", ".join(c.tags),
                "Objective": c.objective,
                "Coverage": c.coverage,
                "Expected result": c.expected_result,
                "Description": c.description,
            }
        )
    return pd.DataFrame(rows)


def _run_step(page, step: MonkeyStep, base_url: str) -> StepResult:
    t0 = time.perf_counter()
    try:
        action = step.action
        if action == "goto":
            target = step.target or base_url
            page.goto(target, wait_until="domcontentloaded")
        elif action == "wait":
            page.wait_for_timeout(int(float(step.value or 500)))
        elif action == "scroll":
            delta = int(float(step.value or 400))
            page.mouse.wheel(0, delta)
            page.wait_for_timeout(200)
        elif action == "keypress":
            page.keyboard.press(step.value or "Tab")
        elif action == "fill":
            locator = page.locator(step.selector).first
            locator.wait_for(state="visible", timeout=5000)
            locator.click(timeout=3000)
            locator.fill(step.value or "", timeout=5000)
        elif action == "click":
            locator = page.locator(step.selector).first
            locator.wait_for(state="visible", timeout=5000)
            locator.click(timeout=5000, force=False)
            page.wait_for_timeout(300)
        elif action == "select":
            locator = page.locator(step.selector).first
            locator.wait_for(state="visible", timeout=5000)
            try:
                locator.select_option(index=int(step.value or 1))
            except Exception:
                options = locator.locator("option")
                if options.count() > 1:
                    locator.select_option(index=1)
        elif action == "assert_no_crash":
            # Soft health check: document is still available
            ready = page.evaluate("() => document.readyState")
            if ready not in ("interactive", "complete"):
                raise RuntimeError(f"Unexpected document.readyState={ready}")
        else:
            raise RuntimeError(f"Unknown action: {action}")

        return StepResult(
            step_index=0,
            description=step.description,
            status="PASS",
            detail="OK",
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        return StepResult(
            step_index=0,
            description=step.description,
            status="FAIL",
            detail=str(exc)[:400],
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )


def execute_test_case(
    test_case: MonkeyTestCase,
    base_url: str,
    timeout_ms: int = 15000,
    headless: bool = True,
    stop_on_fail: bool = False,
) -> TestRunResult:
    _ensure_playwright()
    from playwright.sync_api import sync_playwright

    base_url = normalize_url(base_url)
    console_errors: list[str] = []
    page_errors: list[str] = []
    step_results: list[StepResult] = []
    started_at = datetime.now().isoformat(timespec="seconds")
    t0 = time.perf_counter()
    screenshot_path = ""
    final_url = base_url
    overall = "PASS"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        page.on(
            "console",
            lambda msg: console_errors.append(f"[{msg.type}] {msg.text}")
            if msg.type == "error"
            else None,
        )
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        for idx, step in enumerate(test_case.steps, 1):
            result = _run_step(page, step, base_url)
            result.step_index = idx
            step_results.append(result)
            if result.status == "FAIL":
                overall = "FAIL"
                if stop_on_fail:
                    break

        final_url = page.url
        shot = SCREENSHOT_DIR / f"run_{_safe_filename(test_case.id)}_{int(time.time())}.png"
        try:
            page.screenshot(path=str(shot), full_page=False)
            screenshot_path = str(shot)
        except Exception:
            screenshot_path = ""
        browser.close()

    finished_at = datetime.now().isoformat(timespec="seconds")
    if page_errors and overall == "PASS":
        overall = "WARN"

    return TestRunResult(
        test_id=test_case.id,
        test_name=test_case.name,
        status=overall,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=int((time.perf_counter() - t0) * 1000),
        steps=step_results,
        screenshot_path=screenshot_path,
        console_errors=console_errors[:30],
        page_errors=page_errors[:30],
        final_url=final_url,
    )


def execute_selected_cases(
    test_cases: list[MonkeyTestCase],
    base_url: str,
    headless: bool = True,
    stop_on_fail: bool = False,
    progress_callback=None,
) -> list[TestRunResult]:
    results: list[TestRunResult] = []
    total = len(test_cases)
    for i, tc in enumerate(test_cases, 1):
        if progress_callback:
            progress_callback(i, total, tc.name)
        result = execute_test_case(
            tc,
            base_url=base_url,
            headless=headless,
            stop_on_fail=stop_on_fail,
        )
        results.append(result)
    return results


def assess_webpage_safe(
    url: str,
    timeout_ms: int = 30000,
    headless: bool = True,
) -> PageAssessment:
    """Assess a page from Streamlit (subprocess-isolated Playwright)."""
    data = _subprocess_json_job(
        "assess",
        {"url": url, "timeout_ms": timeout_ms, "headless": headless},
        timeout=max(60, timeout_ms // 1000 + 45),
    )
    elements = [PageElement(**e) for e in data.get("elements", [])]
    return PageAssessment(
        url=data["url"],
        title=data.get("title", ""),
        final_url=data.get("final_url", ""),
        status=data.get("status", ""),
        load_ms=int(data.get("load_ms") or 0),
        elements=elements,
        console_errors=data.get("console_errors", []),
        page_errors=data.get("page_errors", []),
        screenshot_path=data.get("screenshot_path", ""),
        assessed_at=data.get("assessed_at", ""),
        meta=data.get("meta", {}),
    )


def execute_selected_cases_safe(
    test_cases: list[MonkeyTestCase],
    base_url: str,
    headless: bool = True,
    stop_on_fail: bool = False,
    progress_callback=None,
) -> list[TestRunResult]:
    """Execute monkey cases from Streamlit (subprocess-isolated Playwright)."""
    results: list[TestRunResult] = []
    total = len(test_cases)
    for i, tc in enumerate(test_cases, 1):
        if progress_callback:
            progress_callback(i, total, tc.name)
        data = _subprocess_json_job(
            "execute",
            {
                "test_case": tc.to_dict(),
                "base_url": base_url,
                "timeout_ms": 15000,
                "headless": headless,
                "stop_on_fail": stop_on_fail,
            },
            timeout=180,
        )
        steps = [StepResult(**s) for s in data.get("steps", [])]
        results.append(
            TestRunResult(
                test_id=data["test_id"],
                test_name=data["test_name"],
                status=data["status"],
                started_at=data.get("started_at", ""),
                finished_at=data.get("finished_at", ""),
                duration_ms=int(data.get("duration_ms") or 0),
                steps=steps,
                screenshot_path=data.get("screenshot_path", ""),
                console_errors=data.get("console_errors", []),
                page_errors=data.get("page_errors", []),
                final_url=data.get("final_url", ""),
            )
        )
    return results


def export_cases_json(cases: list[MonkeyTestCase]) -> str:
    return json.dumps([c.to_dict() for c in cases], indent=2)


def export_cases_low_code(cases: list[MonkeyTestCase]) -> str:
    blocks = []
    for c in cases:
        blocks.append(c.to_low_code_script())
        blocks.append("\n" + ("-" * 48) + "\n")
    return "\n".join(blocks)
