const $ = (id) => document.getElementById(id);

async function refresh() {
  const state = await chrome.runtime.sendMessage({ type: "flowtest:getState" });
  const recording = !!(state && state.recording);
  $("btnStart").disabled = recording;
  $("btnStop").disabled = !recording;
  if (recording) {
    $("status").textContent = `Recording… ${(state.events || []).length} event(s). Interact in the page, then Finish.`;
    $("resultBox").classList.add("hidden");
  } else if (state && state.result) {
    const n = state.result.count || (state.result.steps || []).length || 0;
    $("status").textContent = "Recording finished.";
    $("resultSummary").textContent = `${n} step(s) ready to import into FlowTest.`;
    $("resultBox").classList.remove("hidden");
  } else {
    $("status").textContent = "Idle — open the site tab, then Start.";
    $("resultBox").classList.add("hidden");
  }
}

$("btnStart").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  await chrome.runtime.sendMessage({
    type: "flowtest:start",
    startUrl: $("startUrl").value.trim(),
    replaceBaseUrl: $("baseUrl").value.trim(),
    tabId: tab && tab.id,
  });
  await refresh();
});

$("btnStop").addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ type: "flowtest:finish" });
  await refresh();
});

$("btnCopy").addEventListener("click", async () => {
  const state = await chrome.runtime.sendMessage({ type: "flowtest:getState" });
  if (!state || !state.result) return;
  const text = JSON.stringify(state.result, null, 2);
  await navigator.clipboard.writeText(text);
  $("status").textContent = "JSON copied — paste it in FlowTest → Import Chrome recording.";
});

$("btnDownload").addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ type: "flowtest:download" });
});

$("btnOpen").addEventListener("click", async () => {
  const url = ($("flowtestUrl").value || "https://lowcodetestautomation.streamlit.app/").trim();
  await chrome.tabs.create({ url });
});

chrome.storage.local.get("flowtestPrefs", (data) => {
  const prefs = data.flowtestPrefs || {};
  if (prefs.startUrl) $("startUrl").value = prefs.startUrl;
  if (prefs.baseUrl) $("baseUrl").value = prefs.baseUrl;
  if (prefs.flowtestUrl) $("flowtestUrl").value = prefs.flowtestUrl;
});

["startUrl", "baseUrl", "flowtestUrl"].forEach((id) => {
  $(id).addEventListener("change", () => {
    chrome.storage.local.set({
      flowtestPrefs: {
        startUrl: $("startUrl").value,
        baseUrl: $("baseUrl").value,
        flowtestUrl: $("flowtestUrl").value,
      },
    });
  });
});

refresh();
setInterval(refresh, 1000);
