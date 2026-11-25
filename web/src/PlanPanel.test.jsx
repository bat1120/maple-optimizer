import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import PlanPanel, { buyable, effPct, stepLabel } from "./PlanPanel.jsx";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const cube = { slot: "하의", path: "큐브", kind: "잠재", grade: "레전드리", lines_good: 2, name: "도전자의 하의", route: "경매장",
  target: ["INT +12%", "INT +9%"], cost_text: "30억 4736만", total_cost_text: "36억 4874만", per_100m: 0.0172, delta_pct: 0.52, gain_pct_after: 1.45 };
const plan = {
  budget_text: null, spent_text: "36억 4874만", left_text: null, gain_pct: 1.45, next_step: null, note: "비용은 평균 기대값이에요.",
  steps: [
    { slot: "귀고리", path: "추옵", name: "에스텔라 이어링", cost_text: "4395만", total_cost_text: "4395만", per_100m: 0.3537, delta_pct: 0.156, gain_pct_after: 0.156 },
    { slot: "장갑", path: "스타포스", name: "에테르넬 메이지글러브", from_star: 15, to_star: 16, cost_text: "4억 9743만",
      total_cost_text: "5억 4138만", per_100m: 0.1287, delta_pct: 0.64, gain_pct_after: 0.797 },
    cube,
    { slot: "무기", path: "큐브", kind: "에디", grade: "레전드리", lines_good: 2, name: "제네시스 카르타", route: "큐브",
      target: ["마력 +12%", "마력 +9%"], cost_text: "185억 6870만", total_cost_text: "222억 1744만", per_100m: 0.019, delta_pct: 3.5, gain_pct_after: 5.0 },
  ],
};
const budgeted = { ...plan, budget_text: "50억", spent_text: "47억 7020만", left_text: "2억 2979만", gain_pct: 3.9299,
  next_step: { slot: "보조무기", path: "큐브", kind: "잠재", grade: "레전드리", lines_good: 3, route: "경매장", cost_text: "105억 8996만", short_text: "103억 6016만" } };
const mock = (...bodies) => {
  const f = vi.spyOn(globalThis, "fetch");
  bodies.forEach((b) => f.mockResolvedValueOnce({ ok: true, status: 200, json: async () => b }));
  return f;
};
const rows = () => within(screen.getByRole("list", { name: "할 순서" })).getAllByRole("listitem").filter((li) => li.classList.contains("plan-row"));

describe("PlanPanel — 계획 하나", () => {
  it("메소를 넣지 않아도 효율 순서가 바로 나오고, 큰 숫자는 1억 메소당 효율이다", async () => {
    const f = mock(plan);
    render(<PlanPanel name="레테" defense={300} />);
    expect(await screen.findByText("귀고리 추옵 재설정")).toBeInTheDocument();
    expect(f.mock.calls[0][0]).toContain("/budget-roadmap?");
    expect(f.mock.calls[0][0]).not.toContain("budget=");
    const first = rows()[0];
    expect(first.querySelector(".plan-eff")).toHaveTextContent("+0.354%");
    expect(first).toHaveTextContent("게임에서 추가옵션 재설정");
    expect(screen.queryByText(/까지 올릴 수 있어요/)).toBeNull(); // 메소를 넣기 전에는 예산 결론이 없다
  });

  it("가진 메소를 넣으면 메소로 바꿔 보내고, 어디까지 오르는지 결론을 먼저 보여 준다", async () => {
    const f = mock(plan, budgeted);
    render(<PlanPanel name="레테" defense={300} />);
    await screen.findByText("귀고리 추옵 재설정");
    fireEvent.change(screen.getByLabelText("가진 메소"), { target: { value: "50억" } });
    fireEvent.click(screen.getByRole("button", { name: "계산하기" }));
    expect(await screen.findByText("+3.93%")).toBeInTheDocument();
    expect(f.mock.calls[1][0]).toContain("budget=5000000000");
    expect(screen.getByText(/47억 7020만 사용 · 2억 2979만 남음/)).toBeInTheDocument();
    // 예산이 모자란 다음 목표는 같은 목록의 마지막 줄 — 경매장에서 살 수 있으면 예산 안의 매물을 찾아볼 수 있다
    const next = rows().at(-1);
    expect(next.querySelector(".plan-no")).toHaveTextContent("다음");
    expect(next).toHaveTextContent("103억 6016만 더 필요");
    expect(within(next).getByRole("button", { name: "경매장에서 찾기" })).toBeInTheDocument();
  });

  it("금액을 읽을 수 없으면 서버를 부르지 않고 적는 법을 알려 준다", async () => {
    const f = mock(plan);
    render(<PlanPanel name="레테" defense={300} />);
    await screen.findByText("귀고리 추옵 재설정");
    fireEvent.change(screen.getByLabelText("가진 메소"), { target: { value: "많이" } });
    fireEvent.click(screen.getByRole("button", { name: "계산하기" }));
    expect(screen.getByRole("alert")).toHaveTextContent("50억");
    expect(f).toHaveBeenCalledTimes(1);
  });

  it("경매장에서 살 수 있는 줄만 [경매장에서 찾기] — 누르면 2단계 조건, 공유를 누르면 그 줄 바로 아래에 공유 칸", async () => {
    mock(plan);
    const onEvaluate = vi.fn();
    const stages = [];
    render(<PlanPanel name="레테" defense={300} onEvaluate={onEvaluate} onStage={(n) => stages.push(n)} watch={<div>화면 공유 칸</div>} />);
    await screen.findByText("귀고리 추옵 재설정");
    expect(screen.getAllByRole("button", { name: "경매장에서 찾기" })).toHaveLength(1);   // 추옵·스타포스·구매 불가 템에는 없다
    expect(within(rows()[3]).getByRole("link", { name: "큐브 비용 계산" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "경매장에서 찾기" }));
    const row = rows()[2];
    expect(row).toHaveTextContent("2단계");
    expect(within(row).getByRole("list", { name: "경매장 검색 조건" })).toHaveTextContent("옵션 1INT +12% 이상");
    expect(row).toHaveTextContent("30억 4736만보다 싸면 사는 쪽이");
    fireEvent.click(within(row).getByRole("button", { name: "화면 공유 칸 열기" }));
    expect(onEvaluate).toHaveBeenCalledWith(cube);
    expect(stages).toEqual([1, 2, 3]);
    const watch = screen.getByText("화면 공유 칸").closest("li");
    expect(Number(watch.style.order)).toBe(Number(row.style.order) + 1);   // 누른 줄 바로 아래
  });

  it("단계가 많으면 처음 6개만 보이고, 눌러서 모두 본다", async () => {
    const many = Array.from({ length: 9 }, (_, i) => ({ slot: `부위${i}`, path: "추옵", name: `템${i}`, cost_text: "1억", total_cost_text: `${i + 1}억`, per_100m: 0.1, gain_pct_after: i + 1 }));
    mock({ ...plan, steps: many });
    render(<PlanPanel name="레테" defense={300} />);
    await screen.findByText("부위0 추옵 재설정");
    expect(rows()).toHaveLength(6);
    fireEvent.click(screen.getByRole("button", { name: "9단계 모두 보기" }));
    expect(rows()).toHaveLength(9);
  });

  it("경매장에서 살 수 있는 첫 줄은 뒤쪽에 있어도 보인다(번호는 그대로) — 2~4단계로 갈 길", async () => {
    const many = Array.from({ length: 9 }, (_, i) => ({ slot: `부위${i}`, path: "추옵", name: `템${i}`, cost_text: "1억", total_cost_text: `${i + 1}억`, per_100m: 0.1, gain_pct_after: i + 1 }));
    mock({ ...plan, steps: [...many, cube] });
    render(<PlanPanel name="레테" defense={300} />);
    await screen.findByText("부위0 추옵 재설정");
    const list = rows();
    expect(list).toHaveLength(7);
    expect(list[6]).toHaveTextContent("하의 잠재 레전드리 2줄");
    expect(list[6].querySelector(".plan-no")).toHaveTextContent("10");
    expect(list[6]).toHaveClass("after-gap");
    expect(list[6].dataset.gap).toMatch(/^7~9번은 '모두 보기'에 있어요/);
    expect(within(list[6]).getByRole("button", { name: "경매장에서 찾기" })).toBeInTheDocument();
  });

  // 2026-11-25 운영 화면: 건너뛴 줄이 하나일 때 '7~7번'이라고 나왔다
  it("건너뛴 줄이 하나면 '7번'이라고 적는다", async () => {
    const many = Array.from({ length: 7 }, (_, i) => ({ slot: `부위${i}`, path: "추옵", name: `템${i}`, cost_text: "1억", total_cost_text: `${i + 1}억`, per_100m: 0.1, gain_pct_after: i + 1 }));
    mock({ ...plan, steps: [...many, cube] });
    render(<PlanPanel name="레테" defense={300} />);
    await screen.findByText("부위0 추옵 재설정");
    expect(rows()[6].dataset.gap).toMatch(/^7번은 '모두 보기'에 있어요/);
  });

  it("계획에 경매장에서 살 수 있는 줄이 없으면 '경매장에서 찾는다면' 줄을 붙인다(계획에 있으면 안 붙인다)", async () => {
    const only = plan.steps.slice(0, 2);
    mock({ ...plan, steps: only, auction_pick: cube });
    const { unmount } = render(<PlanPanel name="레테" defense={300} />);
    await screen.findByText("귀고리 추옵 재설정");
    const last = rows().at(-1);
    expect(last.querySelector(".plan-no")).toHaveTextContent("경매장");
    expect(last).toHaveTextContent("경매장에서 찾는다면 이것부터");
    expect(within(last).getByRole("button", { name: "경매장에서 찾기" })).toBeInTheDocument();
    unmount();
    mock({ ...plan, auction_pick: cube });   // 계획 안에 이미 살 수 있는 줄이 있다
    render(<PlanPanel name="레테" defense={300} />);
    await screen.findByText("귀고리 추옵 재설정");
    expect(rows().some((li) => li.querySelector(".plan-no").textContent === "경매장")).toBe(false);
  });

  it("메소를 넣었으면 그 메소로 하는 줄을 전부 보여 준다(접지 않는다)", async () => {
    const many = Array.from({ length: 9 }, (_, i) => ({ slot: `부위${i}`, path: "추옵", name: `템${i}`, cost_text: "1억", total_cost_text: `${i + 1}억`, per_100m: 0.1, gain_pct_after: i + 1 }));
    mock({ ...budgeted, steps: many, next_step: null });
    render(<PlanPanel name="레테" defense={300} />);
    await screen.findByText("부위0 추옵 재설정");
    expect(rows()).toHaveLength(9);
    expect(screen.queryByRole("button", { name: /모두 보기/ })).toBeNull();
  });

  it("계획이 비면 새 장비부터 맞추라고 알려 준다(기본 장비만 낀 캐릭터)", async () => {
    mock({ ...plan, steps: [], next_step: null, auction_pick: null });
    render(<PlanPanel name="레테" defense={100} />);
    expect(await screen.findByText("지금 낀 장비로는 강화해서 올릴 단계가 없어요")).toBeInTheDocument();
    expect(screen.getByText(/방어구 세트 조합/)).toBeInTheDocument();
  });

  it("1억 메소당 효율은 값이 크면 소수 자리를 줄인다(줄이 넘치지 않게)", () => {
    expect([effPct(0.354), effPct(68.062), effPct(218.635)]).toEqual(["+0.354%", "+68.1%", "+219%"]);
  });

  it("방어율이 바뀌면 늦게 온 옛 요청의 오류는 보여 주지 않는다", async () => {
    let failOld;
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => (String(url).includes("boss_defense=300")
      ? new Promise((r) => { failOld = () => r({ ok: false, status: 422, json: async () => ({ code: "NO_DAMAGE", message: "피해가 들어가지 않아요" }) }); })
      : Promise.resolve({ ok: true, status: 200, json: async () => plan })));
    const { rerender } = render(<PlanPanel name="레테" defense={300} />);
    rerender(<PlanPanel name="레테" defense={100} />);
    await screen.findByRole("list", { name: "할 순서" });
    await act(async () => { failOld(); });
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("list", { name: "할 순서" })).toBeInTheDocument();
  });

  it("단계 이름과 살 수 있는지 판단", () => {
    expect(stepLabel(cube)).toBe("하의 잠재 레전드리 2줄");
    expect(stepLabel({ path: "심볼", name: "어센틱심볼 : 아르크스", from_level: 3, to_level: 4 })).toBe("어센틱심볼 : 아르크스 3→4레벨");
    expect(buyable(cube)).toBe(true);
    expect(buyable({ ...cube, route: "큐브" })).toBe(false);
    expect(buyable({ path: "추옵" })).toBe(false);
  });
});
