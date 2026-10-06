import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import App from "./App.jsx";

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.location.hash = ""; localStorage.clear(); });

const ok = (body) => ({ ok: true, status: 200, json: async () => body });

describe("App shell (주소 → 화면)", () => {
  it("첫 화면: 큰 검색창, 위쪽 막대에는 작은 검색창 없음", () => {
    window.location.hash = "#/";
    render(<App />);
    expect(screen.getByRole("heading", { name: /어디부터 바꿀까/ })).toBeInTheDocument();
    expect(screen.getAllByRole("searchbox")).toHaveLength(1);
  });
  it("계산기 페이지", () => {
    window.location.hash = "#/calc";
    render(<App />);
    expect(screen.getByRole("heading", { name: "강화 계산기" })).toBeInTheDocument();
  });
  it("관리자 페이지", () => {
    window.location.hash = "#/admin";
    render(<App />);
    expect(screen.getByRole("heading", { name: "관리자 도구" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "경매장 화면 연결" })).toBeInTheDocument();
  });
  it("캐릭터 주소면 캐릭터 화면을 불러오고, 주소가 바뀌면 따라간다", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ character_class: "레테", level: 287, date: null,
      active_setting: { equipment: 1, hyper: 1, ability: 1 }, stat_attack: { engine: 1, api: 1 }, combat_power_reference: 1,
      equipment_presets: {}, excluded: [], profile: { name: "레테" }, ranking: [] }));
    window.location.hash = `#/c/${encodeURIComponent("레테")}`;
    render(<App />);
    expect(await screen.findByRole("heading", { name: "레테" })).toBeInTheDocument();
    await act(async () => { window.location.hash = "#/calc"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
    expect(screen.getByRole("heading", { name: "강화 계산기" })).toBeInTheDocument();
  });
});
