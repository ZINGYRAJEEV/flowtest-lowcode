"""Probe Temu homepage section labels after Accept All."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from flowtest.browser_setup import ensure_playwright_chromium, launch_chromium

ACCEPT_JS = r"""
(() => {
  const labelOf = (el) => (el.innerText || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const nodes = Array.from(document.querySelectorAll('button, [role="button"], a'));
  for (const el of nodes) {
    const t = labelOf(el);
    if (t === 'accept all' || t.includes('accept all')) { el.click(); return t; }
  }
  return 'none';
})()
"""

PROBE = r"""
(() => {
  const text = (document.body && document.body.innerText) || '';
  const clean = text.replace(/[\u200b\s]+/g, ' ').trim();
  const needles = [
    'Lightning deals', 'lightning', 'Limited-time', 'deals', 'aanbied', 'deal',
    'Categories', 'Categorie', 'Why choose Temu', 'Secure privacy',
    'Sign in', 'Inloggen', 'Explore', 'Shop'
  ];
  const found = {};
  for (const n of needles) found[n] = clean.toLowerCase().includes(n.toLowerCase());
  // headings
  const heads = Array.from(document.querySelectorAll('h1,h2,h3,[role="heading"]'))
    .map(el => (el.innerText || '').replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .slice(0, 25);
  return {
    title: document.title,
    len: clean.length,
    sample: clean.slice(0, 500),
    found,
    heads,
  };
})()
"""


def main() -> None:
    ensure_playwright_chromium()
    with sync_playwright() as p:
        browser = launch_chromium(p, headless=False)
        page = browser.new_page()
        page.goto("https://www.temu.com/", wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(3500)
        print("accept:", page.evaluate(ACCEPT_JS))
        page.wait_for_timeout(2000)
        page.evaluate("window.scrollBy(0, 1200)")
        page.wait_for_timeout(1500)
        print(page.evaluate(PROBE))
        page.screenshot(path="monkey_artifacts/temu_after_accept.png")
        browser.close()


if __name__ == "__main__":
    main()
