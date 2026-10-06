import { afterEach, describe, expect, it } from "vitest";
import { applyTheme, loadTheme, nextTheme, saveTheme } from "./theme.js";

afterEach(() => { localStorage.clear(); document.documentElement.removeAttribute("data-theme"); });

describe("theme", () => {
  it("라이트 → 다크 → 시스템 순으로 바뀐다", () => {
    expect(nextTheme("light")).toBe("dark");
    expect(nextTheme("dark")).toBe("system");
    expect(nextTheme("system")).toBe("light");
  });
  it("저장한 값을 불러오고, 없으면 시스템", () => {
    expect(loadTheme()).toBe("system");
    saveTheme("dark");
    expect(loadTheme()).toBe("dark");
  });
  it("라이트·다크는 data-theme로, 시스템은 속성을 지운다(CSS가 prefers-color-scheme을 따른다)", () => {
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    applyTheme("system");
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });
});
