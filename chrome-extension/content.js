(() => {
  if (window.__flowtestExtInstalled) return;
  window.__flowtestExtInstalled = true;

  let recording = false;
  let installedUi = false;

  const cssPath = (el) => {
    if (!el || el.nodeType !== 1) return "";
    const name = el.getAttribute && el.getAttribute("name");
    if (name && /^callback_\d+$/i.test(name)) return `[name="${name}"]`;
    const vv = el.getAttribute && el.getAttribute("data-vv-as");
    if (vv) {
      const esc = typeof CSS !== "undefined" && CSS.escape ? CSS.escape(vv) : vv.replace(/"/g, '\\"');
      return `[data-vv-as="${esc}"]`;
    }
    const testId = el.getAttribute && el.getAttribute("data-testid");
    if (testId && testId !== "input-") {
      const esc = typeof CSS !== "undefined" && CSS.escape ? CSS.escape(testId) : testId;
      return `[data-testid="${esc}"]`;
    }
    if (el.id) {
      const id = el.id;
      if (!/^floatingLabelInput\d+$/i.test(id)) {
        if (typeof CSS !== "undefined" && CSS.escape) return `#${CSS.escape(id)}`;
        return `#${id.replace(/([^a-zA-Z0-9_-])/g, "\\$1")}`;
      }
      if (name) return `[name="${name}"]`;
    }
    if (name) return `[name="${name}"]`;
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 6) {
      let part = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter((c) => c.tagName === node.tagName);
        if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      node = parent;
      if (node && node.tagName && node.tagName.toLowerCase() === "body") {
        parts.unshift("body");
        break;
      }
    }
    return parts.join(" > ");
  };

  const labelOf = (el) =>
    el.getAttribute("aria-label") ||
    el.getAttribute("name") ||
    el.getAttribute("placeholder") ||
    el.getAttribute("title") ||
    (el.innerText || "").trim().slice(0, 60) ||
    el.tagName.toLowerCase();

  const emit = (payload) => {
    if (!recording) return;
    try {
      chrome.runtime.sendMessage({ type: "flowtest:event", payload });
    } catch (_) {}
  };

  const escapeHtml = (s) =>
    String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  window.__flowtest_lastSelection = { text: "", selector: "body" };

  const ensureBar = () => {
    if (!recording || !document.body) return;
    let bar = document.getElementById("flowtest-recorder-bar");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "flowtest-recorder-bar";
      bar.style.cssText = [
        "position:fixed",
        "z-index:2147483647",
        "left:12px",
        "right:12px",
        "top:12px",
        "display:flex",
        "flex-wrap:wrap",
        "gap:10px",
        "align-items:center",
        "justify-content:space-between",
        "padding:10px 14px",
        "border-radius:10px",
        "background:#241e1b",
        "color:#fffcfb",
        "font:600 13px/1.35 system-ui,sans-serif",
        "box-shadow:0 8px 24px rgba(0,0,0,.35)",
      ].join(";");
      bar.innerHTML = `
        <div style="flex:1;min-width:220px;">
          <div style="color:#ff9db3;letter-spacing:.04em;text-transform:uppercase;font-size:11px;">FlowTest recording (extension)</div>
          <div style="font-weight:500;opacity:.92;margin-top:2px;">
            Click · type · navigate. <b>Select text</b>, then <b>Assert selection</b> (or press <b>A</b>).
          </div>
          <div id="flowtest-selection-preview" style="margin-top:6px;font-weight:500;font-size:12px;color:#ffc6d3;display:none;max-width:720px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"></div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
          <button id="flowtest-assert-btn" type="button" style="border:0;border-radius:8px;padding:8px 12px;cursor:pointer;background:#ffc6d3;color:#241e1b;font-weight:700;opacity:0.45;" disabled>Assert selection</button>
          <button id="flowtest-finish-btn" type="button" style="border:0;border-radius:8px;padding:8px 14px;cursor:pointer;background:#f83b66;color:#fff;font-weight:700;">Finish recording</button>
        </div>`;
      document.body.appendChild(bar);
      installedUi = true;

      const updateAssertButton = () => {
        const btn = document.getElementById("flowtest-assert-btn");
        const preview = document.getElementById("flowtest-selection-preview");
        const text = (window.__flowtest_lastSelection && window.__flowtest_lastSelection.text) || "";
        if (!btn || !preview) return;
        if (text) {
          btn.disabled = false;
          btn.style.opacity = "1";
          btn.style.cursor = "pointer";
          preview.style.display = "block";
          preview.innerHTML =
            "Selected: “" + escapeHtml(text.slice(0, 120)) + (text.length > 120 ? "…" : "") + "”";
        } else {
          btn.disabled = true;
          btn.style.opacity = "0.45";
          btn.style.cursor = "not-allowed";
          preview.style.display = "none";
          preview.textContent = "";
        }
      };

      const captureSelection = () => {
        const sel = window.getSelection && window.getSelection();
        if (!sel || sel.isCollapsed || !sel.rangeCount) return;
        const text = (sel.toString() || "").replace(/\s+/g, " ").trim();
        if (!text || text.length < 2 || text.length > 300) return;
        let node = sel.getRangeAt(0).commonAncestorContainer;
        if (node && node.nodeType === 3) node = node.parentElement;
        let el = node;
        if (el && el.closest && el.closest("#flowtest-recorder-bar")) return;
        while (el && el !== document.body) {
          const tag = (el.tagName || "").toLowerCase();
          if (
            ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "button", "a", "label", "span", "div", "section", "article"].includes(
              tag
            )
          )
            break;
          el = el.parentElement;
        }
        window.__flowtest_lastSelection = { text, selector: cssPath(el || document.body) || "body" };
        updateAssertButton();
      };

      const assertSelection = () => {
        const sel = window.__flowtest_lastSelection || {};
        const text = (sel.text || "").trim();
        if (!text) return;
        emit({ type: "assert_text", text, selector: sel.selector || "body", ts: Date.now() });
        const preview = document.getElementById("flowtest-selection-preview");
        if (preview) {
          preview.style.display = "block";
          preview.style.color = "#86efac";
          preview.textContent =
            "✓ Assertion added: “" + text.slice(0, 100) + (text.length > 100 ? "…" : "") + "”";
          setTimeout(() => {
            preview.style.color = "#ffc6d3";
            updateAssertButton();
          }, 1600);
        }
        try {
          window.getSelection().removeAllRanges();
        } catch (_) {}
      };

      document.getElementById("flowtest-finish-btn").addEventListener(
        "click",
        (e) => {
          e.preventDefault();
          e.stopPropagation();
          const btn = e.currentTarget;
          btn.textContent = "Saving…";
          btn.disabled = true;
          chrome.runtime.sendMessage({ type: "flowtest:finish" }, () => {
            recording = false;
            removeBar();
          });
        },
        true
      );
      document.getElementById("flowtest-assert-btn").addEventListener(
        "click",
        (e) => {
          e.preventDefault();
          e.stopPropagation();
          assertSelection();
        },
        true
      );

      document.addEventListener(
        "mouseup",
        (e) => {
          if (!recording) return;
          if (e.target && e.target.closest && e.target.closest("#flowtest-recorder-bar")) return;
          setTimeout(captureSelection, 10);
        },
        true
      );

      document.addEventListener(
        "keyup",
        (e) => {
          if (!recording) return;
          if (e.target && e.target.closest && e.target.closest("#flowtest-recorder-bar")) return;
          const tag = ((e.target && e.target.tagName) || "").toLowerCase();
          if (["input", "textarea", "select"].includes(tag) || e.target.isContentEditable) return;
          if ((e.key === "a" || e.key === "A") && window.__flowtest_lastSelection.text) {
            e.preventDefault();
            assertSelection();
          }
        },
        true
      );

      bar.__updateAssert = updateAssertButton;
    }
    bar.style.display = "flex";
  };

  const removeBar = () => {
    const bar = document.getElementById("flowtest-recorder-bar");
    if (bar) bar.remove();
    installedUi = false;
  };

  document.addEventListener(
    "click",
    (e) => {
      if (!recording) return;
      const t = e.target;
      if (!t || !t.closest) return;
      if (t.closest("#flowtest-recorder-bar")) return;
      const sel = window.getSelection && window.getSelection();
      if (sel && !sel.isCollapsed && (sel.toString() || "").trim().length >= 2) return;

      const optionish = t.closest(
        '[role="option"], [role="menuitem"], [role="treeitem"], [role="radio"],' +
          'li[role="option"], .dropdown-item, .multiselect__option, .vs__dropdown-option,' +
          '.hz-option, [data-option], label'
      );
      let el =
        optionish ||
        t.closest('a,button,input,select,textarea,[role="button"],[onclick],[role="tab"]') ||
        t;
      if (el.tagName && el.tagName.toLowerCase() === "select") return;

      if (
        el.tagName &&
        el.tagName.toLowerCase() === "input" &&
        (el.getAttribute("type") || "").toLowerCase() === "radio"
      ) {
        const lab = el.id
          ? document.querySelector('label[for="' + el.id + '"]')
          : el.closest("label");
        if (lab) el = lab;
      }

      const visibleText = ((el.innerText || el.textContent || el.value || "") + "")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 120);
      const role = (el.getAttribute && el.getAttribute("role")) || "";
      const isOptionLike = !!(
        optionish ||
        role === "option" ||
        role === "menuitem" ||
        role === "radio" ||
        (el.classList &&
          (el.classList.contains("dropdown-item") || el.classList.contains("multiselect__option"))) ||
        (el.tagName && el.tagName.toLowerCase() === "label" && visibleText)
      );

      if (isOptionLike && visibleText) {
        emit({
          type: "click_by_text",
          text: visibleText,
          exact: role === "option" || role === "menuitem",
          role: role || (optionish ? "option" : ""),
          selector: cssPath(el),
          label: visibleText,
          ts: Date.now(),
        });
        return;
      }

      emit({
        type: "click",
        selector: cssPath(el),
        text: visibleText.slice(0, 80),
        tag: (el.tagName || "").toLowerCase(),
        inputType: (el.getAttribute && el.getAttribute("type")) || "",
        label: labelOf(el),
        href: (el.getAttribute && el.getAttribute("href")) || "",
        ts: Date.now(),
      });
    },
    true
  );

  const onFieldCommit = (el) => {
    if (!recording || !el || !el.tagName) return;
    const tag = el.tagName.toLowerCase();
    if (tag === "select") {
      const optText =
        el.options && el.selectedIndex >= 0 ? el.options[el.selectedIndex].text : "";
      emit({
        type: "select_by_text",
        selector: cssPath(el),
        text: (optText || "").trim(),
        label: (optText || "").trim(),
        exact: false,
        name: labelOf(el),
        ts: Date.now(),
      });
      return;
    }
    if (tag !== "input" && tag !== "textarea") return;
    const inputType = (el.getAttribute("type") || "text").toLowerCase();
    if (["button", "submit", "reset", "checkbox", "radio", "file", "image"].includes(inputType))
      return;
    emit({
      type: "fill",
      selector: cssPath(el),
      value: el.value || "",
      inputType,
      name: labelOf(el),
      ts: Date.now(),
    });
  };

  document.addEventListener("change", (e) => onFieldCommit(e.target), true);
  document.addEventListener(
    "blur",
    (e) => {
      const t = e.target;
      if (t && t.tagName && ["INPUT", "TEXTAREA"].includes(t.tagName)) onFieldCommit(t);
    },
    true
  );

  chrome.runtime.onMessage.addListener((msg) => {
    if (!msg) return;
    if (msg.type === "flowtest:setRecording") {
      recording = !!msg.recording;
      if (recording) ensureBar();
      else removeBar();
    }
  });

  chrome.runtime.sendMessage({ type: "flowtest:getState" }, (state) => {
    if (chrome.runtime.lastError) return;
    recording = !!(state && state.recording);
    if (recording) ensureBar();
  });

  setInterval(() => {
    if (recording) ensureBar();
  }, 1200);
})();
