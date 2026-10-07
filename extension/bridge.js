// 메이플 장비 최적화 화면 ↔ 확장(2026-10-07). 페이지가 window.postMessage({ type: "MAPLEOPT_FILL", payload })를 보내면
// 백그라운드로 넘기고, 결과를 MAPLEOPT_FILL_ACK로 돌려준다. 페이지는 <html data-mapleopt-ext>로 확장이 깔렸는지 안다.
document.documentElement.setAttribute("data-mapleopt-ext", chrome.runtime.getManifest().version);
window.addEventListener("message", (e) => {
  if (e.source !== window || !e.data || e.data.type !== "MAPLEOPT_FILL") return;
  chrome.runtime.sendMessage({ type: "fill", payload: e.data.payload }, (res) => {
    window.postMessage({ type: "MAPLEOPT_FILL_ACK", ok: !!(res && res.ok), error: res && res.error }, window.location.origin);
  });
});
