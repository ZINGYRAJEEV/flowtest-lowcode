"""
Windows clipboard helpers for hybrid web → desktop flows.
"""

from __future__ import annotations

import sys
import time


def set_clipboard_text(text: str) -> None:
    data = "" if text is None else str(text)
    if sys.platform.startswith("win"):
        _set_clipboard_win(data)
        return
    try:
        import tkinter as tk

        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(data)
        r.update()
        r.destroy()
    except Exception as exc:
        raise RuntimeError(f"Could not set clipboard: {exc}") from exc


def get_clipboard_text() -> str:
    if sys.platform.startswith("win"):
        return _get_clipboard_win()
    try:
        import tkinter as tk

        r = tk.Tk()
        r.withdraw()
        try:
            return r.clipboard_get()
        finally:
            r.destroy()
    except Exception:
        return ""


def _set_clipboard_win(text: str) -> None:
    last_err: Exception | None = None
    # Prefer pywin32 when available
    try:
        import win32clipboard
        import win32con

        for _ in range(10):
            try:
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                    return
                finally:
                    win32clipboard.CloseClipboard()
            except Exception as exc:
                last_err = exc
                time.sleep(0.05)
        raise RuntimeError(f"SetClipboard failed: {last_err}")
    except ImportError:
        pass

    # Fallback: PowerShell (always available on Windows)
    import subprocess
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as fh:
        fh.write(text)
        tmp = Path(fh.name)
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-Content -Raw -Encoding UTF8 '{tmp}' | Set-Clipboard",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        raise RuntimeError(f"Could not set clipboard: {exc}") from exc
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _get_clipboard_win() -> str:
    try:
        import win32clipboard
        import win32con

        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                return "" if data is None else str(data)
            return ""
        finally:
            win32clipboard.CloseClipboard()
    except ImportError:
        pass
    except Exception:
        return ""

    import subprocess

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout or ""
    except Exception:
        return ""
