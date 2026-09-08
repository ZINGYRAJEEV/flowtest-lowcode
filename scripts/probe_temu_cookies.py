"""Quick probe of Temu cookie UI labels."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

from flowtest.browser_setup import ensure_playwright_chromium, launch_chromium

PROBE_JS = r"""
() => {
  const nodes = Array.from(document.querySelectorAll('button, [role="button"], a, input[type="button"]'));
  const btns = [];
  for (const el of nodes) {
    const t = (el.innerText || el.value || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
    if (!t) continue;
    if (!/cookie|accept|consent|privacy|customise|customize|agree|allow|reject|decline/i.test(t)) continue;
    const style = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    const vis = style.display !== 'none' && style.visibility !== 'hidden' && r.width > 2 && r.height > 2;
    btns.push({ t: t.slice(0, 100), id: el.id || '', vis });
  }
  return {
    title: document.title,
    url: location.href,
    btns: btns.slice(0, 40),
    hasTemu: /temu/i.test(document.body.innerText || ''),
  };
}
"""


def main() -> None:
    ensure_playwright_chromium()
    out = Path("monkey_artifacts")
    out.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = launch_chromium(p, headless=False)
        page = browser.new_page()
        page.goto("https://www.temu.com/", wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(4500)
        info = page.evaluate(PROBE_JS)
        print(info)
        page.screenshot(path=str(out / "temu_cookie_probe.png"))
        browser.close()


if __name__ == "__main__":
    main()
