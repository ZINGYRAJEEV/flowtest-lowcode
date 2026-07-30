"""
Ensure Playwright Chromium is installed (needed on Streamlit Cloud / fresh hosts).
"""

from __future__ import annotations

import os
import subprocess
import sys
from functools import lru_cache


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


def _chromium_launches() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        return False


@lru_cache(maxsize=1)
def ensure_playwright_chromium() -> str:
    """
    Install Playwright Chromium if missing. Safe to call repeatedly.
    Returns a short status string.
    """
    if _chromium_launches():
        return "ready"
    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or exc.stdout or str(exc))[-500:]
        raise RuntimeError(
            "Playwright Chromium install failed. "
            "On Streamlit Cloud, ensure packages.txt is deployed, then reboot the app. "
            f"Detail: {err}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Playwright Chromium install failed: {exc}") from exc

    if not _chromium_launches():
        raise RuntimeError(
            "Chromium still missing after install. "
            "Reboot the Streamlit app and confirm packages.txt is in the repo root."
        )
    return "installed"
