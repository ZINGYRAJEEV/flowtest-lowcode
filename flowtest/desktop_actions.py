"""
Windows desktop UI helpers (local only — not Streamlit Cloud).

Uses pywinauto (UI Automation). Install:
  pip install -r requirements-desktop.txt
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from flowtest.browser_setup import is_streamlit_cloud
from flowtest.storage import ARTIFACTS_DIR


def ensure_desktop_available() -> None:
    if is_streamlit_cloud():
        raise RuntimeError(
            "Desktop UI steps cannot run on Streamlit Cloud. Run FlowTest locally on Windows."
        )
    if not sys.platform.startswith("win"):
        raise RuntimeError("Desktop UI automation currently supports Windows only.")
    try:
        import pywinauto  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Desktop deps missing. Install locally: pip install -r requirements-desktop.txt"
        ) from exc


def _desktop():
    from pywinauto import Desktop

    return Desktop(backend="uia")


def list_windows(limit: int = 40) -> list[dict[str, Any]]:
    ensure_desktop_available()
    out: list[dict[str, Any]] = []
    for w in _desktop().windows():
        try:
            title = (w.window_text() or "").strip()
            if not title:
                continue
            out.append(
                {
                    "title": title[:120],
                    "class_name": getattr(w.element_info, "class_name", "") or "",
                    "handle": int(getattr(w.element_info, "handle", 0) or 0),
                }
            )
        except Exception:
            continue
        if len(out) >= limit:
            break
    return out


def focus_window(title: str, timeout_ms: int = 15000) -> str:
    ensure_desktop_available()
    title = (title or "").strip()
    if not title:
        raise RuntimeError("Window title is empty")
    deadline = time.time() + max(timeout_ms, 500) / 1000.0
    last_err = "Window not found"
    while time.time() < deadline:
        try:
            win = _desktop().window(title_re=f".*{_re_escape(title)}.*")
            win.wait("exists enabled visible", timeout=1)
            win.set_focus()
            return f"Focused: {(win.window_text() or title)[:80]}"
        except Exception as exc:
            last_err = str(exc)
            time.sleep(0.35)
    raise RuntimeError(f"Could not focus window matching {title!r}: {last_err[:200]}")


def _re_escape(text: str) -> str:
    import re

    return re.escape(text)


def _resolve_window(window_title: str):
    title = (window_title or "").strip()
    if not title:
        # Prefer the foreground / active top-level window
        try:
            return _desktop().get_active()
        except Exception:
            wins = [w for w in _desktop().windows() if (w.window_text() or "").strip()]
            if not wins:
                raise RuntimeError("No desktop window available — set window_title")
            return wins[0]
    return _desktop().window(title_re=f".*{_re_escape(title)}.*")


def _find_control(win, name: str, control_type: str = "", auto_id: str = ""):
    kwargs: dict[str, Any] = {}
    if auto_id:
        kwargs["auto_id"] = auto_id
    if control_type:
        kwargs["control_type"] = control_type
    if name:
        kwargs["title_re"] = f".*{_re_escape(name)}.*"
    if not kwargs:
        raise RuntimeError("Provide control name, automation id, or both")
    ctrl = win.child_window(**kwargs)
    ctrl.wait("exists enabled visible", timeout=8)
    return ctrl


def click_control(
    name: str = "",
    window_title: str = "",
    control_type: str = "",
    auto_id: str = "",
    timeout_ms: int = 15000,
) -> str:
    ensure_desktop_available()
    deadline = time.time() + max(timeout_ms, 500) / 1000.0
    last_err = "Control not found"
    while time.time() < deadline:
        try:
            win = _resolve_window(window_title)
            win.set_focus()
            ctrl = _find_control(win, name=name, control_type=control_type, auto_id=auto_id)
            ctrl.click_input()
            label = name or auto_id or control_type or "control"
            return f"Clicked desktop control: {label}"
        except Exception as exc:
            last_err = str(exc)
            time.sleep(0.35)
    raise RuntimeError(f"Desktop click failed: {last_err[:300]}")


def type_text(
    text: str,
    window_title: str = "",
    name: str = "",
    control_type: str = "",
    auto_id: str = "",
    clear: bool = False,
    timeout_ms: int = 15000,
) -> str:
    ensure_desktop_available()
    deadline = time.time() + max(timeout_ms, 500) / 1000.0
    last_err = "Control not found"
    while time.time() < deadline:
        try:
            win = _resolve_window(window_title)
            win.set_focus()
            if name or auto_id:
                ctrl = _find_control(win, name=name, control_type=control_type, auto_id=auto_id)
                ctrl.set_focus()
                if clear:
                    ctrl.type_keys("^a{BACKSPACE}", with_spaces=True, set_foreground=True)
                ctrl.type_keys(text, with_spaces=True, set_foreground=True)
            else:
                if clear:
                    win.type_keys("^a{BACKSPACE}", with_spaces=True, set_foreground=True)
                win.type_keys(text, with_spaces=True, set_foreground=True)
            return f"Typed {len(text)} char(s) into desktop UI"
        except Exception as exc:
            last_err = str(exc)
            time.sleep(0.35)
    raise RuntimeError(f"Desktop type failed: {last_err[:300]}")


def send_keys(keys: str, window_title: str = "") -> str:
    """Send pywinauto key sequence, e.g. ^s, {ENTER}, %{F4}."""
    ensure_desktop_available()
    keys = (keys or "").strip()
    if not keys:
        raise RuntimeError("Keys are empty")
    win = _resolve_window(window_title)
    win.set_focus()
    win.type_keys(keys, with_spaces=True, set_foreground=True)
    return f"Sent keys: {keys[:60]}"


def wait_ms(ms: int) -> str:
    time.sleep(max(0, int(ms)) / 1000.0)
    return f"Waited {int(ms)} ms"


def screenshot(label: str = "desktop") -> str:
    ensure_desktop_available()
    try:
        from PIL import ImageGrab
    except ImportError as exc:
        raise RuntimeError(
            "Pillow required for desktop screenshots. pip install -r requirements-desktop.txt"
        ) from exc
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (label or "desktop"))[:40]
    path = ARTIFACTS_DIR / f"desktop_{safe}_{int(time.time())}.png"
    ImageGrab.grab().save(str(path))
    return str(path)


def assert_window(title: str, timeout_ms: int = 10000) -> str:
    ensure_desktop_available()
    title = (title or "").strip()
    if not title:
        raise RuntimeError("Window title is empty")
    deadline = time.time() + max(timeout_ms, 500) / 1000.0
    while time.time() < deadline:
        for item in list_windows(limit=80):
            if title.lower() in item["title"].lower():
                return f"Window present: {item['title']}"
        time.sleep(0.35)
    raise RuntimeError(f"Desktop window matching {title!r} not found")


def assert_control(
    name: str = "",
    window_title: str = "",
    control_type: str = "",
    auto_id: str = "",
    timeout_ms: int = 10000,
) -> str:
    ensure_desktop_available()
    deadline = time.time() + max(timeout_ms, 500) / 1000.0
    last_err = "not found"
    while time.time() < deadline:
        try:
            win = _resolve_window(window_title)
            ctrl = _find_control(win, name=name, control_type=control_type, auto_id=auto_id)
            return f"Control present: {(name or auto_id or ctrl.window_text() or 'ok')[:80]}"
        except Exception as exc:
            last_err = str(exc)
            time.sleep(0.35)
    raise RuntimeError(f"Desktop control not found: {last_err[:300]}")
