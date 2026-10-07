import { mapleoptRun } from "./generated/run.js";
import { createHandlers } from "./lib.js";

const h = createHandlers(chrome, mapleoptRun);
chrome.runtime.onMessage.addListener((msg, sender, send) => {
  h.onMessage(msg, sender).then(send, (e) => send({ ok: false, error: String(e && e.message || e) }));
  return true; // 비동기 응답
});
chrome.tabs.onUpdated.addListener((tabId, info, tab) => { h.onUpdated(tabId, info, tab).catch(() => {}); });
