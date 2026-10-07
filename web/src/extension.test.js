import { readFileSync } from "node:fs";
import { resolve } from "node:path"; // vitest는 web/ 에서 돈다
import { afterEach, describe, expect, it, vi } from "vitest";
import { createHandlers, validPayload } from "../../extension/lib.js";
import { extensionRunModule, sampleScouter } from "./scouter.js";
import { hasExtension, sendToExtension } from "./extension.js";

const ME = sampleScouter({ name: "내신부레테", job: "레테", level: 288 });

function fakeChrome() {
  const store = {};
  return {
    store,
    tabs: { create: vi.fn(async ({ url }) => ({ id: 7, url })) },
    storage: { session: {
      set: vi.fn(async (o) => Object.assign(store, o)),
      get: vi.fn(async (k) => (k in store ? { [k]: store[k] } : {})),
      remove: vi.fn(async (k) => { delete store[k]; }),
    } },
    scripting: { executeScript: vi.fn(async () => [{ result: { s: { switched: true }, r: { changed: 2 } } }]) },
  };
}

describe("extension background (확장 백그라운드)", () => {
  it("fill 요청 → 그 캐릭터의 MapleScouter 정보 탭을 열고, 다 열리면 그 탭에 한 번만 실행한다", async () => {
    const chrome = fakeChrome();
    const run = () => {};
    const h = createHandlers(chrome, run);
    expect(await h.onMessage({ type: "fill", payload: ME }, { tab: { index: 2 } })).toEqual({ ok: true, tabId: 7 });
    expect(chrome.tabs.create).toHaveBeenCalledWith({ url: "https://maplescouter.com/ko/info?name=%EB%82%B4%EC%8B%A0%EB%B6%80%EB%A0%88%ED%85%8C", index: 3 });
    expect(await h.onUpdated(7, { status: "loading" }, { url: "https://maplescouter.com/ko/info" })).toBeNull();
    const out = await h.onUpdated(7, { status: "complete" }, { url: "https://maplescouter.com/ko/info?name=x" });
    expect(out.r.changed).toBe(2);
    expect(chrome.scripting.executeScript).toHaveBeenCalledWith({ target: { tabId: 7 }, world: "MAIN", func: run, args: [ME] });
    expect(await h.onUpdated(7, { status: "complete" }, { url: "https://maplescouter.com/ko/input" })).toBeNull(); // 두 번째는 안 한다
    expect(chrome.scripting.executeScript).toHaveBeenCalledTimes(1);
  });
  it("다른 탭·다른 사이트는 건드리지 않는다", async () => {
    const chrome = fakeChrome();
    const h = createHandlers(chrome, () => {});
    await h.onMessage({ type: "fill", payload: ME }, {});
    expect(await h.onUpdated(8, { status: "complete" }, { url: "https://maplescouter.com/ko/info" })).toBeNull();
    expect(await h.onUpdated(7, { status: "complete" }, { url: "https://example.com/" })).toBeNull();
    expect(chrome.scripting.executeScript).not.toHaveBeenCalled();
  });
  it("이상한 데이터는 탭을 열지 않고 거절한다", async () => {
    const chrome = fakeChrome();
    const h = createHandlers(chrome, () => {});
    expect((await h.onMessage({ type: "fill", payload: { ...ME, fields: { "보스 데미지": "1; alert(1)" } } }, {})).ok).toBe(false);
    expect((await h.onMessage({ type: "other" }, {})).ok).toBe(false);
    expect(chrome.tabs.create).not.toHaveBeenCalled();
    expect(validPayload(ME)).toBe(true);
  });
  it("extension/generated/run.js 가 scouter.js와 같다(바꿨으면 web에서 npm run ext)", () => {
    const file = readFileSync(resolve("../extension/generated/run.js"), "utf8").replace(/\r\n/g, "\n");
    expect(file).toBe(extensionRunModule());
  });
  it("manifest: MapleScouter에만 스크립트 권한, 우리 사이트에만 브리지", () => {
    const m = JSON.parse(readFileSync(resolve("../extension/manifest.json"), "utf8"));
    expect(m.manifest_version).toBe(3);
    expect(m.host_permissions).toEqual(["https://maplescouter.com/*"]);
    expect(m.content_scripts[0].matches).toContain("https://maple-optimizer.onrender.com/*");
  });
});

describe("site ↔ extension (사이트 쪽)", () => {
  afterEach(() => { document.documentElement.removeAttribute("data-mapleopt-ext"); });
  it("브리지가 붙인 표시로 확장 설치 여부를 안다", () => {
    expect(hasExtension()).toBe(false);
    document.documentElement.setAttribute("data-mapleopt-ext", "0.1.0");
    expect(hasExtension()).toBe(true);
  });
  it("sendToExtension: 메시지를 보내고 ACK를 기다린다", async () => {
    const posted = [];
    const orig = window.postMessage.bind(window);
    window.postMessage = (data) => { posted.push(data); if (data.type === "MAPLEOPT_FILL") setTimeout(() => window.dispatchEvent(new MessageEvent("message", { source: window, data: { type: "MAPLEOPT_FILL_ACK", ok: true } })), 0); };
    try {
      expect(await sendToExtension(ME)).toEqual({ ok: true });
      expect(posted[0]).toEqual({ type: "MAPLEOPT_FILL", payload: ME });
    } finally { window.postMessage = orig; }
  });
  it("확장이 답하지 않으면 시간 초과로 실패를 돌려준다", async () => {
    const orig = window.postMessage.bind(window);
    window.postMessage = () => {};
    try { expect((await sendToExtension(ME, 20)).ok).toBe(false); } finally { window.postMessage = orig; }
  });
});
