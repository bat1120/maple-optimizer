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
