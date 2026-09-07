"""
FlowTest — Windows desktop session recorder.

Shows an always-on-top control panel. Captures clicks / typing into desktop.* steps.
Run via subprocess (desktop_recorder_job) so Streamlit on Windows stays stable.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Any

from flowtest.models import TestStep, new_id


def _ensure_env() -> None:
    from flowtest.desktop_actions import ensure_desktop_available

    ensure_desktop_available()
    try:
        import pynput  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Desktop recorder needs pynput. Install: pip install -r requirements-desktop.txt"
        ) from exc


def _uia():
    from comtypes.client import CreateObject, GetModule

    GetModule("UIAutomationCore.dll")
    from comtypes.gen.UIAutomationClient import CUIAutomation

    return CreateObject(CUIAutomation)


def _point_element(x: int, y: int) -> dict[str, str]:
    """Resolve UI Automation element under screen coordinates."""
    try:
        from comtypes.client import GetModule

        GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import tagPOINT

        uia = _uia()
        el = uia.ElementFromPoint(tagPOINT(int(x), int(y)))
        if not el:
            return {}

        def _safe(node, attr: str) -> str:
            try:
                v = getattr(node, attr)
                return (str(v) if v is not None else "").strip()
            except Exception:
                return ""

        # Prefer a named actionable ancestor (button/edit/menuitem) when leaf is empty Pane
        best = el
        walker = uia.ControlViewWalker
        cur = el
        for _ in range(8):
            name = _safe(cur, "CurrentName")
            auto_id = _safe(cur, "CurrentAutomationId")
            try:
                ctype_id = int(cur.CurrentControlType)
            except Exception:
                ctype_id = 0
            if (name or auto_id) and ctype_id in (
                50000, 50003, 50004, 50006, 50008, 50011, 50013, 50018, 50019,
            ):
                best = cur
                break
            if name and ctype_id not in (50032, 50033):  # not Window/Pane alone
                best = cur
            try:
                parent = walker.GetParentElement(cur)
            except Exception:
                parent = None
            if not parent:
                break
            cur = parent

        name = _safe(best, "CurrentName")
        auto_id = _safe(best, "CurrentAutomationId")
        class_name = _safe(best, "CurrentClassName")
        try:
            ctype_id = int(best.CurrentControlType)
        except Exception:
            ctype_id = None
        control_type = _control_type_name(ctype_id)
        window_title = _top_window_title(uia, best) or _window_from_point(x, y)
        return {
            "name": name[:80],
            "auto_id": auto_id[:80],
            "control_type": control_type,
            "class_name": class_name[:80],
            "window_title": (window_title or "")[:100],
        }
    except Exception:
        return {
            "window_title": _window_from_point(x, y),
            "name": "",
            "auto_id": "",
            "control_type": "",
            "class_name": "",
        }


_CONTROL_TYPES = {
    50000: "Button",
    50003: "ComboBox",
    50004: "Edit",
    50006: "CheckBox",
    50008: "ListItem",
    50011: "MenuItem",
    50013: "RadioButton",
    50018: "TabItem",
    50019: "Text",
    50020: "ToolBar",
    50025: "Menu",
    50026: "MenuBar",
    50032: "Window",
    50033: "Pane",
}


def _control_type_name(ctype_id: int | None) -> str:
    if ctype_id is None:
        return ""
    return _CONTROL_TYPES.get(int(ctype_id), "")


def _top_window_title(uia, el) -> str:
    try:
        walker = uia.ControlViewWalker
        cur = el
        for _ in range(24):
            try:
                if int(cur.CurrentControlType) == 50032:  # Window
                    return (str(cur.CurrentName or "")).strip()
            except Exception:
                pass
            parent = walker.GetParentElement(cur)
            if not parent:
                break
            cur = parent
        return (str(getattr(el, "CurrentName", "") or "")).strip()
    except Exception:
        return ""


def _window_from_point(x: int, y: int) -> str:
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.WindowFromPoint(wintypes.POINT(int(x), int(y)))
        while hwnd:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = (buf.value or "").strip()
                if title:
                    return title[:100]
            parent = user32.GetParent(hwnd)
            if not parent:
                # try owner / root
                root = user32.GetAncestor(hwnd, 2)  # GA_ROOT
                if root and root != hwnd:
                    length = user32.GetWindowTextLengthW(root)
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(root, buf, length + 1)
                    return (buf.value or "").strip()[:100]
                break
            hwnd = parent
    except Exception:
        pass
    return ""


def _hwnd_from_tk(widget) -> int:
    try:
        return int(widget.winfo_id())
    except Exception:
        return 0


def _is_under_hwnd(x: int, y: int, root_hwnd: int) -> bool:
    if not root_hwnd:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.WindowFromPoint(wintypes.POINT(int(x), int(y)))
        while hwnd:
            if int(hwnd) == int(root_hwnd):
                return True
            # Tk embeds; also check ancestor chain
            parent = user32.GetParent(hwnd)
            if not parent:
                anc = user32.GetAncestor(hwnd, 2)
                return int(anc) == int(root_hwnd)
            hwnd = parent
    except Exception:
        return False
    return False


def events_to_desktop_steps(events: list[dict[str, Any]]) -> list[TestStep]:
    steps: list[TestStep] = []
    last_focus = ""

    for ev in events:
        et = ev.get("type")
        if et == "focus_window":
            title = str(ev.get("title") or "").strip()
            if not title or title == last_focus:
                continue
            last_focus = title
            steps.append(
                TestStep(
                    id=new_id("stp_"),
                    type="desktop.focus_window",
                    name=f"Focus {title[:40]}",
                    config={"title": title, "timeout_ms": 15000},
                )
            )
        elif et == "click":
            title = str(ev.get("window_title") or "").strip()
            if title and title != last_focus:
                last_focus = title
                steps.append(
                    TestStep(
                        id=new_id("stp_"),
                        type="desktop.focus_window",
                        name=f"Focus {title[:40]}",
                        config={"title": title, "timeout_ms": 15000},
                    )
                )
            name = str(ev.get("name") or "").strip()
            auto_id = str(ev.get("auto_id") or "").strip()
            ctype = str(ev.get("control_type") or "").strip()
            if not name and not auto_id:
                continue
            label = name or auto_id
            steps.append(
                TestStep(
                    id=new_id("stp_"),
                    type="desktop.click",
                    name=f"Click {label[:40]}",
                    config={
                        "window_title": title,
                        "name": name,
                        "auto_id": auto_id,
                        "control_type": ctype if ctype in (
                            "Button", "Edit", "MenuItem", "TabItem", "ListItem",
                            "CheckBox", "ComboBox", "Text", "",
                        ) else "",
                        "timeout_ms": 15000,
                    },
                )
            )
        elif et == "type":
            text = str(ev.get("text") or "")
            if not text:
                continue
            title = str(ev.get("window_title") or "").strip()
            if title and title != last_focus:
                last_focus = title
                steps.append(
                    TestStep(
                        id=new_id("stp_"),
                        type="desktop.focus_window",
                        name=f"Focus {title[:40]}",
                        config={"title": title, "timeout_ms": 15000},
                    )
                )
            steps.append(
                TestStep(
                    id=new_id("stp_"),
                    type="desktop.type_text",
                    name=f"Type {text[:28]!r}",
                    config={
                        "text": text,
                        "window_title": title,
                        "name": str(ev.get("name") or ""),
                        "auto_id": str(ev.get("auto_id") or ""),
                        "control_type": str(ev.get("control_type") or "Edit"),
                        "clear": False,
                        "timeout_ms": 15000,
                    },
                )
            )
        elif et == "send_keys":
            keys = str(ev.get("keys") or "").strip()
            if not keys:
                continue
            title = str(ev.get("window_title") or "").strip()
            steps.append(
                TestStep(
                    id=new_id("stp_"),
                    type="desktop.send_keys",
                    name=f"Keys {keys[:24]}",
                    config={"keys": keys, "window_title": title},
                )
            )
        elif et == "assert_window":
            title = str(ev.get("title") or "").strip()
            if not title:
                continue
            steps.append(
                TestStep(
                    id=new_id("stp_"),
                    type="assert.desktop_window",
                    name=f"Assert window {title[:40]}",
                    config={"title": title, "timeout_ms": 10000},
                )
            )
        elif et == "wait":
            steps.append(
                TestStep(
                    id=new_id("stp_"),
                    type="desktop.wait",
                    name="Desktop wait",
                    config={"ms": int(ev.get("ms") or 1000)},
                )
            )
    return steps


def record_desktop_session(
    window_title: str = "",
    launch: str = "",
    max_seconds: int = 600,
) -> dict[str, Any]:
    """
    Interactive desktop recorder with floating control panel.
    Blocks until Finish / Cancel / timeout.
    """
    _ensure_env()
    if not sys.platform.startswith("win"):
        raise RuntimeError("Desktop recorder supports Windows only")

    import tkinter as tk
    from pynput import keyboard, mouse

    events: list[dict[str, Any]] = []
    events_lock = threading.Lock()
    done = threading.Event()
    cancelled = threading.Event()
    type_buf: list[str] = []
    type_meta: dict[str, str] = {}
    last_type_ts = [0.0]
    recorder_hwnd = [0]
    filter_title = (window_title or "").strip().lower()
    started = time.time()

    def _matches_filter(title: str) -> bool:
        if not filter_title:
            return True
        return filter_title in (title or "").lower()

    def _flush_type() -> None:
        text = "".join(type_buf)
        type_buf.clear()
        if not text:
            return
        payload = {
            "type": "type",
            "text": text,
            "window_title": type_meta.get("window_title", ""),
            "name": type_meta.get("name", ""),
            "auto_id": type_meta.get("auto_id", ""),
            "control_type": type_meta.get("control_type", "Edit"),
            "ts": int(time.time() * 1000),
        }
        if _matches_filter(payload["window_title"]):
            with events_lock:
                events.append(payload)

    def _add(ev: dict[str, Any]) -> None:
        with events_lock:
            events.append(ev)

    def _current_foreground_title() -> str:
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return (buf.value or "").strip()[:100]
        except Exception:
            return ""

    def on_click(x, y, button, pressed):
        if done.is_set():
            return False
        if pressed:  # record on release for final target
            return
        try:
            if button != mouse.Button.left:
                return
        except Exception:
            return
        if _is_under_hwnd(x, y, recorder_hwnd[0]):
            return
        _flush_type()
        # Slight delay so focus settles
        time.sleep(0.05)
        info = _point_element(int(x), int(y))
        title = info.get("window_title") or _current_foreground_title()
        if not _matches_filter(title):
            return
        # Skip empty chrome
        if not info.get("name") and not info.get("auto_id"):
            # still useful to record focus if new window
            if title:
                _add({"type": "focus_window", "title": title, "ts": int(time.time() * 1000)})
            return
        type_meta.update(
            {
                "window_title": title,
                "name": info.get("name") or "",
                "auto_id": info.get("auto_id") or "",
                "control_type": info.get("control_type") or "",
            }
        )
        _add(
            {
                "type": "click",
                "x": int(x),
                "y": int(y),
                "name": info.get("name") or "",
                "auto_id": info.get("auto_id") or "",
                "control_type": info.get("control_type") or "",
                "window_title": title,
                "ts": int(time.time() * 1000),
            }
        )

    def on_press(key):
        if done.is_set():
            return False
        # Ignore input when recorder panel focused
        fg = _current_foreground_title()
        if fg.startswith("FlowTest Desktop Recorder"):
            return
        try:
            from pynput.keyboard import Key

            if key == Key.f9:
                _flush_type()
                done.set()
                return False
            if key == Key.f8:
                title = _current_foreground_title()
                if title and not title.startswith("FlowTest Desktop Recorder"):
                    _add({"type": "assert_window", "title": title, "ts": int(time.time() * 1000)})
                return
            if key == Key.enter:
                _flush_type()
                if _matches_filter(fg):
                    _add({"type": "send_keys", "keys": "{ENTER}", "window_title": fg, "ts": int(time.time() * 1000)})
                return
            if key == Key.tab:
                _flush_type()
                if _matches_filter(fg):
                    _add({"type": "send_keys", "keys": "{TAB}", "window_title": fg, "ts": int(time.time() * 1000)})
                return
            if key == Key.backspace:
                if type_buf:
                    type_buf.pop()
                    last_type_ts[0] = time.time()
                return
            if key in (Key.shift, Key.shift_r, Key.ctrl, Key.ctrl_l, Key.ctrl_r, Key.alt, Key.alt_l, Key.alt_r, Key.cmd):
                return
        except Exception:
            pass

        ch = None
        try:
            ch = key.char
        except AttributeError:
            ch = None
        if ch and ch.isprintable():
            if not type_buf:
                type_meta["window_title"] = fg
            type_buf.append(ch)
            last_type_ts[0] = time.time()

    def idle_flusher():
        while not done.is_set():
            time.sleep(0.4)
            if type_buf and (time.time() - last_type_ts[0]) > 1.1:
                _flush_type()
            if time.time() - started > max_seconds:
                done.set()
                break

    # Optional launch
    if (launch or "").strip():
        import subprocess

        try:
            subprocess.Popen(launch.strip(), shell=True)
            time.sleep(1.0)
            _add({"type": "wait", "ms": 1500, "ts": int(time.time() * 1000)})
        except Exception as exc:
            raise RuntimeError(f"Could not launch {launch!r}: {exc}") from exc

    # Control panel
    root = tk.Tk()
    root.title("FlowTest Desktop Recorder")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    root.configure(bg="#241e1b")
    try:
        root.attributes("-toolwindow", True)
    except Exception:
        pass

    frame = tk.Frame(root, bg="#241e1b", padx=16, pady=14)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="DESKTOP RECORDING",
        fg="#ff9db3",
        bg="#241e1b",
        font=("Segoe UI", 10, "bold"),
    ).pack(anchor="w")

    help_lbl = tk.Label(
        frame,
        text="Use your apps normally — clicks & typing are captured.\n"
        "F8 = assert current window · F9 or Finish = stop",
        fg="#fffcfb",
        bg="#241e1b",
        justify="left",
        font=("Segoe UI", 10),
    )
    help_lbl.pack(anchor="w", pady=(4, 10))

    status_var = tk.StringVar(value="Events: 0")
    status_lbl = tk.Label(
        frame, textvariable=status_var, fg="#ffc6d3", bg="#241e1b", font=("Segoe UI", 11, "bold")
    )
    status_lbl.pack(anchor="w", pady=(0, 10))

    btn_row = tk.Frame(frame, bg="#241e1b")
    btn_row.pack(fill="x")

    def finish():
        _flush_type()
        done.set()

    def cancel():
        cancelled.set()
        done.set()

    def assert_win():
        title = _current_foreground_title()
        if title and not title.startswith("FlowTest Desktop Recorder"):
            _add({"type": "assert_window", "title": title, "ts": int(time.time() * 1000)})

    tk.Button(
        btn_row,
        text="Assert window",
        command=assert_win,
        bg="#ffc6d3",
        fg="#241e1b",
        font=("Segoe UI", 10, "bold"),
        relief="flat",
        padx=10,
        pady=6,
    ).pack(side="left", padx=(0, 8))

    tk.Button(
        btn_row,
        text="Finish recording",
        command=finish,
        bg="#f83b66",
        fg="#ffffff",
        font=("Segoe UI", 10, "bold"),
        relief="flat",
        padx=12,
        pady=6,
    ).pack(side="left", padx=(0, 8))

    tk.Button(
        btn_row,
        text="Cancel",
        command=cancel,
        bg="#4a403c",
        fg="#fffcfb",
        font=("Segoe UI", 10),
        relief="flat",
        padx=10,
        pady=6,
    ).pack(side="left")

    root.update_idletasks()
    # Position top-right
    try:
        sw = root.winfo_screenwidth()
        root.geometry(f"+{max(20, sw - 420)}+20")
    except Exception:
        pass

    root.update()
    recorder_hwnd[0] = _hwnd_from_tk(root)
    # Also try Win32 handle via wm_frame
    try:
        import ctypes

        recorder_hwnd[0] = int(root.wm_frame(), 16) if isinstance(root.wm_frame(), str) else int(root.winfo_id())
    except Exception:
        recorder_hwnd[0] = _hwnd_from_tk(root)

    mouse_listener = mouse.Listener(on_click=on_click)
    key_listener = keyboard.Listener(on_press=on_press)
    mouse_listener.daemon = True
    key_listener.daemon = True
    mouse_listener.start()
    key_listener.start()
    threading.Thread(target=idle_flusher, daemon=True).start()

    def poll_ui():
        with events_lock:
            n = len(events)
        status_var.set(f"Events: {n}   ·   elapsed {int(time.time() - started)}s")
        if done.is_set():
            try:
                root.quit()
            except Exception:
                pass
            return
        root.after(300, poll_ui)

    root.after(300, poll_ui)
    root.protocol("WM_DELETE_WINDOW", finish)
    root.mainloop()

    try:
        mouse_listener.stop()
        key_listener.stop()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass

    _flush_type()
    if cancelled.is_set():
        return {
            "events": [],
            "steps": [],
            "count": 0,
            "cancelled": True,
            "window_title": window_title,
            "launch": launch,
        }

    with events_lock:
        snap = list(events)
    steps = events_to_desktop_steps(snap)
    return {
        "events": snap,
        "steps": [s.to_dict() for s in steps],
        "count": len(steps),
        "cancelled": False,
        "window_title": window_title,
        "launch": launch,
    }


def record_desktop_session_safe(
    window_title: str = "",
    launch: str = "",
    max_seconds: int = 600,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Run desktop recorder in a fresh subprocess (Streamlit/Windows safe)."""
    import json
    import os
    import subprocess
    import tempfile
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    wait = timeout if timeout is not None else max_seconds + 120
    payload = {
        "window_title": window_title,
        "launch": launch,
        "max_seconds": max_seconds,
    }

    with tempfile.TemporaryDirectory(prefix="flowtest_deskrec_") as tmp:
        tmp_path = Path(tmp)
        in_path = tmp_path / "in.json"
        out_path = tmp_path / "out.json"
        in_path.write_text(json.dumps(payload), encoding="utf-8")

        env = dict(os.environ)
        py_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(root) + ((";" + py_path) if py_path else "")

        proc = subprocess.run(
            [sys.executable, "-m", "flowtest.desktop_recorder_job", str(in_path), str(out_path)],
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
                    or (proc.stderr or proc.stdout or "Desktop recorder process failed")
                )
            if proc.returncode != 0 and not result.get("steps") and not result.get("cancelled"):
                raise RuntimeError(
                    result.get("error")
                    or (proc.stderr or proc.stdout or f"Desktop recorder exited {proc.returncode}")
                )
            return result

        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(err or f"Desktop recorder exited with code {proc.returncode}")


def steps_from_desktop_recording(result: dict[str, Any]) -> list[TestStep]:
    return [TestStep(**s) for s in result.get("steps", [])]
