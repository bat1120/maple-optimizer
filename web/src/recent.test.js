import { afterEach, describe, expect, it } from "vitest";
import { addRecent, loadRecent } from "./recent.js";

afterEach(() => localStorage.clear());

describe("recent searches", () => {
  it("최근 것이 앞, 중복은 한 번, 최대 8개", () => {
    for (const n of ["a", "b", "c", "a"]) addRecent(n);
    expect(loadRecent()).toEqual(["a", "c", "b"]);
    for (let i = 0; i < 10; i++) addRecent(`n${i}`);
    expect(loadRecent()).toHaveLength(8);
  });
  it("저장소가 깨져 있어도 빈 목록", () => {
    localStorage.setItem("maple-optimizer:recent", "{broken");
    expect(loadRecent()).toEqual([]);
  });
});
