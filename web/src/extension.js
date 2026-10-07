// 크롬 확장 '메이플 장비 최적화 — 환산 채우기'(extension/)와 주고받기. 확장의 bridge.js가 <html data-mapleopt-ext>를 붙인다.
export function hasExtension() {
  return typeof document !== "undefined" && document.documentElement.hasAttribute("data-mapleopt-ext");
}

// 매물 변화량을 확장으로 보낸다 → 확장이 MapleScouter 탭을 열어 내 캐릭터로 교체하고 채운다
export function sendToExtension(payload, timeoutMs = 3000) {
  return new Promise((resolve) => {
    const done = (v) => { window.removeEventListener("message", onAck); clearTimeout(timer); resolve(v); };
    const onAck = (e) => {
      if (e.source !== window || !e.data || e.data.type !== "MAPLEOPT_FILL_ACK") return;
      done(e.data.ok ? { ok: true } : { ok: false, error: e.data.error || "확장 프로그램이 거절했어요" });
    };
    const timer = setTimeout(() => done({ ok: false, error: "확장 프로그램이 응답하지 않아요 — 크롬 확장 관리에서 켜져 있는지 확인해 주세요" }), timeoutMs);
    window.addEventListener("message", onAck);
    window.postMessage({ type: "MAPLEOPT_FILL", payload }, window.location.origin);
  });
}
