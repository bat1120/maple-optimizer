// 최근 검색한 캐릭터(이 브라우저에만). 서버로 보내지 않는다.
const KEY = "maple-optimizer:recent";
const MAX = 8;

export function loadRecent() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function addRecent(name) {
  const next = [name, ...loadRecent().filter((n) => n !== name)].slice(0, MAX);
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* 저장 못 해도 검색은 된다 */ }
  return next;
}
