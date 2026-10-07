// 확장 백그라운드 로직(크롬 API를 받아서 쓰므로 테스트에서 가짜 chrome으로 돌린다)
// 흐름: 우리 사이트에서 'fill' 메시지 → 그 캐릭터의 MapleScouter 정보 탭을 연다(최근 검색 캐릭터가 된다)
//       → 탭이 다 열리면 그 탭(MAIN world)에 run(payload)을 넣어 교체·채우기를 한다.
export const SCOUTER = "https://maplescouter.com/";
const INFO = "https://maplescouter.com/ko/info?name=";
const INPUT = "https://maplescouter.com/ko/input";

export function validPayload(p) {
  if (!p || typeof p !== "object" || !p.fields || typeof p.fields !== "object" || !p.rows) return false;
  if (p.name != null && (typeof p.name !== "string" || p.name.length > 40)) return false;
  return Object.values(p.fields).every((v) => typeof v === "number" && Number.isFinite(v));
}

export function createHandlers(chrome, run) {
  const key = (tabId) => `pending:${tabId}`;
  async function onMessage(msg, sender) {
    if (!msg || msg.type !== "fill") return { ok: false, error: "알 수 없는 요청" };
    if (!validPayload(msg.payload)) return { ok: false, error: "매물 정보가 올바르지 않아요" };
    const p = msg.payload;
    const tab = await chrome.tabs.create({
      url: p.name ? INFO + encodeURIComponent(p.name) : INPUT,
      ...(sender && sender.tab ? { index: sender.tab.index + 1 } : {}),
    });
    await chrome.storage.session.set({ [key(tab.id)]: p });
    return { ok: true, tabId: tab.id };
  }
  async function onUpdated(tabId, info, tab) {
    if (info.status !== "complete" || !tab || !String(tab.url || "").startsWith(SCOUTER)) return null;
    const k = key(tabId);
    const got = await chrome.storage.session.get(k);
    const p = got[k];
    if (!p) return null;
    await chrome.storage.session.remove(k); // 한 번만 — 같은 탭이 다시 열려도 또 채우지 않는다
    const [res] = await chrome.scripting.executeScript({ target: { tabId }, world: "MAIN", func: run, args: [p] });
    return res ? res.result : null;
  }
  return { onMessage, onUpdated };
}
