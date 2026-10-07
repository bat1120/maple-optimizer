import { describe, expect, it } from "vitest";
import { hashFor, parseHash } from "./router.js";

describe("hash router", () => {
  it("캐릭터 주소: 한글 닉네임과 탭", () => {
    expect(parseHash("#/c/%EB%A0%88%ED%85%8C?tab=upgrade")).toEqual({ page: "character", name: "레테", tab: "upgrade" });
  });
  it("탭이 없거나 잘못되면 summary", () => {
    expect(parseHash("#/c/abc").tab).toBe("summary");
    expect(parseHash("#/c/abc?tab=hack").tab).toBe("summary");
  });
  it("계산기·관리자·첫 화면, 모르는 주소는 첫 화면", () => {
    expect(parseHash("#/calc").page).toBe("calc");
    expect(parseHash("#/admin").page).toBe("admin");
    expect(parseHash("#/scouter").page).toBe("scouter");
    expect(parseHash("").page).toBe("home");
    expect(parseHash("#/what").page).toBe("home");
    expect(parseHash("#/c/").page).toBe("home");
  });
  it("hashFor는 parseHash와 왕복한다(공백·특수문자 닉네임 포함)", () => {
    for (const r of [{ page: "character", name: "내 신부 레테", tab: "calc" }, { page: "calc" }, { page: "home" }, { page: "admin" }]) {
      const back = parseHash(hashFor(r));
      expect(back.page).toBe(r.page);
      if (r.name) expect(back).toEqual(r);
    }
  });
});
