import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import BossPicker, { ForceNote } from "./BossPicker.jsx";
import { bossBody, bossQuery, getSettings } from "../api.js";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const BOSSES = [
  { id: "lotus-hard", name: "스우", difficulty: "하드", defense: 300 },
  { id: "kaling-extreme", name: "카링", difficulty: "익스트림", defense: 380, authentic: 480 },
  { id: "seren-normal-1", name: "선택받은 세렌", difficulty: "노멀", phase: "1페이즈", defense: 380, authentic: 150 },
];

// 2026-10-11: 보스는 목록(보스·난이도)으로 고르고, 방어율 직접 입력도 남긴다
describe("boss picker", () => {
  it("보스 id면 boss=, 숫자면 예전처럼 boss_defense=", async () => {
    expect(bossQuery("kaling-extreme")).toEqual({ boss: "kaling-extreme" });
    expect(bossQuery(300)).toEqual({ boss_defense: "300" });
    expect(bossBody("kaling-extreme")).toEqual({ boss: "kaling-extreme" });
    expect(bossBody(300)).toEqual({ boss_defense: 300 });
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
    await getSettings("x", "kaling-extreme");
    expect(f.mock.calls[0][0]).toBe("/api/character/x/settings?boss=kaling-extreme");
  });

  it("목록에서 고르면 id를, 직접 입력이면 방어율 숫자를 넘긴다", () => {
    const onChange = vi.fn();
    const { rerender } = render(<BossPicker value={300} bosses={BOSSES} onChange={onChange} />);
    const select = screen.getByLabelText("보스");
    expect(screen.getByRole("option", { name: "카링 익스트림 (방어율 380%)" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "선택받은 세렌 노멀 1페이즈 (방어율 380%)" })).toBeInTheDocument();
    expect(select.value).toBe("custom");  // 숫자 값 = 직접 입력
    fireEvent.change(select, { target: { value: "kaling-extreme" } });
    expect(onChange).toHaveBeenLastCalledWith("kaling-extreme");
    fireEvent.change(screen.getByLabelText("보스 방어율(%)"), { target: { value: "250" } });
    expect(onChange).toHaveBeenLastCalledWith(250);
    rerender(<BossPicker value="kaling-extreme" bosses={BOSSES} onChange={onChange} />);
    expect(screen.queryByLabelText("보스 방어율(%)")).toBeNull();
    fireEvent.change(screen.getByLabelText("보스"), { target: { value: "custom" } });
    expect(onChange).toHaveBeenLastCalledWith(380);  // 고른 보스 방어율에서 시작
  });

  it("포스가 모자라면 요구·지금·피해 비율을 보여 준다", () => {
    render(<ForceNote force={{ kind: "어센틱포스", required: 480, current: 450, damage_pct: 70 }} />);
    expect(screen.getByText("요구 어센틱포스 480, 지금 450 — 피해 70%")).toBeInTheDocument();
  });

  it("포스가 넉넉하면 보정 배율만, 요구 포스 없는 보스는 아무것도 안 보인다", () => {
    const { container, rerender } = render(<ForceNote force={{ kind: "아케인포스", required: 1320, current: 1350, damage_pct: 100 }} />);
    expect(screen.getByText("요구 아케인포스 1320, 지금 1350 — 피해 100%")).toBeInTheDocument();
    rerender(<ForceNote force={null} />);
    expect(container.textContent).toBe("");
    rerender(<ForceNote force={{ kind: "어센틱포스", required: 480, current: null, damage_pct: null }} />);
    expect(screen.getByText(/지금 포스를 몰라 보정하지 않았어요/)).toBeInTheDocument();
  });
});
