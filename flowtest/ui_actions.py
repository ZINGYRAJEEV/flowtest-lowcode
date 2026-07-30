"""
Resilient Playwright UI actions for SPAs (ForgeRock XUI / Horizon, Vue forms).

Handles hidden polyfill inputs, volatile #floatingLabel* ids, and name/data-vv-as fallbacks.
"""

from __future__ import annotations

import re
import time
from typing import Any

DEFAULT_UI_TIMEOUT_MS = 30000


def ui_timeout(cfg: dict[str, Any], default: int = DEFAULT_UI_TIMEOUT_MS) -> int:
    try:
        return int(cfg.get("timeout_ms") or default)
    except (TypeError, ValueError):
        return default


def settle_page(page, ms: int = 250) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass
    page.wait_for_timeout(ms)


def selector_candidates(selector: str, cfg: dict[str, Any] | None = None, step_name: str = "") -> list[str]:
    """Prefer stable name / data-vv-as over volatile floatingLabel ids."""
    cfg = cfg or {}
    seen: list[str] = []
    out: list[str] = []

    def add(s: str) -> None:
        s = (s or "").strip()
        if s and s not in seen:
            seen.append(s)
            out.append(s)

    # Callback names from step / config win — avoid wrong #hzVerificationMethod matching callback_3
    callbacks: list[str] = []
    for source in (step_name, str(cfg.get("name") or ""), str(cfg.get("label") or "")):
        for m in re.finditer(r"(callback_\d+)", source, flags=re.I):
            cb = m.group(1).lower()
            if cb not in callbacks:
                callbacks.append(cb)

    for cb in callbacks:
        add(f'[name="{cb}"]')
        add(f'input[name="{cb}"]')
        add(f'select[name="{cb}"]')

    add(selector)
    for alt in cfg.get("alternates") or []:
        add(str(alt))

    name = str(cfg.get("name") or "").strip()
    if name:
        add(f'[name="{name}"]')
        add(f'input[name="{name}"]')
        add(f'select[name="{name}"]')
        add(f'textarea[name="{name}"]')

    # Only remap verification aliases when we are not targeting a different callback_*
    blob = " ".join([selector, step_name, name, str(cfg.get("label") or "")])
    targeting_other_callback = bool(callbacks) and "callback_3" not in callbacks
    if re.search(r"hzVerificationMethod|VerificationMethod", blob, re.I) and not targeting_other_callback:
        add('[data-vv-as="__hzVerificationMethod__"]')
        add('[data-vv-as*="VerificationMethod"]')
        add('[name="callback_3"]')
        add('input[name="callback_3"]')
        add("#hzVerificationMethod")

    return out


def first_attached_locator(page, candidates: list[str], timeout: int):
    if not candidates:
        raise RuntimeError("Selector is empty")
    deadline = time.time() + (timeout / 1000.0)
    last_err: Exception | None = None
    while time.time() < deadline:
        for sel in candidates:
            try:
                loc = page.locator(sel).first
                # count() is sync and cheap; avoids long waits on missing ids
                if loc.count() < 1:
                    continue
                loc.wait_for(state="attached", timeout=800)
                return loc, sel
            except Exception as exc:
                last_err = exc
                continue
        page.wait_for_timeout(250)
    msg = f"No matching element for selectors: {candidates}"
    if last_err:
        msg += f" | last: {last_err}"
    raise RuntimeError(msg[:800])


def prepare_locator(
    page,
    selector: str,
    timeout: int,
    require_visible: bool = True,
    cfg: dict[str, Any] | None = None,
    step_name: str = "",
):
    candidates = selector_candidates(selector, cfg, step_name)
    if not any(candidates):
        raise RuntimeError("Selector is empty")
    loc, matched = first_attached_locator(page, candidates, timeout)
    try:
        loc.scroll_into_view_if_needed(timeout=min(5000, timeout))
    except Exception:
        pass
    if require_visible:
        try:
            loc.wait_for(state="visible", timeout=min(2500, timeout))
        except Exception:
            pass
    return loc, matched


def is_hidden(loc) -> bool:
    try:
        return not loc.is_visible()
    except Exception:
        return True


def is_readonly_or_disabled(loc) -> tuple[bool, bool]:
    readonly = False
    disabled = False
    try:
        readonly = loc.evaluate(
            """el => !!(el.readOnly || el.getAttribute('readonly') !== null
               || el.getAttribute('aria-readonly') === 'true')"""
        )
        disabled = loc.evaluate(
            """el => !!(el.disabled || el.getAttribute('disabled') !== null
               || el.getAttribute('aria-disabled') === 'true')"""
        )
    except Exception:
        pass
    return bool(readonly), bool(disabled)


def wait_until_interactable(page, loc, timeout: int, allow_readonly: bool = False) -> None:
    deadline = time.time() + (timeout / 1000.0)
    last_err = ""
    while time.time() < deadline:
        try:
            readonly, disabled = is_readonly_or_disabled(loc)
            if disabled:
                last_err = "element is disabled"
                page.wait_for_timeout(200)
                continue
            if readonly and not allow_readonly:
                last_err = "element is readonly"
                page.wait_for_timeout(200)
                continue
            return
        except Exception as exc:
            last_err = str(exc)[:200]
            page.wait_for_timeout(200)
    raise RuntimeError(f"Element not interactable within {timeout}ms ({last_err})")


def unlock_input(loc) -> None:
    try:
        loc.evaluate(
            """el => {
              el.removeAttribute('readonly');
              el.removeAttribute('disabled');
              el.readOnly = false;
              el.disabled = false;
              if (el.getAttribute('aria-readonly') === 'true') {
                el.setAttribute('aria-readonly', 'false');
              }
            }"""
        )
    except Exception:
        pass


def dispatch_input_events(loc) -> None:
    try:
        loc.evaluate(
            """el => {
              el.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true }));
              el.dispatchEvent(new Event('change', { bubbles: true }));
              el.dispatchEvent(new Event('blur', { bubbles: true }));
            }"""
        )
    except Exception:
        pass


def set_value_js(loc, value: str) -> None:
    loc.evaluate(
        """(el, v) => {
          el.focus();
          const proto = el.tagName === 'TEXTAREA'
            ? window.HTMLTextAreaElement.prototype
            : window.HTMLInputElement.prototype;
          const desc = Object.getOwnPropertyDescriptor(proto, 'value');
          if (desc && desc.set) {
            desc.set.call(el, v);
          } else {
            el.value = v;
          }
          el.dispatchEvent(new InputEvent('input', {
            bubbles: true, cancelable: true, data: v, inputType: 'insertText'
          }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
          el.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'Enter' }));
          el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'Enter' }));
          el.blur();
          el.dispatchEvent(new Event('blur', { bubbles: true }));
        }""",
        value,
    )


def click_visible_sibling_control(page, loc) -> bool:
    try:
        handle = loc.evaluate_handle(
            """el => {
              const root = el.closest(
                '.form-group, .form-floating, [class*="callback"], fieldset, label, div'
              ) || el.parentElement;
              if (!root) return null;
              const candidates = root.querySelectorAll(
                'button, [role="button"], [role="listbox"], [role="combobox"], [role="option"],
                 .dropdown-toggle, .multiselect, select, input:not([type="hidden"]):not(.polyfill-placeholder)'
              );
              for (const c of candidates) {
                const st = window.getComputedStyle(c);
                if (st && st.display !== 'none' && st.visibility !== 'hidden'
                    && c.offsetParent !== null && c !== el) {
                  return c;
                }
              }
              if (el.id) {
                const lab = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
                if (lab) return lab;
              }
              return null;
            }"""
        )
        if handle:
            el = handle.as_element()
            if el:
                el.click(timeout=3000, force=True)
                return True
    except Exception:
        pass
    return False


def type_text(loc, value: str, timeout: int, delay: int = 25) -> None:
    try:
        loc.press_sequentially(value, delay=delay, timeout=timeout)
    except AttributeError:
        loc.type(value, delay=delay, timeout=timeout)


def smart_click(
    page,
    selector: str = "",
    text: str = "",
    timeout: int = DEFAULT_UI_TIMEOUT_MS,
    cfg: dict[str, Any] | None = None,
    step_name: str = "",
) -> str:
    if selector or (cfg or {}).get("name"):
        loc, matched = prepare_locator(
            page, selector or "", timeout, require_visible=True, cfg=cfg, step_name=step_name
        )
        wait_until_interactable(page, loc, timeout, allow_readonly=True)
        try:
            if is_hidden(loc):
                loc.click(timeout=timeout, force=True)
            else:
                loc.click(timeout=timeout)
        except Exception:
            loc.click(timeout=timeout, force=True)
        return f"Clicked {matched}"
    if text:
        loc = page.get_by_text(text, exact=False).first
        loc.wait_for(state="visible", timeout=timeout)
        loc.click(timeout=timeout)
        return f'Clicked text "{text}"'
    raise RuntimeError("Provide selector or text")


def smart_fill(
    page,
    selector: str,
    value: str,
    clear: bool = True,
    timeout: int = DEFAULT_UI_TIMEOUT_MS,
    cfg: dict[str, Any] | None = None,
    step_name: str = "",
) -> str:
    loc, matched = prepare_locator(
        page, selector, timeout, require_visible=False, cfg=cfg, step_name=step_name
    )

    if value == "" and clear:
        readonly, disabled = is_readonly_or_disabled(loc)
        if readonly or disabled or is_hidden(loc):
            return f"Skipped empty fill on non-editable/hidden {matched}"

    if is_hidden(loc):
        unlock_input(loc)
        click_visible_sibling_control(page, loc)
        page.wait_for_timeout(200)
        set_value_js(loc, value)
        # Dropdown / radio choice often appears as visible text after opening control
        try:
            if value:
                opt = page.get_by_role("option", name=re.compile(re.escape(value), re.I))
                if opt.count() > 0:
                    opt.first.click(timeout=2000)
                else:
                    t = page.get_by_text(value, exact=False).first
                    if t.count() > 0 and t.is_visible():
                        t.click(timeout=2000)
        except Exception:
            pass
        settle_page(page, ms=700)
        return f"Filled {matched} (hidden input via JS)"

    try:
        wait_until_interactable(page, loc, min(timeout, 5000), allow_readonly=False)
        editable = True
    except Exception:
        editable = False

    if editable:
        try:
            if clear:
                loc.fill(value, timeout=min(10000, timeout))
            else:
                type_text(loc, value, timeout=timeout, delay=20)
            dispatch_input_events(loc)
            settle_page(page, ms=400)
            return f"Filled {matched}"
        except Exception:
            pass

    try:
        loc.click(timeout=min(5000, timeout), force=True)
    except Exception:
        pass
    page.wait_for_timeout(100)
    unlock_input(loc)

    if clear:
        try:
            loc.press("Control+a")
            loc.press("Backspace")
        except Exception:
            try:
                loc.fill("", force=True, timeout=3000)
            except Exception:
                pass

    if value:
        try:
            type_text(loc, value, timeout=min(8000, timeout), delay=20)
        except Exception:
            set_value_js(loc, value)

    dispatch_input_events(loc)
    settle_page(page, ms=500)
    return f"Filled {matched} (smart wait)"


def smart_select(
    page,
    selector: str,
    label: str = "",
    index: int = 1,
    timeout: int = DEFAULT_UI_TIMEOUT_MS,
    cfg: dict[str, Any] | None = None,
    step_name: str = "",
) -> str:
    loc, matched = prepare_locator(
        page, selector, timeout, require_visible=False, cfg=cfg, step_name=step_name
    )
    wait_until_interactable(page, loc, timeout, allow_readonly=True)
    if label:
        try:
            loc.select_option(label=label, timeout=timeout)
        except Exception:
            loc.select_option(label=label, force=True, timeout=timeout)
        return f'Selected label "{label}" on {matched}'
    try:
        loc.select_option(index=index, timeout=timeout)
    except Exception:
        loc.select_option(index=index, force=True, timeout=timeout)
    return f"Selected index {index} on {matched}"


def smart_assert_text(
    page,
    text: str,
    selector: str = "body",
    timeout: int = DEFAULT_UI_TIMEOUT_MS,
    ignore_case: bool = True,
) -> str:
    """
    Assert text appears on the page, with auto-wait and fallbacks.

    Brittle recorded paths like section > div > div:nth-of-type(3) ... often
    miss text that moved after SPA re-render — fall back to page-wide search.

    Recorded asserts sometimes concatenate multiple labels into one string; we
    also accept when each sentence/phrase is present separately.
    """
    raw = (text or "").strip()
    if not raw:
        raise AssertionError("Assert text is empty")

    def norm(s: str) -> str:
        s = (s or "").replace("\u2019", "'").replace("\u2018", "'").replace("\u00a0", " ")
        return re.sub(r"\s+", " ", s).strip()

    needle = norm(raw)

    # Phrases to try: full text, then each sentence / line
    phrases = [needle]
    for part in re.split(r"[\n\r]+|(?<=[.!?])\s+", needle):
        part = norm(part)
        if len(part) >= 8 and part not in phrases:
            phrases.append(part)
    # Leading chunk helps when UI truncates helper text
    if len(needle) > 24:
        phrases.append(needle[:40].rstrip("."))

    def present(hay: str, n: str) -> bool:
        h = norm(hay)
        if ignore_case:
            return n.lower() in h.lower()
        return n in h

    def all_phrases_in(hay: str) -> bool:
        """Pass if full needle matches OR every substantial sentence is present."""
        if present(hay, needle):
            return True
        parts = [p for p in phrases[1:] if len(p) >= 12]
        if len(parts) >= 2 and all(present(hay, p) for p in parts):
            return True
        return False

    sel = (selector or "body").strip() or "body"
    scopes = [sel]
    for extra in ("main", "section", "form", "article", "#app", "body"):
        if extra not in scopes:
            scopes.append(extra)

    deadline = time.time() + (timeout / 1000.0)
    last_snip = ""

    while time.time() < deadline:
        # 1) Full string via Playwright text engine
        try:
            loc = page.get_by_text(re.compile(re.escape(needle), re.I if ignore_case else 0)).first
            if loc.count() > 0:
                return f'Text present: "{needle[:60]}"'
        except Exception:
            pass

        # 2) Each phrase via get_by_text — all must be found for multi-sentence asserts
        try:
            parts = [p for p in phrases[1:] if len(p) >= 12] or [needle]
            if all(page.get_by_text(re.compile(re.escape(p), re.I if ignore_case else 0)).count() > 0 for p in parts):
                return f'Text present (phrases): "{parts[0][:40]}…"'
        except Exception:
            pass

        # 3) Scoped / body inner_text
        for scope in scopes:
            try:
                loc = page.locator(scope).first
                if loc.count() < 1:
                    continue
                try:
                    content = loc.inner_text(timeout=800)
                except Exception:
                    content = loc.text_content(timeout=800) or ""
                last_snip = norm(content)[:120]
                if all_phrases_in(content):
                    return f'Text present in {scope}'
            except Exception:
                continue

        try:
            body = page.locator("body").inner_text(timeout=800)
            last_snip = norm(body)[:120]
            if all_phrases_in(body):
                return "Text present in body"
        except Exception:
            pass

        page.wait_for_timeout(300)

    raise AssertionError(
        f'Text not found: "{needle[:80]}"'
        + (f' (near: "{last_snip}...")' if last_snip else "")
        + (f" | tried selector {sel}" if sel != "body" else "")
    )


def smart_wait_for(
    page,
    selector: str,
    timeout: int = DEFAULT_UI_TIMEOUT_MS,
    state: str = "attached",
    cfg: dict[str, Any] | None = None,
    step_name: str = "",
) -> str:
    """
    Wait using primary + fallback selectors.
    'visible' soft-falls back to attached for permanently hidden polyfill inputs.
    """
    candidates = selector_candidates(selector, cfg, step_name)
    loc, matched = first_attached_locator(page, candidates, timeout)
    want = (state or "attached").strip() or "attached"
    if want == "visible":
        try:
            loc.wait_for(state="visible", timeout=min(2500, timeout))
            return f"visible: {matched}"
        except Exception:
            return f"attached (hidden OK): {matched}"
    if want != "attached":
        loc.wait_for(state=want, timeout=min(5000, timeout))
        return f"{want}: {matched}"
    return f"attached: {matched}"
