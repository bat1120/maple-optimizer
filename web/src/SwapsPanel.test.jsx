import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import SwapsPanel, { potentialText } from "./SwapsPanel.jsx";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const ok = (body) => ({ ok: true, status: 200, json: async () => body });
const row = (over) => ({
  slot: "귀고리", name: "커맨더 포스 이어링", set: "칠흑의 보스 세트", level: 200, starforce: 18, wearers: 31,
  current: { name: "에스텔라 이어링", set: "여명의 보스 세트", level: 160, starforce: 18, potentials: ["INT +9%"], additional: [] },
  set_change: [{ set: "여명의 보스 세트", before: 4, after: 3 }, { set: "칠흑의 보스 세트", before: 1, after: 2 }],
  same: 1.0, flame: { samples: 31, min: -0.16, median: 0.67, max: 1.71, better_share: 0.97 },
  potential: { none: -0.5, break_even: { grade: "에픽", lines_good: 2, target: ["INT +6%", "INT +3%"], delta_pct: 0.48 },
               tiers: [], ladder_skips: [] },
  ...over,
});
const DATA = {
  evaluation_setting: { equipment: 2, hyper: 3, ability: 2 }, note: "실측",
  swaps: [
    row(),
    row({ slot: "반지1", name: "거대한 공포", current: { name: "마이스터링", set: "마이스터 세트", starforce: 18, potentials: [], additional: [] },
          same: 2.97, flame: { samples: 0, none: true }, potential: { none: 0.28, break_even: null, tiers: [], ladder_skips: [] } }),
    row({ slot: "모자", name: "도전자의 모자", same: -5.5, flame: { samples: 5, min: -5.9, median: -5.9, max: -5.9, better_share: 0 },
          potential: { none: -7, break_even: null, tiers: [], ladder_skips: [] } }),
  ],
};

describe("swaps panel", () => {
  it("이득인 갈아타기만 먼저 보여 주고 세트 변화·추옵 분포·잠재 손익분기를 적는다", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(DATA));
    render(<SwapsPanel name="내신부레테" defense={300} autoLoad />);
    await act(async () => {});
    expect(f.mock.calls[0][0]).toBe(`/api/character/${encodeURIComponent("내신부레테")}/swaps?boss_defense=300`);
    const rows = within(screen.getByRole("table", { name: "다른 템으로 갈아타기" })).getAllByRole("row");
    expect(rows).toHaveLength(3); // 머리 + 이득 2줄(손해인 도전자의 모자는 숨김)
    expect(rows[1]).toHaveTextContent("에스텔라 이어링 → 커맨더 포스 이어링");
    expect(rows[1]).toHaveTextContent("칠흑의 보스 세트 1→2");
    expect(rows[1]).toHaveTextContent("97%");
    expect(rows[1]).toHaveTextContent("에픽 INT +6% / INT +3% 이상");
    expect(rows[2]).toHaveTextContent("추옵 없음");
    expect(rows[2]).toHaveTextContent("잠재 없어도 이득");
    fireEvent.click(screen.getByRole("button", { name: "손해인 후보도 보기 (1)" }));
    expect(within(screen.getByRole("table", { name: "다른 템으로 갈아타기" })).getAllByRole("row")).toHaveLength(4);
  });

  it("잠재 손익분기 문구", () => {
    expect(potentialText(row({ potential: { none: 1, break_even: null, ladder_skips: [] } }))).toBe("잠재 없어도 이득");
    expect(potentialText(row({ same: 1.7, potential: { none: -3, break_even: null, ladder_skips: ["크리티컬 확률 +6%"] } })))
      .toBe("지금 잠재를 그대로 옮겨야 이득 (크리티컬 확률 +6% 줄 유지)");
    expect(potentialText(row({ same: -2, potential: { none: -3, break_even: null, ladder_skips: [] } }))).toBe("어떤 잠재로도 손해");
  });
});
