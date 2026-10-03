// 매물 목록을 브라우저에 보관한다(스펙 §7). 저장소 접근이 막혀도 앱은 메모리로 동작한다.
const KEY = "maple-optimizer.listings.v1";

export function loadListings() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveListings(listings) {
  try {
    localStorage.setItem(KEY, JSON.stringify(listings));
  } catch {
    // 무시: 사생활 보호 모드 등
  }
}
