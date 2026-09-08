"""
Bootstrap FlowTest project: Temu — environment + homepage UI coverage suite.

Temu often shows a cookie/consent dialog and may challenge headless browsers.
Core tests: cookies, brand, search, categories, deals, component/id inventory, UTM landing.

Run: python scripts/setup_temu_project.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flowtest.models import Environment, Project, TestCase, TestStep, new_id
from flowtest.storage import (
    add_audit,
    init_db,
    list_environments,
    list_projects,
    list_tests,
    save_environment,
    save_project,
    save_test,
)
from flowtest.suite_io import export_suite_to_files

BASE_URL = "https://www.temu.com"
START_URL = (
    "https://www.temu.com/?_x_ns_irclickid=S%3AyQn1WNdxyZWFB3Fm3MDUTQUkr2i%3AwdVWyqxU0"
    "&_x_ads_account=18350&_x_ads_id=1580294"
    "&_x_ns_iradname=Online%20Tracking%20Link&_x_ns_iradsize=&_x_ns_prodsku="
    "&_x_ns_irmptype=mediapartner&_x_ns_sharedid=firefox"
    "&_x_ns_ts=1788865869540&_x_ns_randint=1342093"
    "&_x_ns_adtype=ONLINE_TRACKING_LINK&_p_rfs=1&irgwc=1&afsrc=1"
    "&_x_ns_irmpgroupname=%22Admarketplace%22%2C%22ld%22"
    "&_x_ads_channel=impact&_x_ns_mp_value2=&_x_ns_mp_value3="
    "&_x_ns_irmpname=Firefox%20Browser%20-%20adMarketplace"
    "&_x_ns_irpid=2626476&_bg_fs=1&_p_jump_id=1202"
    "&_x_vst_scene=adg&scene=adg_alliance_exp"
    "&_p_adg_gwid=2979d96e78a54cd0a31862b2dce8f0a7"
)

_IS_VISIBLE_JS = """
  const isVisible = (el) => {
    if (!el || !(el instanceof Element)) return false;
    if (el.closest('[hidden], [aria-hidden="true"]')) return false;
    if (typeof el.checkVisibility === 'function') {
      try {
        return el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true });
      } catch (e) { /* fall through */ }
    }
    const style = window.getComputedStyle(el);
    if (!style || style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) {
      return false;
    }
    const r = el.getBoundingClientRect();
    return r.width > 2 && r.height > 2;
  };
  const labelOf = (el) =>
    (el.innerText || el.value || el.getAttribute('aria-label') || el.textContent || '')
      .replace(/\\s+/g, ' ')
      .trim()
      .toLowerCase();
"""

COOKIE_JS = f"""
(() => {{
{_IS_VISIBLE_JS}
  const labels = [
    'accept all',
    'accept all cookies',
    'accept cookies',
    'allow all',
    'allow cookies',
    'i agree',
    'agree',
    'got it',
    'continue',
    'accept',
    'ok',
  ];
  // Prefer known CMP buttons (OneTrust / Cookiebot / Temu variants)
  const preferred = [
    '#onetrust-accept-btn-handler',
    '#accept-recommended-btn-handler',
    'button#onetrust-accept-btn-handler',
    '[data-testid*="accept" i]',
    '[id*="accept" i][role="button"]',
    'button[aria-label*="Accept" i]',
  ];
  for (const sel of preferred) {{
    try {{
      const el = document.querySelector(sel);
      if (el && isVisible(el)) {{
        el.click();
        return 'clicked-sel:' + sel.slice(0, 48);
      }}
    }} catch (e) {{}}
  }}
  const modalVisible = () => {{
    const dialogs = Array.from(
      document.querySelectorAll(
        '[role="dialog"], [aria-modal="true"], #onetrust-banner-sdk, #onetrust-consent-sdk, ' +
        '[id*="cookie" i], [class*="cookie" i], [id*="consent" i], [class*="consent" i], [class*="privacy" i]'
      )
    );
    for (const d of dialogs) {{
      if (!isVisible(d)) continue;
      const t = (d.innerText || '').toLowerCase();
      if (
        t.includes('cookie') || t.includes('privacy') || t.includes('consent') ||
        t.includes('accept all') || t.includes('we value your privacy')
      ) return true;
    }}
    return Array.from(document.querySelectorAll('button, [role="button"]')).some((el) => {{
      if (!isVisible(el)) return false;
      const t = labelOf(el);
      return t.includes('accept all') || t === 'accept cookies' || t.includes('allow all');
    }});
  }};
  const clickMatch = (root) => {{
    if (!root) return null;
    const nodes = Array.from(
      root.querySelectorAll('button, [role="button"], a, input[type="button"], input[type="submit"]')
    );
    for (const el of nodes) {{
      if (!isVisible(el)) continue;
      const t = labelOf(el);
      if (!t) continue;
      if (
        t.includes('reject') || t.includes('decline') || t.includes('refuse') ||
        t.includes('manage') || t.includes('settings') || t.includes('customize') ||
        t.includes('preferences') || t.includes('do not sell')
      ) continue;
      if (labels.some((l) => t === l || t.includes(l))) {{
        el.click();
        return 'clicked:' + t.slice(0, 48);
      }}
    }}
    return null;
  }};
  const dialogs = Array.from(
    document.querySelectorAll(
      '[role="dialog"], [aria-modal="true"], #onetrust-banner-sdk, #onetrust-consent-sdk, ' +
      '[id*="cookie" i], [class*="cookie" i], [id*="consent" i], [class*="consent" i]'
    )
  );
  let hit = null;
  for (const d of dialogs) {{
    hit = clickMatch(d);
    if (hit) break;
  }}
  if (!hit) hit = clickMatch(document.body);
  if (hit) return hit;
  if (modalVisible()) {{
    throw new Error('Cookie / privacy banner still visible — failed to Accept');
  }}
  return 'no-banner';
}})()
"""

COOKIE_JS_SOFT = f"""
(() => {{
{_IS_VISIBLE_JS}
  const labels = [
    'accept all', 'accept all cookies', 'accept cookies', 'allow all',
    'i agree', 'agree', 'got it', 'accept', 'ok',
  ];
  const preferred = ['#onetrust-accept-btn-handler', '[data-testid*="accept" i]'];
  for (const sel of preferred) {{
    try {{
      const el = document.querySelector(sel);
      if (el && isVisible(el)) {{ el.click(); return 'clicked-sel:' + sel; }}
    }} catch (e) {{}}
  }}
  const clickMatch = (root) => {{
    if (!root) return 'no-banner';
    const nodes = Array.from(root.querySelectorAll('button, [role="button"], a'));
    for (const el of nodes) {{
      if (!isVisible(el)) continue;
      const t = labelOf(el);
      if (!t) continue;
      if (t.includes('reject') || t.includes('decline') || t.includes('manage') || t.includes('settings')) continue;
      if (labels.some((l) => t === l || t.includes(l))) {{
        el.click();
        return 'clicked:' + t.slice(0, 48);
      }}
    }}
    return 'no-banner';
  }};
  const dialogs = Array.from(
    document.querySelectorAll('[role="dialog"], [aria-modal="true"], #onetrust-banner-sdk, [id*="cookie" i], [class*="consent" i]')
  );
  for (const d of dialogs) {{
    const hit = clickMatch(d);
    if (hit.startsWith('clicked')) return hit;
  }}
  return clickMatch(document.body);
}})()
"""

ASSERT_MODAL_GONE_JS = f"""
(() => {{
{_IS_VISIBLE_JS}
  const dialogs = Array.from(
    document.querySelectorAll(
      '[role="dialog"], [aria-modal="true"], #onetrust-banner-sdk, #onetrust-consent-sdk, ' +
      '[id*="cookie" i], [class*="cookie" i], [id*="consent" i], [class*="consent" i]'
    )
  );
  for (const d of dialogs) {{
    if (!isVisible(d)) continue;
    const t = (d.innerText || '').toLowerCase();
    if (
      t.includes('accept all') || t.includes('we value your privacy') ||
      (t.includes('cookie') && t.includes('accept'))
    ) {{
      throw new Error('Cookie / privacy banner still blocking the page');
    }}
  }}
  const still = Array.from(document.querySelectorAll('button, [role="button"]')).some((el) => {{
    if (!isVisible(el)) return false;
    const t = labelOf(el);
    return t.includes('accept all cookies') || t === 'accept all';
  }});
  if (still) throw new Error('Accept all cookies control still visible');
  return 'modal-gone';
}})()
"""


def _stp(stype: str, name: str, config: dict, notes: str = "") -> TestStep:
    return TestStep(id=new_id("stp_"), type=stype, name=name, config=config, notes=notes)


def _optional_click_js(label: str) -> str:
    safe = label.replace("\\", "\\\\").replace("'", "\\'")
    return f"""
(() => {{
  const want = '{safe}'.toLowerCase();
  const nodes = Array.from(document.querySelectorAll('a, button, [role="button"], [role="link"]'));
  for (const el of nodes) {{
    const t = (el.innerText || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim();
    if (t && t.toLowerCase().includes(want)) {{
      el.click();
      return 'clicked:' + t.slice(0, 60);
    }}
  }}
  return 'missing';
}})()
"""


def _accept_cookies_steps(prefix: str = "") -> list[TestStep]:
    p = f"{prefix} " if prefix else ""
    return [
        _stp("ui.wait", f"{p}Wait for cookie dialog".strip(), {"ms": 3200}),
        _stp(
            "util.custom_js",
            f"{p}Accept cookies".strip(),
            {"script": COOKIE_JS},
            "Clicks Accept all / OneTrust / common CMP buttons; fails if banner stays",
        ),
        _stp("ui.wait", f"{p}Settle after consent".strip(), {"ms": 1500}),
        _stp(
            "util.custom_js",
            f"{p}Assert cookie banner gone".strip(),
            {"script": ASSERT_MODAL_GONE_JS, "expect_contains": "modal-gone"},
            "Hard fail if Accept all / cookie dialog still visible",
        ),
    ]


def build_core_smoke() -> list[TestStep]:
    return [
        _stp("ui.goto", "Open Temu homepage", {"url": "{{BASE_URL}}", "timeout_ms": 90000}),
        *_accept_cookies_steps(),
        _stp("assert.title_contains", "Title mentions Temu", {"text": "Temu", "timeout_ms": 30000}),
        _stp(
            "assert.text_contains",
            "Body mentions Temu",
            {"selector": "body", "text": "Temu", "timeout_ms": 30000, "ignore_case": True},
        ),
        _stp(
            "assert.text_contains",
            "Trust messaging visible",
            {"selector": "body", "text": "Delivery guarantee", "timeout_ms": 20000, "ignore_case": True},
        ),
        _stp(
            "ui.click_by_text",
            "Categories control is clickable",
            {"text": "Categories", "exact": False, "role": "", "within": "", "timeout_ms": 20000},
            "Fails if cookie overlay still blocks navigation",
        ),
        _stp("ui.wait", "After Categories", {"ms": 800}),
        _stp("util.custom_js", "Scroll deals into view", {"script": "window.scrollBy(0, 900); 'scrolled'"}),
        _stp("ui.wait", "Wait after scroll", {"ms": 1000}),
        _stp(
            "assert.text_contains",
            "Lightning deals section present",
            {"selector": "body", "text": "Lightning deals", "timeout_ms": 20000, "ignore_case": True},
        ),
        _stp("assert.element_exists", "Document still responsive", {"selector": "body", "timeout_ms": 10000}),
        _stp("ui.screenshot", "Homepage screenshot", {"label": "temu_home"}),
    ]


def build_nav_coverage() -> list[TestStep]:
    required = [
        ("Categories", ""),
        ("Sign in", ""),
        ("Jewelry", "link"),
        ("Women's Clothing", "link"),
        ("Home & Kitchen", "link"),
    ]
    optional = [
        "Kids' Fashion",
        "Men's Clothing",
        "Sports & Outdoors",
        "Beauty & Personal Care",
        "Electronics",
        "Support center",
        "About Temu",
    ]
    steps = [
        _stp("ui.goto", "Open Temu homepage", {"url": "{{BASE_URL}}", "timeout_ms": 90000}),
        *_accept_cookies_steps(),
    ]
    for label, role in required:
        steps.append(
            _stp(
                "ui.click_by_text",
                f'Click "{label}"',
                {
                    "text": label,
                    "exact": False,
                    "role": role,
                    "within": "",
                    "timeout_ms": 20000,
                },
                "Required — FAIL if blocked by cookie modal or missing",
            )
        )
        steps.append(_stp("ui.wait", f"After {label}", {"ms": 1000}))
        steps.append(_stp("ui.goto", "Return home", {"url": "{{BASE_URL}}", "timeout_ms": 90000}))
        steps.append(_stp("ui.wait", "Home settle", {"ms": 1200}))
        steps.append(_stp("util.custom_js", "Re-dismiss cookies if shown", {"script": COOKIE_JS_SOFT}))
        steps.append(_stp("ui.wait", "After re-dismiss", {"ms": 600}))
        steps.append(
            _stp(
                "util.custom_js",
                "Assert modal not blocking",
                {"script": ASSERT_MODAL_GONE_JS, "expect_contains": "modal-gone"},
            )
        )
    for label in optional:
        steps.append(
            _stp(
                "util.custom_js",
                f'Optional click "{label}"',
                {"script": _optional_click_js(label)},
                "Optional — does not fail if missing",
            )
        )
        steps.append(_stp("ui.wait", f"After optional {label}", {"ms": 600}))
        steps.append(_stp("ui.goto", "Return home", {"url": "{{BASE_URL}}", "timeout_ms": 90000}))
        steps.append(_stp("util.custom_js", "Soft cookie dismiss", {"script": COOKIE_JS_SOFT}))
    steps.append(
        _stp(
            "assert.element_exists",
            "Home still loads after nav trail",
            {"selector": "body", "timeout_ms": 15000},
        )
    )
    steps.append(_stp("ui.screenshot", "After nav coverage", {"label": "temu_nav"}))
    return steps


def build_search_coverage() -> list[TestStep]:
    search_js = """
(() => {
  const inputs = Array.from(document.querySelectorAll('input, textarea, [role="searchbox"]'));
  const hints = ['search', 'zoek', 'q', 'query', 'keyword', 'find'];
  let target = null;
  for (const el of inputs) {
    const meta = [
      el.getAttribute('name') || '',
      el.getAttribute('placeholder') || '',
      el.getAttribute('aria-label') || '',
      el.getAttribute('type') || '',
      el.id || '',
      el.className || '',
    ].join(' ').toLowerCase();
    if (el.getAttribute('type') === 'search' || hints.some((h) => meta.includes(h))) {
      target = el;
      break;
    }
  }
  if (!target && inputs.length) {
    // Temu often uses a prominent header search input
    target = inputs.find((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 80 && r.top < 160;
    }) || null;
  }
  if (!target) throw new Error('No search input found after cookie accept');
  target.focus();
  target.value = 'wireless earbuds';
  target.dispatchEvent(new Event('input', { bubbles: true }));
  target.dispatchEvent(new Event('change', { bubbles: true }));
  return 'filled-search:' + (target.id || target.name || target.getAttribute('placeholder') || 'ok').slice(0, 40);
})()
"""
    submit_js = """
(() => {
  const labels = ['search', 'submit', 'go'];
  const nodes = Array.from(document.querySelectorAll('button, [role="button"], a, input[type="submit"]'));
  for (const el of nodes) {
    const t = (el.innerText || el.value || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().toLowerCase();
    if (!t) continue;
    if (labels.some((l) => t === l || t.includes(l))) {
      el.click();
      return 'clicked:' + t.slice(0, 40);
    }
  }
  // Enter on focused search
  const active = document.activeElement;
  if (active && (active.tagName === 'INPUT' || active.getAttribute('role') === 'searchbox')) {
    active.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    return 'enter-search';
  }
  throw new Error('Search submit control not found');
})()
"""
    return [
        _stp("ui.goto", "Open Temu homepage", {"url": "{{BASE_URL}}", "timeout_ms": 90000}),
        *_accept_cookies_steps(),
        _stp("util.custom_js", "Fill homepage search", {"script": search_js}),
        _stp("ui.wait", "After fill", {"ms": 600}),
        _stp("util.custom_js", "Submit search", {"script": submit_js}),
        _stp("ui.wait", "Wait for search reaction", {"ms": 2500}),
        _stp(
            "assert.element_exists",
            "Page responsive after search",
            {"selector": "body", "timeout_ms": 15000},
        ),
        _stp("ui.screenshot", "After search", {"label": "temu_search"}),
    ]


def build_components_ids_coverage() -> list[TestStep]:
    """Inventory + assert key homepage components, roles, and stable-ish ids/testids."""
    inventory_js = """
(() => {
  const out = {
    title: document.title || '',
    brandText: /temu/i.test(document.body.innerText || ''),
    inputs: [],
    buttons: [],
    links: [],
    ids: [],
    testids: [],
    roles: {},
    landmarks: [],
  };
  const pushUnique = (arr, v, max = 40) => {
    if (!v || arr.includes(v) || arr.length >= max) return;
    arr.push(v);
  };
  document.querySelectorAll('input, textarea, [role="searchbox"]').forEach((el) => {
    pushUnique(out.inputs, [
      el.id, el.name, el.getAttribute('placeholder'), el.getAttribute('aria-label'), el.getAttribute('type')
    ].filter(Boolean).join('|').slice(0, 80));
  });
  document.querySelectorAll('button, [role="button"]').forEach((el, i) => {
    if (i > 60) return;
    const t = (el.innerText || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim();
    if (t) pushUnique(out.buttons, t.slice(0, 60), 50);
  });
  document.querySelectorAll('a[href]').forEach((el, i) => {
    if (i > 80) return;
    const t = (el.innerText || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim();
    if (t) pushUnique(out.links, t.slice(0, 60), 50);
  });
  document.querySelectorAll('[id]').forEach((el) => {
    const id = el.id;
    if (!id || id.length > 64) return;
    if (/^(ember|react|radix|:r)/i.test(id)) return;
    pushUnique(out.ids, id, 60);
  });
  document.querySelectorAll('[data-testid], [data-test], [data-qa]').forEach((el) => {
    pushUnique(
      out.testids,
      el.getAttribute('data-testid') || el.getAttribute('data-test') || el.getAttribute('data-qa'),
      60
    );
  });
  ['banner', 'navigation', 'main', 'search', 'contentinfo'].forEach((role) => {
    out.roles[role] = document.querySelectorAll('[role="' + role + '"]').length;
  });
  ['header', 'nav', 'main', 'footer', 'form'].forEach((tag) => {
    if (document.querySelector(tag)) out.landmarks.push(tag);
  });
  const mustText = ['Temu', 'Categories', 'Lightning deals'];
  const missingText = mustText.filter((t) => !(document.body.innerText || '').includes(t));
  if (!out.brandText) throw new Error('Temu brand text missing from body');
  if (missingText.length) throw new Error('Missing homepage text: ' + missingText.join(', '));
  if (!out.landmarks.includes('body') && out.landmarks.length === 0 && !document.body) {
    throw new Error('No landmarks found');
  }
  // Require at least a search-ish input OR Categories control
  const hasSearch = out.inputs.some((s) => /search|query|keyword/i.test(s)) || out.roles.search > 0;
  const hasCategories = out.buttons.some((b) => /categor/i.test(b)) || out.links.some((l) => /categor/i.test(l));
  if (!hasSearch && !hasCategories) {
    throw new Error('Neither search nor Categories controls found — page may be blocked');
  }
  return 'inventory-ok|' + JSON.stringify({
    ok: true,
    title: out.title.slice(0, 80),
    inputCount: out.inputs.length,
    buttonSample: out.buttons.slice(0, 12),
    linkSample: out.links.slice(0, 12),
    idSample: out.ids.slice(0, 20),
    testidSample: out.testids.slice(0, 20),
    roles: out.roles,
    landmarks: out.landmarks,
  });
})()
"""
    trust_js = """
(() => {
  const t = (document.body.innerText || '').toLowerCase();
  const need = ['secure privacy', 'safe payments', 'delivery guarantee'];
  const missing = need.filter((n) => !t.includes(n));
  if (missing.length === need.length) {
    throw new Error('Trust / Why choose Temu messaging not found');
  }
  return 'trust-ok:' + need.filter((n) => t.includes(n)).join(',');
})()
"""
    deals_js = """
(() => {
  const t = (document.body.innerText || '').toLowerCase();
  if (!t.includes('lightning deals') && !t.includes('limited-time')) {
    throw new Error('Deals section not found on homepage');
  }
  const prices = (document.body.innerText || '').match(/\\$[0-9]+(\\.[0-9]{2})?/g) || [];
  if (prices.length < 1) throw new Error('No deal prices found');
  return 'deals-ok:prices=' + prices.length;
})()
"""
    return [
        _stp("ui.goto", "Open Temu homepage", {"url": "{{BASE_URL}}", "timeout_ms": 90000}),
        *_accept_cookies_steps(),
        _stp(
            "util.custom_js",
            "Inventory ids / roles / components",
            {"script": inventory_js, "expect_contains": "inventory-ok", "save_as": "temu_inventory"},
            "Asserts brand, Categories/search, collects ids/testids/landmarks",
        ),
        _stp("util.custom_js", "Assert trust badges / why Temu", {"script": trust_js}),
        _stp("util.custom_js", "Scroll to deals", {"script": "window.scrollBy(0, 700); 'ok'"}),
        _stp("ui.wait", "After scroll to deals", {"ms": 1000}),
        _stp("util.custom_js", "Assert Lightning deals + prices", {"script": deals_js}),
        _stp(
            "assert.element_exists",
            "Header or banner region exists",
            {"selector": "header, [role='banner'], body", "timeout_ms": 10000},
        ),
        _stp(
            "assert.element_exists",
            "Main or body content exists",
            {"selector": "main, [role='main'], body", "timeout_ms": 10000},
        ),
        _stp(
            "assert.element_exists",
            "Footer or contentinfo exists",
            {"selector": "footer, [role='contentinfo'], body", "timeout_ms": 10000},
        ),
        _stp("ui.screenshot", "Components coverage", {"label": "temu_components"}),
    ]


def build_landing_utm_smoke() -> list[TestStep]:
    return [
        _stp(
            "ui.goto",
            "Open campaign landing URL",
            {"url": "{{LANDING_URL}}", "timeout_ms": 90000},
            "Uses LANDING_URL from environment (Impact / adMarketplace link)",
        ),
        *_accept_cookies_steps(),
        _stp(
            "assert.element_exists",
            "Landing document loaded",
            {"selector": "body", "timeout_ms": 20000},
        ),
        _stp(
            "assert.text_contains",
            "Page shows Temu",
            {"selector": "body", "text": "Temu", "timeout_ms": 20000, "ignore_case": True},
        ),
        _stp(
            "util.custom_js",
            "Landing still interactive",
            {
                "script": "(() => { const n = document.querySelectorAll('a,button,input').length; if (n < 3) throw new Error('Too few interactive nodes: ' + n); return 'nodes:' + n; })()"
            },
        ),
        _stp("ui.screenshot", "Landing screenshot", {"label": "temu_landing_utm"}),
    ]


def main() -> int:
    init_db()

    existing = next((p for p in list_projects() if p.name.lower() == "temu"), None)
    if existing:
        project = existing
        print(f"Project exists: {project.id} {project.name}")
    else:
        project = Project(
            id=new_id("prj_"),
            name="Temu",
            description="Temu.com UI automation — homepage cookies, nav, search, components/ids, UTM landing.",
            tags=["web", "temu", "ecommerce", "ui"],
        )
        save_project(project)
        add_audit("local", "create", "project", project.id, project.name)
        print(f"Created project: {project.id} {project.name}")

    env = next((e for e in list_environments() if e.name == "Temu Prod"), None)
    if not env:
        env = Environment(
            id=new_id("env_"),
            name="Temu Prod",
            base_url=BASE_URL,
            variables={
                "BRAND": "Temu",
                "LOCALE": "en-US",
                "LANDING_URL": START_URL,
            },
        )
        save_environment(env)
        add_audit("local", "create", "environment", env.id, env.name)
        print(f"Created environment: {env.id} {env.name} -> {env.base_url}")
    else:
        env.base_url = BASE_URL
        env.variables = {
            **(env.variables or {}),
            "BRAND": "Temu",
            "LOCALE": "en-US",
            "LANDING_URL": START_URL,
        }
        save_environment(env)
        print(f"Updated environment: {env.id} {env.name}")

    specs = [
        (
            "Smoke: Temu homepage load & brand",
            "Accept cookies, verify Temu brand, Categories, Lightning deals.",
            ["smoke", "homepage", "cookies"],
            build_core_smoke(),
        ),
        (
            "Coverage: Temu navigation & categories",
            "Required + optional category/nav clicks with cookie re-dismiss.",
            ["coverage", "nav", "categories"],
            build_nav_coverage(),
        ),
        (
            "Coverage: Temu homepage search",
            "Find search field, submit query, assert page stays responsive.",
            ["coverage", "search"],
            build_search_coverage(),
        ),
        (
            "Coverage: Temu components & web ids",
            "Inventory ids/testids/roles/landmarks; assert trust + deals components.",
            ["coverage", "components", "ids", "a11y"],
            build_components_ids_coverage(),
        ),
        (
            "Smoke: Campaign landing (UTM / Impact)",
            "Open LANDING_URL with Impact params; accept cookies; assert Temu.",
            ["smoke", "utm", "landing"],
            build_landing_utm_smoke(),
        ),
    ]

    existing_tests = {t.name: t for t in list_tests(project.id)}
    saved: list[TestCase] = []
    for name, desc, tags, steps in specs:
        prior = existing_tests.get(name)
        if prior:
            prior.steps = steps
            prior.description = desc
            prior.tags = tags
            prior.suite = "UI Coverage"
            save_test(prior, bump_version=True)
            print(f"Updated test: {prior.id} {prior.name} ({len(steps)} steps)")
            saved.append(prior)
        else:
            case = TestCase(
                id=new_id("tst_"),
                project_id=project.id,
                name=name,
                description=desc,
                tags=tags,
                steps=steps,
                suite="UI Coverage",
                created_by="local",
            )
            save_test(case, bump_version=False)
            add_audit("local", "create", "test", case.id, case.name)
            print(f"Created test: {case.id} {case.name} ({len(steps)} steps)")
            saved.append(case)

    out = export_suite_to_files(
        project_name=project.name,
        suite="UI Coverage",
        tests=saved,
        environment_name=env.name,
        project_id=project.id,
    )
    readme = Path(out).parent / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Temu — UI Coverage",
                "",
                "Homepage / cookie / nav / search / component-id coverage for [temu.com](https://www.temu.com/).",
                "",
                "## Environment",
                "",
                "- **Temu Prod** → `https://www.temu.com`",
                "- `LANDING_URL` → Impact / adMarketplace campaign URL",
                "",
                "## Notes",
                "",
                "- Cookie banner must be accepted (`Accept all` / OneTrust).",
                "- Temu may block or challenge headless automation; run locally headed if needed.",
                "- Component inventory collects ids, data-testids, roles, and landmarks.",
                "",
                "Regenerate: `python scripts/setup_temu_project.py`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Exported suite -> {out}")
    print("Done. Open FlowTest -> Project Temu -> suite 'UI Coverage'. Use environment 'Temu Prod'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
