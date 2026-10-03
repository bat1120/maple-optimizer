import { describe, expect, it } from "vitest";
import { formatMeso, formatPct, parsePrice, parsePotentials } from "./format.js";

describe("formatMeso", () => {
  it("억·만 단위로 표시", () => {
    expect(formatMeso(4_530_000_000)).toBe("45억 3000만");
    expect(formatMeso(100_000_000)).toBe("1억");
    expect(formatMeso(25_000_000)).toBe("2500만");
  });
});

describe("parsePrice", () => {
  it("억·만 표기를 메소로", () => {
    expect(parsePrice("45억 3000만")).toBe(4_530_000_000);
    expect(parsePrice("4.5억")).toBe(450_000_000);
  });
  it("숫자만 쓰면 메소", () => {
    expect(parsePrice("1,000,000")).toBe(1_000_000);
  });
  it("해석 불가면 null", () => {
    expect(parsePrice("")).toBeNull();
    expect(parsePrice("많이")).toBeNull();
  });
});

describe("formatPct / parsePotentials", () => {
  it("상승률은 소수 셋째 자리, 부호 포함", () => {
    expect(formatPct(1.04862)).toBe("+1.049%");
    expect(formatPct(-0.5)).toBe("-0.500%");
  });
  it("잠재 텍스트는 줄 단위, 빈 줄 제거", () => {
    expect(parsePotentials("INT +12%\n\n  LUK +9% \n")).toEqual(["INT +12%", "LUK +9%"]);
  });
});

describe("settingLabel", () => {
  it("유니온 프리셋이 있으면 함께 표시", async () => {
    const { settingLabel } = await import("./format.js");
    expect(settingLabel({ equipment: 2, hyper: 3, ability: 2, union: 3 })).toBe("장비 2 · 하이퍼 3 · 어빌 2 · 유니온 3");
    expect(settingLabel({ equipment: 1, hyper: 1, ability: 1 })).toBe("장비 1 · 하이퍼 1 · 어빌 1");
  });
});
