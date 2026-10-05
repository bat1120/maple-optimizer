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

export function getCharacter(name) {
  return request(base(name));
}

export function getSettings(name, bossDefense = 300) {
  return request(`${base(name)}/settings?boss_defense=${bossDefense}`);
}

export function getRecommend(name, bossDefense = 300, top = 5, cooldownMainPct = null) {
  const cd = cooldownMainPct ? `&cooldown_main_pct=${cooldownMainPct}` : "";
  return request(`${base(name)}/recommend?boss_defense=${bossDefense}&top=${top}${cd}`);
}

export function getRoadmap(name, bossDefense = 300, cooldownMainPct = null) {
  const cd = cooldownMainPct ? `&cooldown_main_pct=${cooldownMainPct}` : "";
  return request(`${base(name)}/roadmap?boss_defense=${bossDefense}${cd}`);
}

export function getPaths(name, bossDefense = 300) {
  return request(`${base(name)}/paths?boss_defense=${bossDefense}`);
}

export const postMarketRefresh = (body) => post("/api/market/refresh", body);

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
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      if (chunk.startsWith("data: ")) onEvent(JSON.parse(chunk.slice(6)));
    }
  }
}

export const postVision = (body) => post("/api/vision/listings", body);
export const postVisionEvaluate = (body) => post("/api/vision/evaluate", body);
export const postVisionCorrect = (body) => post("/api/vision/correct", body);
export const getVisionDataset = () => request("/api/vision/dataset");
export const postVisionScore = (body) => post("/api/vision/score", body);
