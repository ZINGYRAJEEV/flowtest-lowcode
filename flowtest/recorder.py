"""
FlowTest — browser session recorder.

Opens a headed Chromium window, captures navigations / clicks / fills / selects,
and converts them into low-code TestStep definitions.
"""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urlparse

from flowtest.models import TestStep, new_id

_RECORDER_JS = r"""
(() => {
  if (window.__flowtestRecorderInstalled) return;
  window.__flowtestRecorderInstalled = true;
  window.__flowtest_done = false;
  window.__flowtest_lastSelection = { text: '', selector: 'body' };

  const cssPath = (el) => {
    if (!el || el.nodeType !== 1) return '';
    // Prefer stable ForgeRock / Horizon attributes over volatile floatingLabel ids
    const name = el.getAttribute && el.getAttribute('name');
    if (name && /^callback_\d+$/i.test(name)) {
      return `[name="${name}"]`;
    }
    const vv = el.getAttribute && el.getAttribute('data-vv-as');
    if (vv) {
      const esc = (typeof CSS !== 'undefined' && CSS.escape) ? CSS.escape(vv) : vv.replace(/"/g, '\\"');
      return `[data-vv-as="${esc}"]`;
    }
    const testId = el.getAttribute && el.getAttribute('data-testid');
    if (testId && testId !== 'input-') {
      const esc = (typeof CSS !== 'undefined' && CSS.escape) ? CSS.escape(testId) : testId;
      return `[data-testid="${esc}"]`;
    }
    if (el.id) {
      const id = el.id;
      // Skip volatile auto-generated floating label ids — fall through to name/path
      if (!/^floatingLabelInput\d+$/i.test(id)) {
        if (typeof CSS !== 'undefined' && CSS.escape) return `#${CSS.escape(id)}`;
        return `#${id.replace(/([^a-zA-Z0-9_-])/g, '\\$1')}`;
      }
      if (name) return `[name="${name}"]`;
    }
    if (name) return `[name="${name}"]`;
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 6) {
      let part = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(c => c.tagName === node.tagName);
        if (siblings.length > 1) {
          part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
        }
      }
      parts.unshift(part);
      node = parent;
      if (node && node.tagName && node.tagName.toLowerCase() === 'body') {
        parts.unshift('body');
        break;
      }
    }
    return parts.join(' > ');
  };

  const labelOf = (el) => {
    return (el.getAttribute('aria-label')
      || el.getAttribute('name')
      || el.getAttribute('placeholder')
      || el.getAttribute('title')
      || (el.innerText || '').trim().slice(0, 60)
      || el.tagName.toLowerCase());
  };

  const emit = (payload) => {
    try {
      if (window.__flowtest_record) {
        window.__flowtest_record(payload);
      }
    } catch (e) {}
  };

  const escapeHtml = (s) => String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  const bar = document.createElement('div');
  bar.id = 'flowtest-recorder-bar';
  bar.style.cssText = [
    'position:fixed', 'z-index:2147483647', 'left:12px', 'right:12px', 'top:12px',
    'display:flex', 'flex-wrap:wrap', 'gap:10px', 'align-items:center', 'justify-content:space-between',
    'padding:10px 14px', 'border-radius:10px',
    'background:#241e1b', 'color:#fffcfb', 'font:600 13px/1.35 system-ui,sans-serif',
    'box-shadow:0 8px 24px rgba(0,0,0,.35)'
  ].join(';');
  bar.innerHTML = `
    <div style="flex:1;min-width:220px;">
      <div style="color:#ff9db3;letter-spacing:.04em;text-transform:uppercase;font-size:11px;">FlowTest recording</div>
      <div id="flowtest-help" style="font-weight:500;opacity:.92;margin-top:2px;">
        Click · type · navigate. <b>Select text</b> on the page, then click <b>Assert selection</b> (or press <b>A</b>).
      </div>
      <div id="flowtest-selection-preview" style="
        margin-top:6px;font-weight:500;font-size:12px;color:#ffc6d3;display:none;
        max-width:720px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
      </div>
    </div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
      <button id="flowtest-assert-btn" type="button" style="
        border:0;border-radius:8px;padding:8px 12px;cursor:pointer;
        background:#ffc6d3;color:#241e1b;font-weight:700;opacity:0.45;" disabled>
        Assert selection
      </button>
      <button id="flowtest-finish-btn" type="button" style="
        border:0;border-radius:8px;padding:8px 14px;cursor:pointer;
        background:#f83b66;color:#fff;font-weight:700;">Finish recording</button>
    </div>
  `;

  const updateAssertButton = () => {
    const btn = document.getElementById('flowtest-assert-btn');
    const preview = document.getElementById('flowtest-selection-preview');
    const text = (window.__flowtest_lastSelection && window.__flowtest_lastSelection.text) || '';
    if (!btn || !preview) return;
    if (text) {
      btn.disabled = false;
      btn.style.opacity = '1';
      btn.style.cursor = 'pointer';
      preview.style.display = 'block';
      preview.innerHTML = 'Selected: “' + escapeHtml(text.slice(0, 120)) + (text.length > 120 ? '…' : '') + '”';
    } else {
      btn.disabled = true;
      btn.style.opacity = '0.45';
      btn.style.cursor = 'not-allowed';
      preview.style.display = 'none';
      preview.textContent = '';
    }
  };

  const captureSelection = () => {
    const sel = window.getSelection && window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) {
      // keep last selection until cleared intentionally
      return;
    }
    const text = (sel.toString() || '').replace(/\s+/g, ' ').trim();
    if (!text || text.length < 2) return;
    if (text.length > 300) return; // ignore huge accidental selections

    let node = sel.getRangeAt(0).commonAncestorContainer;
    if (node && node.nodeType === 3) node = node.parentElement;
    let el = node;
    if (el && el.closest && el.closest('#flowtest-recorder-bar')) return;

    // Prefer a reasonably small readable container
    while (el && el !== document.body) {
      const tag = (el.tagName || '').toLowerCase();
      if (['p','h1','h2','h3','h4','h5','h6','li','td','th','button','a','label','span','div','section','article'].includes(tag)) {
        break;
      }
      el = el.parentElement;
    }
    const selector = cssPath(el || document.body) || 'body';
    window.__flowtest_lastSelection = { text, selector };
    updateAssertButton();
  };

  const assertSelection = () => {
    const sel = window.__flowtest_lastSelection || {};
    const text = (sel.text || '').trim();
    if (!text) return;
    emit({
      type: 'assert_text',
      text,
      selector: sel.selector || 'body',
      ts: Date.now(),
    });
    // Visual confirmation
    const preview = document.getElementById('flowtest-selection-preview');
    if (preview) {
      preview.style.display = 'block';
      preview.style.color = '#86efac';
      preview.textContent = '✓ Assertion added: “' + text.slice(0, 100) + (text.length > 100 ? '…' : '') + '”';
      setTimeout(() => {
        preview.style.color = '#ffc6d3';
        updateAssertButton();
      }, 1600);
    }
    // Clear selection highlight but keep last text available
    try { window.getSelection().removeAllRanges(); } catch (e) {}
  };

  const wireBar = () => {
    const finish = document.getElementById('flowtest-finish-btn');
    const assertBtn = document.getElementById('flowtest-assert-btn');
    if (finish && !finish.__wired) {
      finish.__wired = true;
      finish.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        window.__flowtest_done = true;
        emit({ type: 'finish', ts: Date.now() });
        finish.textContent = 'Saving…';
        finish.disabled = true;
      }, true);
    }
    if (assertBtn && !assertBtn.__wired) {
      assertBtn.__wired = true;
      assertBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        assertSelection();
      }, true);
    }
    updateAssertButton();
  };

  const mountBar = () => {
    if (!document.body) return;
    if (!document.getElementById('flowtest-recorder-bar')) {
      document.body.appendChild(bar);
    }
    wireBar();
  };
  if (document.body) mountBar();
  else document.addEventListener('DOMContentLoaded', mountBar);
  setInterval(mountBar, 1000);

  document.addEventListener('mouseup', (e) => {
    if (e.target && e.target.closest && e.target.closest('#flowtest-recorder-bar')) return;
    setTimeout(captureSelection, 10);
  }, true);

  document.addEventListener('keyup', (e) => {
    if (e.target && e.target.closest && e.target.closest('#flowtest-recorder-bar')) return;
    // Don't steal typing in inputs
    const tag = (e.target && e.target.tagName || '').toLowerCase();
    if (['input','textarea','select'].includes(tag) || e.target.isContentEditable) return;
    if (e.key === 'a' || e.key === 'A') {
      if (window.__flowtest_lastSelection && window.__flowtest_lastSelection.text) {
        e.preventDefault();
        assertSelection();
      }
    }
  }, true);

  document.addEventListener('click', (e) => {
    const t = e.target;
    if (!t || !t.closest) return;
    if (t.closest('#flowtest-recorder-bar')) return;
    // If user is finishing a text selection, skip click capture
    const sel = window.getSelection && window.getSelection();
    if (sel && !sel.isCollapsed && (sel.toString() || '').trim().length >= 2) {
      captureSelection();
      return;
    }
    const el = t.closest('a,button,input,select,textarea,[role="button"],[onclick]') || t;
    if (el.tagName && el.tagName.toLowerCase() === 'select') return;
    emit({
      type: 'click',
      selector: cssPath(el),
      text: (el.innerText || el.value || '').trim().slice(0, 80),
      tag: (el.tagName || '').toLowerCase(),
      inputType: (el.getAttribute && el.getAttribute('type')) || '',
      label: labelOf(el),
      href: el.getAttribute && el.getAttribute('href') || '',
      ts: Date.now(),
    });
  }, true);

  const onFieldCommit = (el) => {
    if (!el || !el.tagName) return;
    const tag = el.tagName.toLowerCase();
    if (tag === 'select') {
      emit({
        type: 'select',
        selector: cssPath(el),
        label: el.options && el.selectedIndex >= 0 ? el.options[el.selectedIndex].text : '',
        index: el.selectedIndex,
        name: labelOf(el),
        ts: Date.now(),
      });
      return;
    }
    if (tag !== 'input' && tag !== 'textarea') return;
    const inputType = (el.getAttribute('type') || 'text').toLowerCase();
    if (['button', 'submit', 'reset', 'checkbox', 'radio', 'file', 'image'].includes(inputType)) return;
    emit({
      type: 'fill',
      selector: cssPath(el),
      value: el.value || '',
      inputType,
      name: labelOf(el),
      ts: Date.now(),
    });
  };

  document.addEventListener('change', (e) => onFieldCommit(e.target), true);
  document.addEventListener('blur', (e) => {
    const t = e.target;
    if (t && t.tagName && ['INPUT', 'TEXTAREA'].includes(t.tagName)) onFieldCommit(t);
  }, true);
})();
"""


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("Start URL is required")
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    if not urlparse(url).netloc:
        raise ValueError("Invalid URL")
    return url


def _dedupe_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse noisy click-before-fill and repeated fills on the same field."""
    cleaned: list[dict[str, Any]] = []
    for ev in events:
        et = ev.get("type")
        if et == "finish":
            continue
        if et == "click":
            tag = (ev.get("tag") or "").lower()
            itype = (ev.get("inputType") or "").lower()
            # Skip clicks that are just focusing inputs (fill will follow)
            if tag in ("input", "textarea") and itype not in ("button", "submit", "checkbox", "radio"):
                continue
        if et == "fill" and cleaned and cleaned[-1].get("type") == "fill":
            if cleaned[-1].get("selector") == ev.get("selector"):
                cleaned[-1] = ev
                continue
        if et == "goto" and cleaned and cleaned[-1].get("type") == "goto":
            if cleaned[-1].get("url") == ev.get("url"):
                continue
            cleaned[-1] = ev
            continue
        if et == "assert_text" and cleaned and cleaned[-1].get("type") == "assert_text":
            if cleaned[-1].get("text") == ev.get("text") and cleaned[-1].get("selector") == ev.get("selector"):
                continue
        cleaned.append(ev)
    return cleaned


def events_to_steps(events: list[dict[str, Any]], replace_base_url: str | None = None) -> list[TestStep]:
    steps: list[TestStep] = []
    base = (replace_base_url or "").rstrip("/")

    def _auto_wait(selector: str, label: str = "", state: str = "attached") -> None:
        sel = (selector or "").strip()
        if not sel:
            return
        # Avoid duplicate wait_for for the same selector back-to-back
        if steps and steps[-1].type == "ui.wait_for" and (steps[-1].config or {}).get("selector") == sel:
            return
        cfg: dict[str, Any] = {"selector": sel, "timeout_ms": 30000, "state": state}
        if str(label).startswith("callback_"):
            cfg["name"] = str(label)
        steps.append(
            TestStep(
                id=new_id("stp_"),
                type="ui.wait_for",
                name=f"Wait for {(label or sel)[:40]}",
                # "attached" — hidden polyfill inputs never become Playwright-visible
                config=cfg,
                notes="Auto-wait (recorded)",
            )
        )

    for ev in _dedupe_events(events):
        et = ev.get("type")
        if et == "goto":
            url = ev.get("url") or ""
            if base and url.startswith(base):
                suffix = url[len(base) :] or "/"
                url_cfg = "{{BASE_URL}}" + ("" if suffix == "/" and url.rstrip("/") == base else suffix)
                if url.rstrip("/") == base:
                    url_cfg = "{{BASE_URL}}"
            else:
                url_cfg = url
            steps.append(
                TestStep(
                    id=new_id("stp_"),
                    type="ui.goto",
                    name=f"Navigate to {urlparse(url).path or url}",
                    config={"url": url_cfg, "timeout_ms": 30000},
                    notes="Recorded",
                )
            )
            # Let SPA settle after navigation
            steps.append(
                TestStep(
                    id=new_id("stp_"),
                    type="ui.wait",
                    name="Wait after navigate",
                    config={"ms": 500},
                    notes="Auto-wait (recorded)",
                )
            )
        elif et == "click":
            selector = ev.get("selector") or ""
            text = (ev.get("text") or "").strip()
            label = ev.get("label") or text or selector
            _auto_wait(selector, str(label), state="visible")
            cfg: dict[str, Any] = {"selector": selector, "text": "", "timeout_ms": 30000}
            steps.append(
                TestStep(
                    id=new_id("stp_"),
                    type="ui.click",
                    name=f"Click {label[:50]}",
                    config=cfg,
                    notes="Recorded",
                )
            )
        elif et == "fill":
            selector = ev.get("selector") or ""
            value = ev.get("value") or ""
            # Skip empty fills — blur on untouched/readonly fields often records fill("")
            # which fails on readonly SSN-style inputs during replay.
            if str(value).strip() == "":
                continue
            name = ev.get("name") or selector
            _auto_wait(selector, str(name), state="attached")
            steps.append(
                TestStep(
                    id=new_id("stp_"),
                    type="ui.fill",
                    name=f"Fill {str(name)[:40]}",
                    config={
                        "selector": selector,
                        "value": value,
                        "clear": True,
                        "timeout_ms": 30000,
                        "name": name if str(name).startswith("callback_") else "",
                    },
                    notes="Recorded",
                )
            )
        elif et == "select":
            selector = ev.get("selector") or ""
            label = ev.get("label") or ""
            index = int(ev.get("index") or 0)
            name = ev.get("name") or selector
            _auto_wait(selector, str(name), state="attached")
            steps.append(
                TestStep(
                    id=new_id("stp_"),
                    type="ui.select",
                    name=f"Select on {str(name)[:40]}",
                    config={"selector": selector, "label": label, "index": index, "timeout_ms": 30000},
                    notes="Recorded",
                )
            )
        elif et == "assert_text":
            text = (ev.get("text") or "").strip()
            selector = (ev.get("selector") or "body").strip() or "body"
            if not text:
                continue
            # Deep nth-of-type paths break after SPA re-renders — assert against body
            if "nth-of-type" in selector or selector.count(">") >= 3:
                selector = "body"
            short = text if len(text) <= 48 else text[:45] + "..."
            steps.append(
                TestStep(
                    id=new_id("stp_"),
                    type="assert.text_contains",
                    name=f'Assert text "{short}"',
                    config={"selector": selector, "text": text, "timeout_ms": 30000, "ignore_case": True},
                    notes="Recorded from text selection",
                )
            )
        elif et == "wait":
            steps.append(
                TestStep(
                    id=new_id("stp_"),
                    type="ui.wait",
                    name="Wait",
                    config={"ms": int(ev.get("ms") or 500)},
                    notes="Recorded",
                )
            )
    return steps


def record_browser_session(
    start_url: str,
    replace_base_url: str | None = None,
    max_seconds: int = 600,
) -> dict[str, Any]:
    """
    Open a headed browser, record interactions until the user clicks
    "Finish recording" or closes the window.
    """
    from playwright.sync_api import sync_playwright

    start_url = _normalize_url(start_url)
    events: list[dict[str, Any]] = []
    started = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = browser.new_context(no_viewport=True, ignore_https_errors=True)
        page = context.new_page()

        def _on_record(source, payload):  # noqa: ARG001
            if isinstance(payload, dict):
                events.append(payload)

        page.expose_binding("__flowtest_record", _on_record)
        page.add_init_script(_RECORDER_JS)

        def on_nav(frame):
            if frame != page.main_frame:
                return
            url = frame.url
            if url and not url.startswith("about:"):
                events.append({"type": "goto", "url": url, "ts": int(time.time() * 1000)})

        page.on("framenavigated", on_nav)

        page.goto(start_url, wait_until="domcontentloaded")
        # Ensure banner/script active on first document
        try:
            page.evaluate(_RECORDER_JS)
        except Exception:
            pass

        # If first goto wasn't captured by listener yet
        if not any(e.get("type") == "goto" for e in events):
            events.insert(0, {"type": "goto", "url": page.url, "ts": int(time.time() * 1000)})

        while True:
            if time.time() - started > max_seconds:
                break
            try:
                if not browser.is_connected():
                    break
                done = page.evaluate("() => window.__flowtest_done === true")
                if done:
                    page.wait_for_timeout(300)
                    break
            except Exception:
                # Page/browser closed
                break
            page.wait_for_timeout(350)

        try:
            browser.close()
        except Exception:
            pass

    steps = events_to_steps(events, replace_base_url=replace_base_url)
    return {
        "events": events,
        "steps": [s.to_dict() for s in steps],
        "count": len(steps),
        "start_url": start_url,
    }


def record_browser_session_safe(
    start_url: str,
    replace_base_url: str | None = None,
    max_seconds: int = 600,
    timeout: int | None = None,
) -> dict[str, Any]:
    """
    Run the recorder in a fresh Python subprocess (not ProcessPoolExecutor).

    Streamlit on Windows uses app.py as __main__; process-pool workers re-import
    it and crash. A `-m flowtest.recorder_job` child avoids that.
    """
    import json
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    wait = timeout if timeout is not None else max_seconds + 120
    payload = {
        "start_url": start_url,
        "replace_base_url": replace_base_url,
        "max_seconds": max_seconds,
    }

    with tempfile.TemporaryDirectory(prefix="flowtest_rec_") as tmp:
        tmp_path = Path(tmp)
        in_path = tmp_path / "in.json"
        out_path = tmp_path / "out.json"
        in_path.write_text(json.dumps(payload), encoding="utf-8")

        env = {**dict(**{k: v for k, v in __import__("os").environ.items()})}
        # Ensure project root is importable
        py_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(root) + ((";" + py_path) if py_path else "")

        proc = subprocess.run(
            [sys.executable, "-m", "flowtest.recorder_job", str(in_path), str(out_path)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=wait,
            env=env,
        )

        if out_path.exists():
            result = json.loads(out_path.read_text(encoding="utf-8"))
            if result.get("error") and proc.returncode != 0:
                raise RuntimeError(
                    result.get("error")
                    or (proc.stderr or proc.stdout or "Recorder process failed")
                )
            if proc.returncode != 0 and not result.get("steps"):
                raise RuntimeError(
                    result.get("error")
                    or (proc.stderr or proc.stdout or f"Recorder exited {proc.returncode}")
                )
            return result

        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(err or f"Recorder exited with code {proc.returncode}")


def steps_from_recording(result: dict[str, Any]) -> list[TestStep]:
    return [TestStep(**s) for s in result.get("steps", [])]
