// 서버 API 호출. 오류는 서버가 준 code·message를 그대로 담은 ApiError로 던진다.

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request(url, options) {
  let res;
  try {
    res = await fetch(url, options);
  } catch {
    throw new ApiError(0, "NETWORK", "서버에 연결할 수 없습니다.");
  }
  let body = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    throw new ApiError(res.status, body?.code ?? "UNKNOWN", body?.message ?? `요청 실패 (HTTP ${res.status})`);
  }
  return body;
}

const base = (name) => `/api/character/${encodeURIComponent(name)}`;

// 보스: 문자열이면 보스 목록 id(boss=), 숫자면 예전처럼 방어율(boss_defense=) — 2026-10-11
export const bossQuery = (boss) => (typeof boss === "string" ? { boss } : { boss_defense: String(boss) });
export const bossBody = (boss) => (typeof boss === "string" ? { boss } : { boss_defense: boss });
const bq = (boss) => new URLSearchParams(bossQuery(boss)).toString();

export const getBosses = () => request("/api/bosses");

export function getCharacter(name) {
  return request(base(name));
}

export function getSettings(name, bossDefense = 300) {
  return request(`${base(name)}/settings?${bq(bossDefense)}`);
}

export function getRecommend(name, bossDefense = 300, top = 5, cooldownMainPct = null) {
  const cd = cooldownMainPct ? `&cooldown_main_pct=${cooldownMainPct}` : "";
  return request(`${base(name)}/recommend?${bq(bossDefense)}&top=${top}${cd}`);
}

export function getRoadmap(name, bossDefense = 300, cooldownMainPct = null) {
  const cd = cooldownMainPct ? `&cooldown_main_pct=${cooldownMainPct}` : "";
  return request(`${base(name)}/roadmap?${bq(bossDefense)}${cd}`);
}

// events: { discount30, destroy_down30, guarantee_5_10_15, restore_discount20, protect, miracle, spareEok, fragmentMan, hexaSunday }
// 썬데이 스타포스 이벤트는 하나씩. 샤이닝 스타포스 = SHINING 둘(나무위키, 2026-10-11). 예전 shining: true도 그 둘로 받는다
export const SF_EVENTS = ["discount30", "destroy_down30", "guarantee_5_10_15", "restore_discount20"];
export const SHINING = ["discount30", "destroy_down30"];
export function getPaths(name, bossDefense = 300, events = {}) {
  const q = new URLSearchParams(bossQuery(bossDefense));
  const sf = [...SF_EVENTS.filter((k) => events[k] || (events.shining && SHINING.includes(k))), events.protect && "protect"].filter(Boolean).join(",");
  if (sf) q.set("sf", sf);
  if (events.miracle) q.set("miracle", "true");
  const spare = Number(events.spareEok);
  if (spare > 0) q.set("spare_price", String(Math.round(spare * 1e8)));
  const frag = Number(events.fragmentMan);  // 솔 에르다 조각 1개 값(만 메소)
  if (frag > 0) q.set("fragment_price", String(Math.round(frag * 1e4)));
  if (events.hexaSunday) q.set("hexa_sunday", "true");
  const bySlot = Object.entries(events.spareBySlot || {}).filter(([, v]) => v !== "" && Number(v) >= 0)
    .map(([slot, v]) => `${slot}:${Math.round(Number(v) * 1e8)}`);
  if (bySlot.length) q.set("spare_by_slot", bySlot.join(","));
  // 환생의 불꽃 1개 값(만 메소): 공식 메소 가격이 없어 넣은 불꽃만 추옵 경로에 들어간다(메소 재설정은 항상)
  const flames = Object.entries(events.flameMan || {}).filter(([, v]) => Number(v) > 0)
    .map(([k, v]) => `${k}:${Math.round(Number(v) * 1e4)}`);
  if (flames.length) q.set("flame_prices", flames.join(","));
  return request(`${base(name)}/paths?${q}`);
}

export const postMarketRefresh = (body) => post("/api/market/refresh", body);
export const getMarketStats = () => request("/api/market/stats");

export function postListings(name, body) {
  return request(`${base(name)}/listings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function post(url, body) {
  return request(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export const postStarforce = (body) => post("/api/enhance/starforce", body);
export const postCube = (body) => post("/api/enhance/cube", body);
export const postCraft = (body) => post("/api/craft/compare", body);
export const postOptimize = (name, body) => post(`${base(name)}/optimize`, body);

export const adminLogin = (password) => post("/api/admin/login", { password });

// 에이전트 SSE 스트림: 이벤트마다 onEvent를 부른다. 연결·인증 실패는 ApiError로 던진다.
export async function streamAgent(messages, onEvent) {
  const res = await fetch("/api/agent/chat", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages }),
  });
  if (!res.ok) {
    let body = null;
    try { body = await res.json(); } catch { body = null; }
    throw new ApiError(res.status, body?.code ?? "UNKNOWN", body?.message ?? `요청 실패 (HTTP ${res.status})`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let finished = false;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      if (!chunk.startsWith("data: ")) continue; // ': ping' 같은 연결 유지 주석
      const ev = JSON.parse(chunk.slice(6));
      if (ev.type === "done") finished = true;
      onEvent(ev);
    }
  }
  // done 없이 끝나면 중간에 끊긴 것 — 아무 말 없이 멈춰 보이지 않게(2026-10-12)
  if (!finished) throw new ApiError(0, "STREAM_CUT", "연결이 끊겼어요 — 서버가 계산하는 동안 응답이 끊겼을 수 있어요. 다시 물어봐 주세요.");
}

export const postVision = (body) => post("/api/vision/listings", body);
export const postVisionEvaluate = (body) => post("/api/vision/evaluate", body);
export const postVisionCorrect = (body) => post("/api/vision/correct", body);
export const getVisionDataset = () => request("/api/vision/dataset");
export const postVisionScore = (body) => post("/api/vision/score", body);
export const postVisionScoreReset = () => post("/api/vision/score/reset", {});

// 목표 보스 배율 로드맵: { current, target, fragmentMan }
export function getTargetRoadmap(name, bossDefense = 300, { current, target, fragmentMan } = {}) {
  const q = new URLSearchParams({ ...bossQuery(bossDefense), current_ratio: String(current), target_ratio: String(target) });
  const frag = Number(fragmentMan);
  if (frag > 0) q.set("fragment_price", String(Math.round(frag * 1e4)));
  return request(`${base(name)}/target-roadmap?${q}`);
}
