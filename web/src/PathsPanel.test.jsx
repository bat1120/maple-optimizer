import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import PathsPanel from "./PathsPanel.jsx";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const ok = (body) => ({ ok: true, status: 200, json: async () => body });
const PATHS = {
  evaluation_setting: { equipment: 2, hyper: 3, ability: 2 }, observed_count: 2, note: "구매·직작·큐브",
  all: [
    { slot: "상의", path: "구매", name: "에테르넬 메이지로브", delta_pct: 3.1, cost: 2e10, cost_text: "200억", per_100m: 0.0155,
      sold: false, set_change: [{ set: "도전자의 장비 세트(마법사)", before: 7, after: 6 }, { set: "에테르넬 세트(마법사)", before: 2, after: 3 }] },
    { slot: "엠블렘", path: "큐브", kind: "에디", grade: "레전드리", lines_good: 2, target: ["마력 +12%", "마력 +9%"],
      delta_pct: 7.362, cost: 2.5e10, cost_text: "253억 8269만", per_100m: 0.029, set_change: [] },
  ],
  best_by_slot: [],
};

describe("paths panel", () => {
  it("구매·직작·큐브 경로를 억당으로 보여주고 세트 변화를 표시한다", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(PATHS));
    render(<PathsPanel name="내신부레테" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "업그레이드 경로 비교" })); });
    expect(f.mock.calls[0][0]).toBe(`/api/character/${encodeURIComponent("내신부레테")}/paths?boss_defense=300`);
    const rows = within(screen.getByRole("table", { name: "업그레이드 경로" })).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("상의");
    expect(rows[1]).toHaveTextContent("구매 · 에테르넬 메이지로브 (호가)");
    expect(rows[1]).toHaveTextContent("200억");
    expect(rows[1]).toHaveTextContent("도전자의 장비 세트(마법사) 7→6");
    expect(rows[2]).toHaveTextContent("큐브 에디 레전드리 2줄");
  });

  it("경매장 시세 갱신을 누르면 검색 횟수를 알리고 경로를 다시 불러온다", async () => {
    const f = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(ok({ searched: 6, recorded: 9, search_remaining: 81, errors: [], plan: [] }))
      .mockResolvedValueOnce(ok(PATHS));
    render(<PathsPanel name="내신부레테" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "경매장 시세 갱신" })); });
    expect(f.mock.calls[0][0]).toBe("/api/market/refresh");
    expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({ name: "내신부레테", boss_defense: 300, max_searches: 15 });
    expect(screen.getByText(/검색 6회 · 매물 9건 저장 · 오늘 남은 검색 81회/)).toBeInTheDocument();
    expect(f.mock.calls[1][0]).toContain("/paths");
  });
  it("스타포스 경로: 지금 성 → 목표 성과 평균 파괴 횟수(스페어 비용 별도)를 보여 준다", async () => {
    const sf = { slot: "벨트", path: "스타포스", name: "분노한 자쿰의 벨트", from_star: 17, to_star: 22, delta_pct: 2.1,
                 cost: 3e9, cost_text: "30억", per_100m: 0.07, expected_destroys: 0.42, expected_spares: 0.5, spare_price: 0,
                 gain: { INT: 55 }, set_change: [] };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ ...PATHS, all: [sf] }));
    render(<PathsPanel name="내신부레테" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "업그레이드 경로 비교" })); });
    const row = within(screen.getByRole("table", { name: "업그레이드 경로" })).getAllByRole("row")[1];
    expect(row).toHaveTextContent("스타포스 · 분노한 자쿰의 벨트 17→22성");
    expect(row).toHaveTextContent("평균 파괴 0.42회");
    expect(row).toHaveTextContent("스페어 0.50개");
    expect(row).toHaveTextContent("스페어 값 미포함");
  });
  it("이벤트·스페어 값: 고르면 그 조건으로 다시 계산한다(샤이닝 스타포스·파괴 방지·미라클 타임·스페어 억)", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ ...PATHS, events: { label: "이벤트 없음" } }));
    render(<PathsPanel name="내신부레테" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "업그레이드 경로 비교" })); });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "샤이닝 스타포스 한 번에" })); });
    for (const n of [/30% 할인/, /21성 이하 파괴 30% 감소/, /5·10·15성 100%/, /복구 메소 20% 할인/]) {
      expect(screen.getByRole("checkbox", { name: n })).toBeChecked();
    }
    await act(async () => { fireEvent.click(screen.getByRole("checkbox", { name: /미라클 타임/ })); });
    await act(async () => { fireEvent.click(screen.getByRole("checkbox", { name: /파괴 방지/ })); });
    await act(async () => { fireEvent.change(screen.getByLabelText("스페어 1개 값(억)"), { target: { value: "12" } }); });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "이 조건으로 계산" })); });
    const url = f.mock.calls.at(-1)[0];
    expect(url).toContain("sf=discount30%2Cdestroy_down30%2Cguarantee_5_10_15%2Crestore_discount20%2Cprotect");
    expect(url).toContain("miracle=true");
    expect(url).toContain("spare_price=1200000000");
  });
  it("HEXA: 조각 값(만 메소)·HEXA 스탯 썬데이를 보내고, 헥사 행에 조각·솔 에르다·딜 지분 출처를 보여 준다", async () => {
    const hx = { slot: "HEXA 코어", path: "HEXA 코어", name: "인보크 : 템플러 VI/이딕트 : 템플러 아츠 VI 20→21레벨",
                 delta_pct: 0.25, cost: 5.95e8, cost_text: "5억 9500만", per_100m: 0.042, fragments: 85, erda: 3,
                 share_source: "직업 기준값(연무장 상위 기록 중앙값)", set_change: [] };
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ ...PATHS, all: [hx], events: { label: "이벤트 없음" } }));
    render(<PathsPanel name="내신부레테" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "업그레이드 경로 비교" })); });
    await act(async () => { fireEvent.change(screen.getByLabelText("조각 1개 값(만 메소)"), { target: { value: "700" } }); });
    await act(async () => { fireEvent.click(screen.getByRole("checkbox", { name: /HEXA 스탯 썬데이/ })); });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "이 조건으로 계산" })); });
    const url = f.mock.calls.at(-1)[0];
    expect(url).toContain("fragment_price=7000000");
    expect(url).toContain("hexa_sunday=true");
    const row = within(screen.getByRole("table", { name: "업그레이드 경로" })).getAllByRole("row")[1];
    expect(row).toHaveTextContent("다음 1레벨 · 인보크 : 템플러 VI/이딕트 : 템플러 아츠 VI 20→21레벨");
    expect(row.textContent).not.toContain("HEXA 코어 · ");  // 부위 칸과 겹치지 않게
    expect(row).toHaveTextContent("조각 85개 · 솔 에르다 3개");
    expect(row).toHaveTextContent("직업 기준값");
  });
  it("썬데이 이벤트를 하나씩: 30% 할인만 켜면 그것만 보낸다", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ ...PATHS, events: { label: "스타포스 30% 할인" } }));
    render(<PathsPanel name="내신부레테" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "업그레이드 경로 비교" })); });
    await act(async () => { fireEvent.click(screen.getByRole("checkbox", { name: /30% 할인/ })); });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "이 조건으로 계산" })); });
    const url = f.mock.calls.at(-1)[0];
    expect(url).toContain("sf=discount30");
    expect(url).not.toContain("destroy_down30");
  });
  it("부위별 스페어 값: 스타포스 경로가 나온 부위마다 칸이 생기고, 넣은 부위만 spare_by_slot으로 보낸다", async () => {
    const sf = { slot: "벨트", path: "스타포스", name: "분노한 자쿰의 벨트", from_star: 17, to_star: 18, delta_pct: 0.5,
                 cost: 3e8, cost_text: "3억", per_100m: 0.1, expected_destroys: 0.4, expected_spares: 0.4, spare_price: 0, set_change: [] };
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ ...PATHS, all: [sf], events: { label: "이벤트 없음" } }));
    render(<PathsPanel name="내신부레테" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "업그레이드 경로 비교" })); });
    await act(async () => { fireEvent.change(screen.getByLabelText("벨트 스페어 값(억)"), { target: { value: "50" } }); });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "이 조건으로 계산" })); });
    const url = decodeURIComponent(f.mock.calls.at(-1)[0]);
    expect(url).toContain("spare_by_slot=벨트:5000000000");
  });
  it("추옵: 불꽃 값(만 메소)을 넣으면 flame_prices로 보내고, 추옵 행에 불꽃·평균 횟수·주스탯 환산 목표를 보여 준다", async () => {
    const fl = { slot: "무기", path: "추옵", name: "제네시스 카르타", flame: "추가옵션 재설정", price_each: 3e6,
                 expected_tries: 1154.65, reach_probability: 0.000866, target_score: 8.93, mean_score: 9.42, current_score: 8.93,
                 target_main: 829.4, current_main: 829.3, delta_pct: 0.49, cost: 3.46e9, cost_text: "34억 6396만", per_100m: 0.014,
                 kind: null, set_change: [] };
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ ...PATHS, all: [fl], events: { label: "이벤트 없음" } }));
    render(<PathsPanel name="내신부레테" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "업그레이드 경로 비교" })); });
    await act(async () => { fireEvent.change(screen.getByLabelText("심연의 환생의 불꽃 1개 값(만 메소)"), { target: { value: "5000" } }); });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "이 조건으로 계산" })); });
    const url = decodeURIComponent(f.mock.calls.at(-1)[0]);
    expect(url).toContain("flame_prices=심연:50000000");
    const row = within(screen.getByRole("table", { name: "업그레이드 경로" })).getAllByRole("row")[1];
    expect(row).toHaveTextContent("추옵 · 제네시스 카르타 · 추가옵션 재설정");
    expect(row).toHaveTextContent("평균 1,155회");
    expect(row).toHaveTextContent("주스탯 환산 829 → 830 이상");
  });
});
