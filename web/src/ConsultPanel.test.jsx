import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import ConsultPanel from "./ConsultPanel.jsx";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

// 실제 서버 응답 모양(2026-11-26, /api/character/{name}/consult)
const build = (starforce, delta, over = {}) => ({
  starforce, delta_pct: delta,
  armor: { label: "에테르넬 7", delta_pct: 22.67 }, accessory: { label: "칠흑 6 · 보스 장신구 2 · 광휘 3", delta_pct: 49.51 },
  pieces: [],
  buy: [{ slot: "귀고리", name: "커맨더 포스 이어링", starforce, group: "장신구", set: "칠흑의 보스 세트", level: 200 },
        { slot: "반지1", name: "근원의 속삭임", starforce, group: "장신구", set: "광휘의 보스 세트", level: 250 }],
  raise: [{ slot: "모자", name: "에테르넬 메이지햇", from_star: 18, starforce, cost: 56362620000, cost_text: "563억 6262만", destroys: 1.2, group: "방어구" }],
  raise_cost: 56362620000, raise_cost_text: "563억 6262만",
  set_change: [{ set: "칠흑의 보스 세트", before: 0, after: 6, lost: [], gained: ["공격력 +10, 마력 +10, 보스 몬스터 데미지 +10%"] },
               { set: "여명의 보스 세트", before: 3, after: 0, lost: ["올스탯 +10, 최대 HP +250, 공격력 +10, 마력 +10"], gained: [] }],
  ...over,
});
const DATA = { evaluation_setting: { equipment: 2 }, boss: { defense: 300 }, note: "세팅 전체를 한 번에 낀 보스 실딜이에요.",
               builds: [build(17, 13.94, { raise: [], raise_cost: 0, raise_cost_text: null }), build(18, 20.07), build(21, 60.77), build(22, 77.24)] };
const ok = (body) => ({ ok: true, status: 200, json: async () => body });

describe("목표 세팅 컨설팅", () => {
  it("성마다 세팅 전체의 실딜을 보여 주고, 기본은 22성 — 살 템·강화할 템·세트 효과 변화가 나온다", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(DATA));
    render(<ConsultPanel name="내신부레테" defense={300} />);
    const tabs = await screen.findByRole("tablist", { name: "목표 스타포스" });
    expect(String(f.mock.calls[0][0])).toContain("/consult?boss_defense=300");
    expect(within(tabs).getAllByRole("tab").map((t) => t.textContent)).toEqual(["17성 +13.9%", "18성 +20.1%", "21성 +60.8%", "22성 +77.2%"]);
    expect(within(tabs).getByRole("tab", { name: /22성/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("22성 세팅으로 갈아타면 보스 실딜")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "살 템" })).toBeNull();           // 처음엔 결론만 — 목록은 눌러서 편다
    fireEvent.click(screen.getByRole("button", { name: "살 템 2개 · 강화할 템 1개 보기" }));
    const buy = screen.getByRole("list", { name: "살 템" });
    expect(within(buy).getAllByRole("listitem")).toHaveLength(2);
    expect(buy).toHaveTextContent("커맨더 포스 이어링 22성 · 칠흑");
    expect(screen.getByRole("list", { name: "강화할 템" })).toHaveTextContent("에테르넬 메이지햇 18→22성563억 6262만");
    const sets = screen.getByRole("list", { name: "세트 효과 변화" });
    expect(sets).toHaveTextContent("칠흑의 보스 세트 0→6개 · 새로 켜지는 효과: 공격력 +10, 마력 +10, 보스 몬스터 데미지 +10%");
    expect(sets).toHaveTextContent("여명의 보스 세트 3→0개 · 사라지는 효과: 올스탯 +10, 최대 HP +250, 공격력 +10, 마력 +10");
  });

  it("시세를 넣으면 필요한 메소를 합치고, 다 넣으면 1억 메소당 효율까지 계산한다", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(DATA));
    render(<ConsultPanel name="내신부레테" defense={300} />);
    await screen.findByRole("tablist", { name: "목표 스타포스" });
    fireEvent.click(screen.getByRole("button", { name: /보기$/ }));
    const total = () => document.querySelector(".consult-total").textContent;
    expect(total()).toContain("필요한 메소 563억 6262만");                       // 강화 비용만(시세 없음)
    expect(total()).toContain("시세를 안 넣은 템 2개");
    fireEvent.change(screen.getByLabelText("커맨더 포스 이어링 시세"), { target: { value: "30억" } });
    expect(total()).toContain("필요한 메소 593억 6262만");
    expect(total()).toContain("시세를 안 넣은 템 1개");
    fireEvent.change(screen.getByLabelText("근원의 속삭임 시세"), { target: { value: "406억 3738만" } });
    expect(total()).toContain("필요한 메소 1000억");
    expect(total()).toContain("1억 메소당 +0.077%");                             // 77.24% ÷ 1000억
  });

  it("성을 바꾸면 그 성의 세팅으로 바뀐다(17성은 강화할 템이 없다)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(DATA));
    render(<ConsultPanel name="내신부레테" defense={300} />);
    fireEvent.click(await screen.findByRole("tab", { name: /17성/ }));
    expect(screen.getByText("17성 세팅으로 갈아타면 보스 실딜")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "살 템 2개 · 강화할 템 0개 보기" }));
    expect(screen.queryByRole("list", { name: "강화할 템" })).toBeNull();
    expect(document.querySelector(".consult-total").textContent).toContain("시세를 넣으면");
  });
});
