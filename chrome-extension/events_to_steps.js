/**
 * Convert recorder events → FlowTest TestStep dicts (mirrors flowtest/recorder.py).
 */
(function (root) {
  function newId(prefix) {
    const hex = Array.from(crypto.getRandomValues(new Uint8Array(6)))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    return (prefix || "stp_") + hex;
  }

  function dedupeEvents(events) {
    const cleaned = [];
    for (const ev of events || []) {
      const et = ev.type;
      if (et === "finish") continue;
      if (et === "click") {
        const tag = (ev.tag || "").toLowerCase();
        const itype = (ev.inputType || "").toLowerCase();
        if (
          (tag === "input" || tag === "textarea") &&
          !["button", "submit", "checkbox", "radio"].includes(itype)
        ) {
          continue;
        }
      }
      const last = cleaned[cleaned.length - 1];
      if (et === "click_by_text" && last && last.type === "click_by_text" && last.text === ev.text) {
        cleaned[cleaned.length - 1] = ev;
        continue;
      }
      if (
        et === "select_by_text" &&
        last &&
        last.type === "select_by_text" &&
        last.selector === ev.selector
      ) {
        cleaned[cleaned.length - 1] = ev;
        continue;
      }
      if (et === "fill" && last && last.type === "fill" && last.selector === ev.selector) {
        cleaned[cleaned.length - 1] = ev;
        continue;
      }
      if (et === "goto" && last && last.type === "goto") {
        if (last.url === ev.url) continue;
        cleaned[cleaned.length - 1] = ev;
        continue;
      }
      if (
        et === "assert_text" &&
        last &&
        last.type === "assert_text" &&
        last.text === ev.text &&
        last.selector === ev.selector
      ) {
        continue;
      }
      cleaned.push(ev);
    }
    return cleaned;
  }

  function eventsToSteps(events, replaceBaseUrl) {
    const steps = [];
    const base = (replaceBaseUrl || "").replace(/\/$/, "");

    function autoWait(selector, label, state) {
      const sel = (selector || "").trim();
      if (!sel) return;
      const last = steps[steps.length - 1];
      if (last && last.type === "ui.wait_for" && (last.config || {}).selector === sel) return;
      const cfg = { selector: sel, timeout_ms: 30000, state: state || "attached" };
      if (String(label || "").startsWith("callback_")) cfg.name = String(label);
      steps.push({
        id: newId("stp_"),
        type: "ui.wait_for",
        name: `Wait for ${String(label || sel).slice(0, 40)}`,
        config: cfg,
        enabled: true,
        notes: "Auto-wait (recorded)",
      });
    }

    for (const ev of dedupeEvents(events)) {
      const et = ev.type;
      if (et === "goto") {
        let url = ev.url || "";
        let urlCfg = url;
        if (base && url.startsWith(base)) {
          const suffix = url.slice(base.length) || "/";
          urlCfg =
            url.replace(/\/$/, "") === base
              ? "{{BASE_URL}}"
              : "{{BASE_URL}}" + (suffix === "/" && url.replace(/\/$/, "") === base ? "" : suffix);
          if (url.replace(/\/$/, "") === base) urlCfg = "{{BASE_URL}}";
          else urlCfg = "{{BASE_URL}}" + suffix;
        }
        let path = url;
        try {
          path = new URL(url).pathname || url;
        } catch (_) {}
        steps.push({
          id: newId("stp_"),
          type: "ui.goto",
          name: `Navigate to ${path}`,
          config: { url: urlCfg, timeout_ms: 30000 },
          enabled: true,
          notes: "Recorded (Chrome extension)",
        });
        steps.push({
          id: newId("stp_"),
          type: "ui.wait",
          name: "Wait after navigate",
          config: { ms: 500 },
          enabled: true,
          notes: "Auto-wait (recorded)",
        });
      } else if (et === "click") {
        const selector = ev.selector || "";
        const text = (ev.text || "").trim();
        const label = ev.label || text || selector;
        if (text && (!selector || selector.includes("nth-of-type"))) {
          steps.push({
            id: newId("stp_"),
            type: "ui.click_by_text",
            name: `Click text "${text.slice(0, 40)}"`,
            config: { text, exact: false, role: "", within: "", timeout_ms: 30000 },
            enabled: true,
            notes: "Recorded (by text)",
          });
        } else {
          autoWait(selector, label, "visible");
          steps.push({
            id: newId("stp_"),
            type: "ui.click",
            name: `Click ${String(label).slice(0, 50)}`,
            config: { selector, text: "", timeout_ms: 30000 },
            enabled: true,
            notes: "Recorded (Chrome extension)",
          });
        }
      } else if (et === "click_by_text") {
        const text = (ev.text || ev.label || "").trim();
        if (!text) continue;
        let role = ev.role != null ? ev.role || "option" : "option";
        if (!role) role = "option";
        steps.push({
          id: newId("stp_"),
          type: "ui.click_by_text",
          name: `Click / select "${text.slice(0, 40)}"`,
          config: {
            text,
            exact: !!ev.exact,
            role,
            within: "",
            timeout_ms: 30000,
          },
          enabled: true,
          notes: "Recorded (by text — order-independent)",
        });
      } else if (et === "fill") {
        const selector = ev.selector || "";
        const value = ev.value || "";
        if (String(value).trim() === "") continue;
        const name = ev.name || selector;
        autoWait(selector, name, "attached");
        steps.push({
          id: newId("stp_"),
          type: "ui.fill",
          name: `Fill ${String(name).slice(0, 40)}`,
          config: {
            selector,
            value,
            clear: true,
            timeout_ms: 30000,
            name: String(name).startsWith("callback_") ? name : "",
          },
          enabled: true,
          notes: "Recorded (Chrome extension)",
        });
      } else if (et === "select_by_text") {
        const text = (ev.text || ev.label || "").trim();
        const selector = ev.selector || "";
        if (!text) continue;
        steps.push({
          id: newId("stp_"),
          type: "ui.select_by_text",
          name: `Select "${text.slice(0, 40)}"`,
          config: { text, selector, exact: !!ev.exact, timeout_ms: 30000 },
          enabled: true,
          notes: "Recorded (by text — order-independent)",
        });
      } else if (et === "select") {
        const selector = ev.selector || "";
        const label = (ev.label || ev.text || "").trim();
        const index = Number(ev.index || 0);
        const name = ev.name || selector;
        if (label) {
          steps.push({
            id: newId("stp_"),
            type: "ui.select_by_text",
            name: `Select "${label.slice(0, 40)}"`,
            config: { text: label, selector, exact: false, timeout_ms: 30000 },
            enabled: true,
            notes: "Recorded (by text — order-independent)",
          });
        } else {
          autoWait(selector, name, "attached");
          steps.push({
            id: newId("stp_"),
            type: "ui.select",
            name: `Select on ${String(name).slice(0, 40)}`,
            config: { selector, label, index, timeout_ms: 30000 },
            enabled: true,
            notes: "Recorded (Chrome extension)",
          });
        }
      } else if (et === "assert_text") {
        const text = (ev.text || "").trim();
        let selector = (ev.selector || "body").trim() || "body";
        if (!text) continue;
        if (selector.includes("nth-of-type") || (selector.match(/>/g) || []).length >= 3) {
          selector = "body";
        }
        const short = text.length <= 48 ? text : text.slice(0, 45) + "...";
        steps.push({
          id: newId("stp_"),
          type: "assert.text_contains",
          name: `Assert text "${short}"`,
          config: { selector, text, timeout_ms: 30000, ignore_case: true },
          enabled: true,
          notes: "Recorded from text selection",
        });
      } else if (et === "wait") {
        steps.push({
          id: newId("stp_"),
          type: "ui.wait",
          name: "Wait",
          config: { ms: Number(ev.ms || 500) },
          enabled: true,
          notes: "Recorded (Chrome extension)",
        });
      }
    }
    return steps;
  }

  root.FlowTestEventsToSteps = { eventsToSteps, newId };
})(typeof self !== "undefined" ? self : globalThis);
