import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getCharacter, postListings } from "./api.js";

afterEach(() => vi.restoreAllMocks());

function mockFetch(status, body) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: status < 400, status, json: async () => body,
  });
}

describe("api", () => {
  it("닉네임을 URL 인코딩해 조회", async () => {
    const f = mockFetch(200, { character_class: "레테" });
    const r = await getCharacter("내신부레테");
    expect(r.character_class).toBe("레테");
    expect(f.mock.calls[0][0]).toBe(`/api/character/${encodeURIComponent("내신부레테")}`);
  });
  it("오류 응답은 code·message를 가진 ApiError", async () => {
    mockFetch(404, { code: "NOT_FOUND", message: "캐릭터를 찾을 수 없습니다." });
    await expect(getCharacter("없음")).rejects.toMatchObject({ code: "NOT_FOUND", status: 404 });
    await expect(getCharacter("없음")).rejects.toBeInstanceOf(ApiError);
  });
  it("매물은 POST JSON으로 보낸다", async () => {
    const f = mockFetch(200, { ranking: [] });
    await postListings("x", { listings: [] });
    expect(f.mock.calls[0][1].method).toBe("POST");
    expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({ listings: [] });
  });
});

describe("streamAgent(2026-10-12: 끊겨도 아무 말 없이 멈추던 것)", () => {
  const streamOf = (text) => ({ ok: true, status: 200, body: new Response(text).body });
  it("ping 주석은 건너뛰고, done까지 오면 정상으로 끝난다", async () => {
    const { streamAgent } = await import("./api.js");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(streamOf(': ping\n\ndata: {"type":"text","text":"답"}\n\ndata: {"type":"done","unverified_numbers":[]}\n\n'));
    const evs = [];
    await streamAgent([], (e) => evs.push(e.type));
    expect(evs).toEqual(["text", "done"]);
  });
  it("done 없이 연결이 끝나면 끊겼다고 알린다", async () => {
    const { streamAgent } = await import("./api.js");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(streamOf('data: {"type":"tool_call","name":"recommend_searches","input":{}}\n\n'));
    await expect(streamAgent([], () => {})).rejects.toThrow(/연결이 끊겼/);
  });
});
