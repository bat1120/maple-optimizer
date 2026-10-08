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
  });
  it("확장이 있으면 [MapleScouter에서 진짜 배율 보기] — 고른 보스와 함께 변화량을 보낸다", async () => {
    document.documentElement.setAttribute("data-mapleopt-ext", "0.1.0");
    const posted = [];
    const orig = window.postMessage.bind(window);
    window.postMessage = (d) => { posted.push(d); if (d.type === "MAPLEOPT_FILL") setTimeout(() => window.dispatchEvent(new MessageEvent("message", { source: window, data: { type: "MAPLEOPT_FILL_ACK", ok: true } })), 0); };
    try {
      await run();
      await act(async () => { fireEvent.click(screen.getByRole("button", { name: "MapleScouter에서 진짜 배율 보기" })); await new Promise((r) => setTimeout(r, 10)); });
      expect(posted[0].payload.check).toMatchObject({ boss: "extreme_lotus", label: "익스트림 스우" });
      expect(posted[0].payload.fields).toEqual({ "STR|기본": 10 });
    } finally { window.postMessage = orig; }
  });
});
