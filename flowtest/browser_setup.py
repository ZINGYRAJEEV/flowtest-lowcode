"""
Ensure Playwright Chromium is installed and can launch (Streamlit Cloud friendly).
"""

from __future__ import annotations

import os
import subprocess
import sys
from functools import lru_cache
from typing import Any


def is_streamlit_cloud() -> bool:
    """Detect Streamlit Community Cloud (no headed browser / GUI)."""
    home = os.path.expanduser("~").replace("\\", "/")
    user = (os.environ.get("USER") or os.environ.get("USERNAME") or "").lower()
    return (
        home.rstrip("/") == "/home/appuser"
        or user == "appuser"
        or os.environ.get("STREAMLIT_RUNTIME_ENVIRONMENT", "").lower() == "cloud"
        or "streamlit.app" in (os.environ.get("STREAMLIT_SERVER_BASE_URL") or "").lower()
    )


def can_record_headed() -> bool:
    """
    Recording needs a real headed Chromium window the user can see/control.
    That is not available on Streamlit Cloud or headless Linux servers.
    """
    if is_streamlit_cloud():
        return False
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        return False
    return True


def browsers_path() -> str:
    """Writable cache dir for Playwright browsers (Cloud-safe)."""
    configured = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if configured and configured != "0":
        return configured
    path = os.path.join(os.path.expanduser("~"), ".cache", "ms-playwright")
    os.makedirs(path, exist_ok=True)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = path
    return path


def chromium_launch_args(headed: bool = False) -> list[str]:
    """Args required for Chromium in restricted Linux / Streamlit Cloud sandboxes."""
    args = [
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--font-render-hinting=none",
    ]
    if is_streamlit_cloud() or (sys.platform.startswith("linux") and not headed):
        args.extend(
            [
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )
    if headed:
        args.append("--start-maximized")
    return args


def launch_chromium(playwright_instance, headless: bool = True):
    """Launch Chromium with Cloud-safe defaults."""
    browsers_path()
    return playwright_instance.chromium.launch(
        headless=headless,
        args=chromium_launch_args(headed=not headless),
    )


def _probe_chromium() -> tuple[bool, str]:
    """Try launching Chromium; return (ok, detail)."""
    browsers_path()
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = launch_chromium(p, headless=True)
            page = browser.new_page()
            page.set_content("<html><body>ok</body></html>")
            browser.close()
        return True, "ok"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _run_playwright_install() -> str:
    browsers_path()
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path()
    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=900,
        env=env,
    )
    out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise RuntimeError(out[-800:] or f"playwright install exit {proc.returncode}")
    return out[-400:] or "installed"


@lru_cache(maxsize=1)
def ensure_playwright_chromium() -> str:
    """
    Install Playwright Chromium if needed and verify it launches.
    Raises RuntimeError with the underlying Playwright error when it cannot run.
    """
    ok, detail = _probe_chromium()
    if ok:
        return "ready"

    try:
        _run_playwright_install()
    except Exception as exc:
        raise RuntimeError(
            "Playwright Chromium download failed. "
            f"Browsers path: {browsers_path()}. Detail: {exc}"
        ) from exc

    ok2, detail2 = _probe_chromium()
    if ok2:
        return "installed"

    # Clear cached failure if we ever change to soft-fail later
    raise RuntimeError(
        "Chromium installed but still cannot launch (common on Streamlit Cloud without "
        "sandbox flags / system libs).\n"
        f"Probe error: {detail2}\n"
        f"Earlier probe: {detail}\n"
        f"Browsers path: {browsers_path()}\n"
        "Confirm packages.txt is in the repo root, then Reboot the app. "
        "If apt install failed in Cloud logs, share those lines."
    )


def chromium_status() -> dict[str, Any]:
    """Non-raising status for UI diagnostics."""
    ok, detail = _probe_chromium()
    return {
        "ok": ok,
        "detail": detail,
        "cloud": is_streamlit_cloud(),
        "browsers_path": browsers_path(),
        "can_record": can_record_headed(),
    }
