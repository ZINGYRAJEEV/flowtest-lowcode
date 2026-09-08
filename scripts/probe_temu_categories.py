"""Find how Categories is exposed in the Temu DOM."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from flowtest.browser_setup import ensure_playwright_chromium, launch_chromium

JS = r"""
(() => {
  const accept = () => {
    for (const el of document.querySelectorAll('button,[role="button"],a')) {
      const t = (el.innerText||el.getAttribute('aria-label')||'').replace(/\s+/g,' ').trim().toLowerCase();
      if (t === 'accept all' || t.includes('accept all')) { el.click(); return t; }
    }
    return 'none';
  };
  const acc = accept();
  const matches = [];
  const all = document.querySelectorAll('a,button,[role="button"],[role="link"],div,span');
  for (const el of all) {
    const t = (el.innerText||el.getAttribute('aria-label')||'').replace(/\s+/g,' ').trim();
    if (!t) continue;
    if (!/^categories$/i.test(t) && !/^categories\b/i.test(t.slice(0,20))) continue;
    const r = el.getBoundingClientRect();
    matches.push({
      tag: el.tagName,
      role: el.getAttribute('role')||'',
      t: t.slice(0,80),
      id: el.id||'',
      cls: (el.className||'').toString().slice(0,60),
      w: Math.round(r.width), h: Math.round(r.height),
      top: Math.round(r.top),
    });
    if (matches.length > 20) break;
  }
  return { acc, matches };
})()
"""


def main() -> None:
    ensure_playwright_chromium()
    with sync_playwright() as p:
        browser = launch_chromium(p, headless=False)
        page = browser.new_page()
        page.goto("https://www.temu.com/", wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(4000)
        print(page.evaluate(JS))
        # try playwright get_by_text
        try:
            loc = page.get_by_text("Categories", exact=False).first
            print("count", page.get_by_text("Categories", exact=False).count())
            print("visible", loc.is_visible())
            loc.click(timeout=5000)
            print("clicked ok")
            page.wait_for_timeout(1500)
        except Exception as exc:
            print("playwright click failed", exc)
        browser.close()


if __name__ == "__main__":
    main()
