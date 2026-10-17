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
      cube_cost: 25382690000, cube_cost_text: "253억 8269만", per_100m: 0.029,
      market: { count: 3, median: 18000000000, min: 15000000000, last_seen: 0, per_100m: 0.0409 } },
    { slot: "하의", kind: "잠재", grade: "레전드리", lines_good: 2, target: ["INT +12%", "INT +9%"], delta_pct: 0.523,
      cube_cost: 3087360000, cube_cost_text: "30억 8736만", per_100m: 0.0169 },
  ],
};

// 순위 카드(목록의 직계 항목)만 센다 — 카드 안의 경매장 조건 칩 목록은 빼고(2026-10-11)
const cards = () => [...screen.getByRole("list", { name: "가격 대비 순위" }).children];

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
    const rows = cards();
    expect(rows[0]).toHaveTextContent("엠블렘 에디");
    expect(rows[0]).toHaveTextContent("253억 8269만");
    expect(rows[0]).toHaveTextContent("+0.029%");
    expect(rows[1]).toHaveTextContent("하의 잠재");
  });

  it("관측 시세가 있으면 큐브 비용 옆에 시세와 시세 기준 억당을 보여준다", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => body });
    render(<RoadmapPanel name="x" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "전체 부위 로드맵" })); });
    const rows = cards();
    expect(rows[0]).toHaveTextContent("시세 180억 (3건, 최저 150억) · 억당 +0.041%");
    expect(rows[1]).not.toHaveTextContent("시세 없음");   // 2026-10-11 심사: 시세가 없으면 줄을 비운다(뜻이 모호했다)
  });

  it("가격 대비 순위는 처음 7개만(1위 전체 폭 + 2단 3줄) 보이고 [더 보기]로 나머지를 펼친다, 부위별 표는 접어 둔다", async () => {
    const many = Array.from({ length: 11 }, (_, i) => ({ ...body.value_ranking[1], slot: `부위${i + 1}`, per_100m: 0.02 - i * 0.001 }));
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => ({ ...body, value_ranking: many }) });
    render(<RoadmapPanel name="내신부레테" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "전체 부위 로드맵" })); });
    const list = () => cards();
    expect(list()).toHaveLength(7);
    fireEvent.click(screen.getByRole("button", { name: "순위 4개 더 보기" }));
    expect(list()).toHaveLength(11);
    expect(screen.getByText("부위별 다음 단계·모든 단계 보기").closest("details")).not.toHaveAttribute("open");
  });

  // 2026-10-17 사용자: 게임 경매장은 드롭다운이라 복사할 곳이 없다 → 칩대로 찾은 뒤 화면 공유로 평가하는 버튼
  it("순위 카드 [이 조건으로 찾은 매물 평가하기] — 그 카드의 조건을 onEvaluate로 넘긴다", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => body });
    const onEvaluate = vi.fn();
    render(<RoadmapPanel name="내신부레테" defense={300} onEvaluate={onEvaluate} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "전체 부위 로드맵" })); });
    const first = cards()[0];
    expect(within(first).queryByRole("button", { name: "경매장 검색 조건 복사" })).toBeNull();
    fireEvent.click(within(first).getByRole("button", { name: "이 조건으로 찾은 매물 평가하기" }));
    expect(onEvaluate).toHaveBeenCalledWith(expect.objectContaining({ slot: "엠블렘", kind: "에디", target: ["마력 +12%", "마력 +9%"] }));
  });

  // 2026-10-11 심사 5회차: 경매장에서 못 사는 템은 다음 행동이 없었다 → 같은 자리에 큐브 비용 계산기로 가는 버튼
  it("경매장에서 못 사는 템(큐브)은 복사 대신 [큐브 비용 계산하기]로 계산기 탭에 간다", async () => {
    const cube = { ...body.value_ranking[1], slot: "무기", route: "큐브" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => ({ ...body, value_ranking: [body.value_ranking[0], cube] }) });
    render(<RoadmapPanel name="내신부레테" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "전체 부위 로드맵" })); });
    const second = cards()[1];
    expect(within(second).queryByRole("button", { name: "경매장 검색 조건 복사" })).toBeNull();
    expect(within(second).getByRole("link", { name: "큐브 비용 계산하기" }).getAttribute("href")).toMatch(/tab=calc|\/calc/);
  });

  it("순위 카드 안에 경매장 조건을 칩으로 바로 보여 준다(부위·등급·옵션 줄)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => body });
    render(<RoadmapPanel name="내신부레테" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "전체 부위 로드맵" })); });
    const first = cards()[0];
    const chips = within(first).getByRole("list", { name: "경매장 검색 조건" });
    expect(within(chips).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["부위엠블렘", "에디레전드리", "1줄마력 +12% 이상", "2줄마력 +9% 이상"]);
  });
});
