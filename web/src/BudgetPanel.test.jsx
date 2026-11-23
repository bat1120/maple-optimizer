import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import BudgetPanel, { stepLabel } from "./BudgetPanel.jsx";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const body = {
  budget_text: "50억", spent_text: "47억 7020만", left_text: "2억 2979만", gain_pct: 3.9299,
  steps: [
    { slot: "귀고리", path: "추옵", name: "에스텔라 이어링", cost_text: "4395만", total_cost_text: "4395만", gain_pct_after: 0.156 },
    { slot: "장갑", path: "스타포스", name: "에테르넬 메이지글러브", from_star: 15, to_star: 16, cost_text: "4억 9743만",
      total_cost_text: "5억 4138만", gain_pct_after: 0.797 },
  ],
  next_step: { slot: "보조무기", path: "큐브", kind: "잠재", grade: "레전드리", target: ["마력 +9%"], cost_text: "105억 8996만", short_text: "103억 6016만" },
  note: "비용은 평균 기대값이에요.",
};
const mock = (json, ok = true, status = 200) => vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok, status, json: async () => json });

describe("BudgetPanel", () => {
  it("가진 메소를 넣으면 메소로 바꿔 보내고, 어디까지 오르는지 결론을 먼저 보여 준다", async () => {
    const f = mock(body);
    render(<BudgetPanel name="레테" defense={300} />);
    fireEvent.change(screen.getByLabelText("가진 메소"), { target: { value: "50억" } });
    fireEvent.click(screen.getByRole("button", { name: "계산하기" }));
    expect(await screen.findByText("+3.93%")).toBeInTheDocument();
    expect(f.mock.calls[0][0]).toContain("/budget-roadmap?");
    expect(f.mock.calls[0][0]).toContain("budget=5000000000");
    expect(screen.getByText(/47억 7020만 사용 · 2억 2979만 남음/)).toBeInTheDocument();
    const steps = within(screen.getByRole("list", { name: "예산 안에서 할 순서" })).getAllByRole("listitem");
    expect(steps).toHaveLength(2);
    expect(steps[0]).toHaveTextContent("귀고리 추옵 재설정");
    expect(steps[1]).toHaveTextContent("에테르넬 메이지글러브 15→16성");
    expect(screen.getByText(/103억 6016만/)).toBeInTheDocument();
  });

  it("자주 쓰는 금액을 누르면 바로 계산한다", async () => {
    const f = mock(body);
    render(<BudgetPanel name="레테" defense={300} />);
    fireEvent.click(screen.getByRole("button", { name: "100억" }));
    await screen.findByText("+3.93%");
    expect(f.mock.calls[0][0]).toContain("budget=10000000000");
  });

  it("금액을 읽을 수 없으면 서버를 부르지 않고 적는 법을 알려 준다", () => {
    const f = mock(body);
    render(<BudgetPanel name="레테" defense={300} />);
    fireEvent.change(screen.getByLabelText("가진 메소"), { target: { value: "많이" } });
    fireEvent.click(screen.getByRole("button", { name: "계산하기" }));
    expect(screen.getByRole("alert")).toHaveTextContent("50억");
    expect(f).not.toHaveBeenCalled();
  });

  it("할 수 있는 단계가 없으면 그렇게 말한다", async () => {
    mock({ ...body, steps: [], gain_pct: 0, spent_text: "0", left_text: "100만" , budget_text: "100만" });
    render(<BudgetPanel name="레테" defense={300} />);
    fireEvent.change(screen.getByLabelText("가진 메소"), { target: { value: "100만" } });
    fireEvent.click(screen.getByRole("button", { name: "계산하기" }));
    expect(await screen.findByText(/지금 할 수 있는 단계가 없어요/)).toBeInTheDocument();
  });

  it("단계가 많으면 처음 5개만 보이고, 눌러서 모두 본다", async () => {
    const many = Array.from({ length: 8 }, (_, i) => ({ slot: `부위${i}`, path: "추옵", name: `템${i}`, cost_text: "1억", total_cost_text: `${i + 1}억`, gain_pct_after: i + 1 }));
    mock({ ...body, steps: many });
    render(<BudgetPanel name="레테" defense={300} />);
    fireEvent.click(screen.getByRole("button", { name: "50억" }));
    const list = await screen.findByRole("list", { name: "예산 안에서 할 순서" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(5);
    fireEvent.click(screen.getByRole("button", { name: "8단계 모두 보기" }));
    expect(within(list).getAllByRole("listitem")).toHaveLength(8);
  });

  it("단계 이름을 사람이 읽는 말로 만든다", () => {
    expect(stepLabel({ path: "큐브", slot: "보조무기", kind: "잠재", grade: "레전드리" })).toBe("보조무기 잠재 레전드리");
    expect(stepLabel({ path: "심볼", name: "어센틱심볼 : 아르크스", from_level: 3, to_level: 4 })).toBe("어센틱심볼 : 아르크스 3→4레벨");
  });
});
