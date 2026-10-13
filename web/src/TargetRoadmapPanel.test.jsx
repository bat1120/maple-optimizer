import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import TargetRoadmapPanel from "./TargetRoadmapPanel.jsx";

afterEach(() => { cleanup(); vi.restoreAllMocks(); document.documentElement.removeAttribute("data-mapleopt-ext"); });

const ok = (body) => ({ ok: true, status: 200, json: async () => body });
const DATA = {
  current_ratio: 34.52, target_ratio: 50, needed_multiplier: 1.448, reached: false, final_ratio: 48.7,
  total_cost_text: "1129억", hexa_core_multiplier: 1.02, equipment_steps: 2, events: { label: "이벤트 없음" }, note: "추정",
  steps: [
    { slot: "펜던트", path: "스타포스", name: "도미네이터 펜던트", from_star: 15, to_star: 16, delta_pct: 0.4, cost_text: "5000만",
      ratio_after: 34.66, total_cost_text: "5000만" },
    { slot: "HEXA 코어", path: "HEXA 코어", name: "화중군자 VI 1→2레벨", delta_pct: 0.47, cost_text: "2억 6600만",
      ratio_after: 34.82, total_cost_text: "3억 1600만" },
    { slot: "심볼", path: "심볼", name: "어센틱심볼 : 세르니움", from_level: 9, to_level: 10, delta_pct: 0.3, cost_text: "7억 900만",
      ratio_after: 34.92, total_cost_text: "10억 2500만", remaining_symbols: 263 },
  ],
  scouter: { v: 1, slot: "로드맵", from: "지금 템", to: "목표 50% 로드맵", name: "천지만물렌", job: "렌", level: 284,
             rows: { main: ["STR"], sub: ["DEX"], attack: "공격력" }, fields: { "STR|기본": 10 }, ied_add: [], ied_remove: [] },
};

async function run() {
  const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(DATA));
  render(<TargetRoadmapPanel name="천지만물렌" defense={300} />);
  fireEvent.change(screen.getByLabelText("지금 배율(%)"), { target: { value: "34.52" } });
  fireEvent.change(screen.getByLabelText("목표 배율(%)"), { target: { value: "50" } });
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "로드맵 만들기" })); });
  return f;
}

describe("목표 배율 로드맵 패널", () => {
  it("지금·목표 배율로 로드맵을 불러와 단계별 누적 배율과 비용을 보여 준다", async () => {
    const f = await run();
    expect(f.mock.calls[0][0]).toContain("/target-roadmap?");
    expect(f.mock.calls[0][0]).toContain("current_ratio=34.52");
    expect(f.mock.calls[0][0]).toContain("target_ratio=50");
    const rows = within(screen.getByRole("table", { name: "목표 배율 로드맵" })).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("도미네이터 펜던트 15→16성");
    expect(rows[1]).toHaveTextContent("34.66%");
    expect(screen.getByText(/48.70%/)).toBeInTheDocument();
    expect(rows[3]).toHaveTextContent("심볼 · 어센틱심볼 : 세르니움 9→10레벨");
    expect(rows[3]).toHaveTextContent("심볼 263개");
  });
  it("MapleScouter에 자동으로 넣어 배율을 읽는 버튼은 없다(2026-10-13, 운영자 연동 불가)", async () => {
    document.documentElement.setAttribute("data-mapleopt-ext", "0.1.0");
    await run();
    expect(screen.queryByRole("button", { name: /진짜 배율 보기/ })).toBeNull();
    expect(screen.queryByText(/크롬 확장/)).toBeNull();
  });
  it("[변화량 복사] — 로드맵 장비 변화(큐브·스타포스·HEXA 스탯·심볼)를 사람이 읽는 글로 복사한다", async () => {
    const writeText = vi.fn().mockResolvedValue();
    Object.assign(navigator, { clipboard: { writeText } });
    await run();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "변화량 복사" })); });
    const text = writeText.mock.calls[0][0];
    expect(text).toContain("로드맵: 지금 템 → 목표 50% 로드맵");
    expect(text).toContain("STR +10");
    expect(text).not.toContain("MAPLEOPT1");
  });
});
