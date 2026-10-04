import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import RoadmapPanel from "./RoadmapPanel.jsx";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const tier = (grade, lines_good, target, delta_pct, probability) => ({ grade, lines_good, target, delta_pct, probability });
const body = {
  evaluation_setting: { equipment: 2, hyper: 3, ability: 2 }, note: "각 단계 = 흔한 줄",
  slots: [
    { slot: "상의", name: "도전자의 상의", starforce: 22, route: "경매장",
      current: { 잠재: ["INT +9%", "INT +6%"], 에디: ["INT +4%", "마력 +10"] },
      잠재: [tier("유니크", 2, ["INT +9%", "INT +6%"], 0, 8e-3), tier("유니크", 3, ["INT +9%", "INT +6%", "INT +6%"], 0.523, 1.06e-3)],
      에디: [tier("에픽", 2, ["마력 +11", "마력 +10"], 0.006, 1.6e-3), tier("유니크", 3, ["INT +6%", "마력 +11", "마력 +11"], 0.569, 6.3e-5)],
      next: { 잠재: 1, 에디: 1 } },
    { slot: "무기", name: "제네시스 카르타", starforce: 22, route: "큐브",
      current: { 잠재: ["보스 몬스터 데미지 +40%"], 에디: ["마력 +12%"] },
      잠재: [tier("레전드리", 3, ["마력 +12%", "마력 +9%", "마력 +9%"], 0.33, 1.8e-4)], 에디: [], next: { 잠재: 0, 에디: null } },
  ],
  value_note: "메소 재설정 평균 비용",
  value_ranking: [
    { slot: "엠블렘", kind: "에디", grade: "레전드리", lines_good: 2, target: ["마력 +12%", "마력 +9%"], delta_pct: 7.362,
      cube_cost: 25382690000, cube_cost_text: "253억 8269만", per_100m: 0.029 },
    { slot: "하의", kind: "잠재", grade: "레전드리", lines_good: 2, target: ["INT +12%", "INT +9%"], delta_pct: 0.523,
      cube_cost: 3087360000, cube_cost_text: "30억 8736만", per_100m: 0.0169 },
  ],
};

describe("roadmap panel", () => {
  it("전체 부위의 다음 단계를 잠재·에디로 보여주고, 큐브 경로를 표시한다", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => body });
    render(<RoadmapPanel name="내신부레테" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "전체 부위 로드맵" })); });
    expect(f.mock.calls[0][0]).toBe(`/api/character/${encodeURIComponent("내신부레테")}/roadmap?boss_defense=300`);
    const rows = within(screen.getByRole("table", { name: "부위별 다음 단계" })).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("상의");
    expect(rows[1]).toHaveTextContent("유니크 3줄 +0.523%");
    expect(rows[1]).toHaveTextContent("유니크 3줄 +0.569%");
    expect(rows[2]).toHaveTextContent("큐브");
    expect(rows[2]).toHaveTextContent("—");
  });

  it("부위를 펼치면 모든 단계가 보인다", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => body });
    render(<RoadmapPanel name="x" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "전체 부위 로드맵" })); });
    expect(screen.getAllByText(/에픽 2줄 · 마력 \+11 \/ 마력 \+10 · \+0\.006%/)).toHaveLength(1);
  });

  it("가격 대비 순위를 억당 순으로 보여준다", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => body });
    render(<RoadmapPanel name="x" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "전체 부위 로드맵" })); });
    const rows = within(screen.getByRole("table", { name: "가격 대비 순위" })).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("엠블렘 에디");
    expect(rows[1]).toHaveTextContent("253억 8269만");
    expect(rows[1]).toHaveTextContent("+0.029%");
    expect(rows[2]).toHaveTextContent("하의 잠재");
  });
});
