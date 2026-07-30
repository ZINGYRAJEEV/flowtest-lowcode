"""
Subprocess probe/install for Playwright Chromium.
Never call sync_playwright inside the Streamlit process (Windows asyncio breaks).
"""

from __future__ import annotations

import sys


def main() -> int:
    from flowtest.browser_setup import browsers_path, launch_chromium

    browsers_path()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = launch_chromium(p, headless=True)
        page = browser.new_page()
        page.set_content("<html><body>ok</body></html>")
        browser.close()
    print("OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
