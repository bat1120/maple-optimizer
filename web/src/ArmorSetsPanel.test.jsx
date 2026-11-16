import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import ArmorSetsPanel from "./ArmorSetsPanel.jsx";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const ok = (body) => ({ ok: true, status: 200, json: async () => body });
const piece = (name, set, starforce, kept = false) => ({ name, set, branch: "도적", starforce, kept });
const combo = (label, delta_pct, over = {}) => ({
  label, delta_pct, set_change: [{ set: "루타비스 세트(도적)", before: 3, after: 4 }],
  pieces: { 모자: piece("하이네스 어새신보닛", "카루타", 24, true), 신발: piece("앱솔랩스 시프슈즈", "앱솔", 18) }, ...over,
});
const NOW = combo("카루타(도적) 3 · 앱솔(도적) 3 · 에테르넬(도적) 1", 0,
  { pieces: { 모자: piece("하이네스 어새신보닛", "카루타", 24, true) }, set_change: [] });
const DATA = {
  starforce: 18, total: 3, note: "실측",
  current: NOW,
  combos: [combo("에테르넬(도적) 7", 15.26), NOW, combo("카루타(도적) 3 · 앱솔(도적) 4", -1.5)],
  classics: [{ ...combo("에테르넬(도적) 7", 15.26), classic: "7에테" },
             { ...combo("카루타(도적) 3 · 아케인(해적) 4", -4.2), classic: "3카 4아케인" }],
};

describe("방어구 세트 조합", () => {
  it("조합 이름·실딜·칸별 템을 큰 순으로 보여 주고 지금 세팅을 표시한다", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(DATA));
    render(<ArmorSetsPanel name="행복누림공익" defense={300} autoLoad />);
    await act(async () => {});
    expect(f.mock.calls[0][0]).toBe(`/api/character/${encodeURIComponent("행복누림공익")}/armor-sets?boss_defense=300&starforce=18`);
    const rows = within(screen.getByRole("table", { name: "방어구 세트 조합" })).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveTextContent("에테르넬(도적) 7");
    expect(rows[0]).toHaveTextContent("+15.260%");
    expect(rows[1]).toHaveTextContent("지금");
    expect(rows[2]).toHaveTextContent("카루타(도적) 3 · 앱솔(도적) 4");
    expect(rows[2]).toHaveTextContent("신발 앱솔랩스 시프슈즈 18성");
    expect(rows[2]).toHaveTextContent("루타비스 세트(도적) 3→4");
    // 지금 세팅은 순위 밖이어도 표 위에 따로 적는다
    expect(screen.getByText(/지금 세팅/)).toHaveTextContent("지금 세팅: 카루타(도적) 3 · 앱솔(도적) 3 · 에테르넬(도적) 1");
  });

  it("대표 조합(3카4앱 등)은 순위와 상관없이 따로 보여 준다", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(DATA));
    render(<ArmorSetsPanel name="행복누림공익" defense={300} autoLoad />);
    await act(async () => {});
    const rows = within(screen.getByRole("table", { name: "대표 조합" })).getAllByRole("row").slice(1);
    expect(rows.map((r) => r.cells[0].textContent)).toEqual(["7에테", "3카 4아케인"]);
    expect(rows[1]).toHaveTextContent("카루타(도적) 3 · 아케인(해적) 4");
    expect(rows[1]).toHaveTextContent("-4.200%");
  });

  it("스타포스를 바꾸면 그 성으로 다시 계산한다", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(DATA));
    render(<ArmorSetsPanel name="행복누림공익" defense={300} autoLoad />);
    await act(async () => {});
    const pick = screen.getByRole("combobox", { name: "바꿀 템 스타포스" });
    expect([...pick.options].map((o) => o.value)).toEqual(["17", "18", "21", "22"]);
    await act(async () => { fireEvent.change(pick, { target: { value: "22" } }); });
    expect(f.mock.calls.at(-1)[0]).toBe(`/api/character/${encodeURIComponent("행복누림공익")}/armor-sets?boss_defense=300&starforce=22`);
  });
});
