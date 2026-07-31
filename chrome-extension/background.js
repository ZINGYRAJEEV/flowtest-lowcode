/* global FlowTestEventsToSteps */
importScripts("events_to_steps.js");

const DEFAULT_STATE = {
  recording: false,
  events: [],
  startUrl: "",
  replaceBaseUrl: "",
  result: null,
  tabId: null,
};

async function getState() {
  const data = await chrome.storage.session.get("flowtest");
  return { ...DEFAULT_STATE, ...(data.flowtest || {}) };
}

async function setState(patch) {
  const cur = await getState();
  const next = { ...cur, ...patch };
  await chrome.storage.session.set({ flowtest: next });
  return next;
}

async function broadcastRecording(recording) {
  const tabs = await chrome.tabs.query({});
  await Promise.all(
    tabs.map(async (tab) => {
      if (!tab.id || !tab.url || !/^https?:/i.test(tab.url)) return;
      try {
        await chrome.tabs.sendMessage(tab.id, { type: "flowtest:setRecording", recording });
      } catch (_) {
        /* content script may not be ready */
      }
    })
  );
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    if (!msg || !msg.type) return;

    if (msg.type === "flowtest:getState") {
      sendResponse(await getState());
      return;
    }

    if (msg.type === "flowtest:event") {
      const state = await getState();
      if (!state.recording) {
        sendResponse({ ok: false });
        return;
      }
      const events = [...(state.events || []), msg.payload];
      await setState({ events });
      sendResponse({ ok: true, count: events.length });
      return;
    }

    if (msg.type === "flowtest:start") {
      const startUrl = (msg.startUrl || "").trim();
      const replaceBaseUrl = (msg.replaceBaseUrl || "").trim();
      let tabId = msg.tabId;
      if (!tabId) {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        tabId = tab && tab.id;
      }
      await setState({
        recording: true,
        events: [],
        startUrl,
        replaceBaseUrl,
        result: null,
        tabId,
      });
      await broadcastRecording(true);

      if (startUrl && tabId) {
        let url = startUrl;
        if (!/^https?:\/\//i.test(url)) url = "https://" + url;
        await chrome.tabs.update(tabId, { url });
        // Seed goto once navigation settles (content also emits on load)
        setTimeout(async () => {
          const st = await getState();
          if (!st.recording) return;
          if (!(st.events || []).some((e) => e.type === "goto")) {
            await setState({
              events: [{ type: "goto", url, ts: Date.now() }, ...(st.events || [])],
            });
          }
        }, 1500);
      } else if (tabId) {
        try {
          const tab = await chrome.tabs.get(tabId);
          if (tab.url && /^https?:/i.test(tab.url)) {
            await setState({
              events: [{ type: "goto", url: tab.url, ts: Date.now() }],
            });
          }
        } catch (_) {}
      }

      sendResponse({ ok: true });
      return;
    }

    if (msg.type === "flowtest:stop" || msg.type === "flowtest:finish") {
      const state = await getState();
      const events = state.events || [];
      const steps = FlowTestEventsToSteps.eventsToSteps(events, state.replaceBaseUrl || "");
      const result = {
        source: "chrome-extension",
        version: 1,
        start_url: state.startUrl || (events.find((e) => e.type === "goto") || {}).url || "",
        events,
        steps,
        count: steps.length,
        created_at: new Date().toISOString(),
      };
      await setState({ recording: false, result, events });
      await broadcastRecording(false);
      sendResponse({ ok: true, result });
      return;
    }

    if (msg.type === "flowtest:clearResult") {
      await setState({ result: null, events: [] });
      sendResponse({ ok: true });
      return;
    }

    if (msg.type === "flowtest:download") {
      const state = await getState();
      const result = state.result;
      if (!result) {
        sendResponse({ ok: false, error: "No recording to download" });
        return;
      }
      // Service worker: use data URL (no Blob URL in SW)
      const text = JSON.stringify(result, null, 2);
      const url =
        "data:application/json;base64," +
        btoa(unescape(encodeURIComponent(text)));
      const filename = `flowtest-recording-${Date.now()}.json`;
      await chrome.downloads.download({ url, filename, saveAs: true });
      sendResponse({ ok: true, filename });
      return;
    }
  })();
  return true;
});

chrome.tabs.onUpdated.addListener(async (tabId, info, tab) => {
  const state = await getState();
  if (!state.recording || info.status !== "complete") return;
  if (!tab.url || !/^https?:/i.test(tab.url)) return;
  try {
    await chrome.tabs.sendMessage(tabId, { type: "flowtest:setRecording", recording: true });
  } catch (_) {}
  // Record navigations
  const events = state.events || [];
  const lastGoto = [...events].reverse().find((e) => e.type === "goto");
  if (!lastGoto || lastGoto.url !== tab.url) {
    await setState({
      events: [...events, { type: "goto", url: tab.url, ts: Date.now() }],
    });
  }
});
