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

export function postListings(name, body) {
  return request(`${base(name)}/listings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
