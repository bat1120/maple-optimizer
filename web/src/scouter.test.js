import { afterEach, describe, expect, it } from "vitest";
import { FILL_SOURCE, PREFIX, bookmarkletHref, clipboardText, runFill } from "./scouter.js";

// MapleScouter 입력 화면 흉내(2026-10-07 실제 구조): <span>라벨</span> → 세 단계 위 div 안에 input
function row(label, values) {
  return `<div class="flex w-full"><div><div><span class="text-sm">${label}</span></div></div>${values.map((v) => `<input type="text" value="${v}">`).join("")}</div>`;
}
function page() {
  document.body.innerHTML = `<main>
    ${row("INT", [5503, 423, 27310])}${row("LUK", [2633, 132, 660])}${row("마력", [3074, 63, 0])}
    ${row("데미지", [91])}${row("최종 데미지", [188.93])}${row("보스 데미지", [438])}${row("방어율 무시", [95.2782])}
    ${row("크리티컬 확률", [103])}${row("마력", [5010])}${row("크리 데미지", [87])}${row("초", [2])}
  </main>`;
}
const vals = () => [...document.querySelectorAll("input")].map((i) => i.value);
afterEach(() => { document.body.innerHTML = ""; });

const PAYLOAD = {
  v: 1, to: "에테르넬 메이지글러브", from: "도전자의 장갑", slot: "장갑",
  rows: { main: ["INT"], sub: ["LUK"], attack: "마력" },
  fields: { "INT|기본": 30, "INT|%": 9, "INT|% 미적용": 0, "LUK|기본": 10, "LUK|%": 0, "LUK|% 미적용": 0,
            "마력|기본": 12, "마력|%": 0, "데미지": 0, "보스 데미지": 30, "최종 데미지": 0, "크리티컬 확률": 0, "크리 데미지": 8, "초": 0 },
  ied_add: [40], ied_remove: [],
};

describe("scouter fill (MapleScouter 입력칸 채우기)", () => {
  it("칸 이름으로 찾아 변화량을 더한다(두 번째 '마력' 한 칸짜리는 건드리지 않는다)", () => {
    page();
    const r = runFill(document, PAYLOAD);
    const v = vals();
    expect(v.slice(0, 3)).toEqual(["5533", "432", "27310"]);
    expect(v[3]).toBe("2643");
    expect(v[6]).toBe("3086");
    expect(v[10]).toBe("188.93");                  // 최종 데미지 변화 0 → 그대로
    expect(v[11]).toBe("468");                     // 보스 데미지 438 + 30
    expect(v[14]).toBe("5010");                    // 아래쪽 '마력'(한 칸)은 그대로
    expect(v[15]).toBe("95");                      // 크리 데미지 87 + 8
    expect(r.changed).toBeGreaterThanOrEqual(6);
  });
  it("방무는 곱연산: 100 − (100−기존)×(1−더한 줄)", () => {
    page();
    runFill(document, PAYLOAD);
    expect(Number(vals()[12])).toBeCloseTo(100 - (100 - 95.2782) * 0.6, 4);
  });
  it("칸을 못 찾으면 그 칸만 건너뛰고 알려 준다", () => {
    document.body.innerHTML = `<main>${row("INT", [1, 2, 3])}</main>`;
    const r = runFill(document, PAYLOAD);
    expect(vals()).toEqual(["31", "11", "3"]);
    expect(r.missing).toContain("보스 데미지");
  });
  it("복사 글: 사람이 읽는 요약 + 북마클릿이 읽는 한 줄(PREFIX JSON)", () => {
    const t = clipboardText(PAYLOAD, { price: 10_000_000_000, delta_pct: 0.84, per_100m: 0.084 });
    expect(t).toContain("장갑: 도전자의 장갑 → 에테르넬 메이지글러브");
    expect(t).toContain("INT +30");
    const line = t.split("\n").find((l) => l.startsWith(PREFIX));
    expect(JSON.parse(line.slice(PREFIX.length))).toEqual(PAYLOAD);
  });
  it("북마클릿 주소는 같은 채우기 코드를 담는다", () => {
    const href = bookmarkletHref();
    expect(href.startsWith("javascript:")).toBe(true);
    expect(decodeURIComponent(href)).toContain(FILL_SOURCE.slice(0, 40));
  });
});
