import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { CraftPanel, CubePanel, OptimizePanel, StarforcePanel } from "./Panels.jsx";

function mockFetch(body, status = 200) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: status < 400, status, json: async () => body });
}
const sent = (f) => JSON.parse(f.mock.calls[0][1].body);
const set = (label, value) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("starforce panel", () => {
  it("입력을 보내고 평균·분포를 억 단위로 보여준다", async () => {
    const f = mockFetch({ exact_mean: 17_887_000_000, distribution: { mean: 1.79e10, median: 1.63e10, p75: 2.29e10, p90: 3.0e10 }, note: "n" });
    render(<StarforcePanel />);
    set("장비 레벨", "200"); set("시작 성", "0"); set("목표 성", "22"); set("파괴 시 비용", "30억");
    fireEvent.click(screen.getByLabelText("30% 할인"));
    fireEvent.click(screen.getByRole("button", { name: "스타포스 계산" }));
    expect(await screen.findByText(/평균 178억 8700만/)).toBeInTheDocument();
    expect(screen.getByText(/p90 300억/)).toBeInTheDocument();
    expect(sent(f)).toMatchObject({ level: 200, start: 0, target: 22, destroy_cost: 3_000_000_000, conditions: { discount30: true } });
  });

  it("목표 성이 시작 성 이하면 서버를 부르지 않고 안내한다", () => {
    const f = mockFetch({});
    render(<StarforcePanel />);
    set("시작 성", "22"); set("목표 성", "17");
    fireEvent.click(screen.getByRole("button", { name: "스타포스 계산" }));
    expect(f).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("목표 성");
  });
});

describe("cube panel", () => {
  it("줄 수 조건을 보내고 확률·평균 횟수·메소를 보여준다", async () => {
    const f = mockFetch({ probability: 0.02765, cost_per_reset: 45_000_000, cubes: { mean: 36.2, median: 25, p75: 50, p90: 83 },
                          meso: { mean: 1_628_000_000, median: 1_125_000_000, p75: 2_250_000_000, p90: 3_735_000_000 } });
    const onResult = vi.fn();
    render(<CubePanel onResult={onResult} />);
    set("옵션", "BOSS"); set("조건", "lines"); set("값", "2");
    fireEvent.click(screen.getByRole("button", { name: "큐브 계산" }));
    expect(await screen.findByText(/2\.765%/)).toBeInTheDocument();
    expect(screen.getByText(/평균 36\.2회/)).toBeInTheDocument();
    expect(sent(f)).toMatchObject({ table: "레전드리/무기/200", lines_at_least: { BOSS: 2 } });
    expect(onResult).toHaveBeenCalledWith({ probability: 0.02765, cost: 45_000_000 });
  });

  it("합 조건은 sum_at_least로 보낸다", async () => {
    const f = mockFetch({ probability: 0.007, cost_per_reset: 45_000_000, cubes: { mean: 140, median: 99, p75: 198, p90: 328 }, meso: { mean: 1, median: 1, p75: 1, p90: 1 } });
    render(<CubePanel />);
    set("옵션", "MATK"); set("조건", "sum"); set("값", "21");
    fireEvent.click(screen.getByRole("button", { name: "큐브 계산" }));
    await screen.findByText(/0\.700%/);
    expect(sent(f).sum_at_least).toEqual([{ key: "MATK", percent: true, value: 21 }]);
  });
});

describe("craft panel", () => {
  it("매물 가격의 직작 대비 위치를 보여준다", async () => {
    const f = mockFetch({ price: 2e10, craft_mean: 2.16e10, distribution: { mean: 2.16e10, median: 2.0e10, p75: 2.7e10, p90: 3.4e10 },
                          ratio_to_mean: 0.926, prob_craft_costs_more: 0.499, note: "추옵(환불) 비용 미포함" });
    render(<CraftPanel initialCube={{ probability: 0.02765, cost: 45_000_000 }} />);
    set("매물 가격", "200억"); set("베이스 템 가격", "20억"); set("장비 레벨", "200"); set("목표 성", "22"); set("파괴 시 비용", "30억");
    fireEvent.click(screen.getByRole("button", { name: "직작 비교" }));
    expect(await screen.findByText(/직작 평균의 92\.6%/)).toBeInTheDocument();
    expect(screen.getByText(/49\.9% 확률로 이 가격보다 더/)).toBeInTheDocument();
    expect(screen.getByText(/추옵\(환불\) 비용 미포함/)).toBeInTheDocument();
    expect(sent(f)).toMatchObject({ price: 2e10, base_price: 2e9, cube_p: 0.02765, cube_cost: 45_000_000, target_star: 22 });
  });
});

describe("optimize panel", () => {
  it("예산과 매물 목록으로 추천 순서를 보여준다", async () => {
    const f = mockFetch({ setting: { equipment: 2, hyper: 3, ability: 2, union: 3, link: 2 }, budget: 5e9, spent: 4e9, gain_pct: 2.006,
                          actions: [{ slot: "반지1", name: "더 센 반지", cost: 4e9 }] });
    const listings = [{ slot: "반지1", part: "반지", name: "더 센 반지", total: {}, potentials: [], price: 4e9, resale: 0 }];
    render(<OptimizePanel name="내신부레테" listings={listings} defense={300} />);
    set("예산", "50억");
    fireEvent.click(screen.getByRole("button", { name: "최적화" }));
    expect(await screen.findByText(/1\. 반지1 · 더 센 반지 · 40억/)).toBeInTheDocument();
    expect(screen.getByText(/실딜 \+2\.006%/)).toBeInTheDocument();
    expect(f.mock.calls[0][0]).toBe(`/api/character/${encodeURIComponent("내신부레테")}/optimize`);
    expect(sent(f)).toMatchObject({ budget: 5e9, boss_defense: 300, candidates: listings });
  });

  it("매물이 없으면 안내만 한다", () => {
    const f = mockFetch({});
    render(<OptimizePanel name="x" listings={[]} defense={300} />);
    fireEvent.click(screen.getByRole("button", { name: "최적화" }));
    expect(f).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("매물");
  });
});
