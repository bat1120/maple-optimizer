import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import App from "./Admin.jsx";

const SUMMARY = {
  character_class: "레테", level: 287, date: null,
  active_setting: { equipment: 1, hyper: 1, ability: 1 },
  stat_attack: { engine: 67838400, api: 67838474 }, combat_power_reference: 72267618,
  equipment_presets: { 1: [{ slot: "무기", name: "제네시스 카르타", starforce: 22 }] }, excluded: [],
};
const SETTINGS = {
  ranking: [{ setting: { equipment: 2, hyper: 3, ability: 2 }, index: 2, relative_to_active: 1.42 }],
};

function routeFetch(routes) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    const key = Object.keys(routes).find((k) => url.includes(k));
    const [status, body] = routes[key];
    return { ok: status < 400, status, json: async () => body };
  });
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("admin page (예전 한 페이지 화면)", () => {
  it("조회하면 직업·레벨과 최적 보스 세팅을 보여준다", async () => {
    routeFetch({ "/settings": [200, SETTINGS], "/api/character/": [200, SUMMARY] });
    render(<App />);
    fireEvent.change(screen.getByLabelText("닉네임"), { target: { value: "내신부레테" } });
    fireEvent.click(screen.getByRole("button", { name: "조회" }));
    expect(await screen.findByText(/레테 Lv\.287/)).toBeInTheDocument();
    expect(await screen.findByText(/장비 2 · 하이퍼 3 · 어빌 2/)).toBeInTheDocument();
    expect(screen.getByText(/\+42\.0%/)).toBeInTheDocument();
  });

  it("오류 메시지를 그대로 보여준다", async () => {
    routeFetch({ "/api/character/": [404, { code: "NOT_FOUND", message: "캐릭터를 찾을 수 없습니다." }] });
    render(<App />);
    fireEvent.change(screen.getByLabelText("닉네임"), { target: { value: "없음" } });
    fireEvent.click(screen.getByRole("button", { name: "조회" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("캐릭터를 찾을 수 없습니다.");
  });

  it("빈 닉네임으로는 조회하지 않는다", () => {
    const f = routeFetch({});
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "조회" }));
    expect(f).not.toHaveBeenCalled();
  });

  it("판매 수수료를 고르면 효율 계산에 함께 보낸다 (기본 5%, MVP 실버↑·PC방 3%)", async () => {
    localStorage.setItem("maple-optimizer.listings.v1", JSON.stringify([
      { slot: "무기", part: "카르타", name: "새 무기", total: { MATK: 300 }, potentials: [], price: 5e9, resale: 1e9 }]));
    const f = routeFetch({ "/listings": [200, { setting: { equipment: 2, hyper: 3, ability: 2 }, boss: { name: "기준" }, ranking: [] }],
                           "/settings": [200, SETTINGS], "/api/character/": [200, SUMMARY] });
    render(<App />);
    expect(screen.getByLabelText("경매장 판매 수수료")).toHaveValue("0.05");
    fireEvent.change(screen.getByLabelText("경매장 판매 수수료"), { target: { value: "0.03" } });
    fireEvent.change(screen.getByLabelText("닉네임"), { target: { value: "내신부레테" } });
    fireEvent.click(screen.getByRole("button", { name: "조회" }));
    fireEvent.click(await screen.findByRole("button", { name: "효율 계산" }));
    await vi.waitFor(() => expect(f.mock.calls.some(([u]) => u.endsWith("/listings"))).toBe(true));
    const [, opts] = f.mock.calls.find(([u]) => u.endsWith("/listings"));
    expect(JSON.parse(opts.body).fee_rate).toBe(0.03);
    localStorage.clear();
  });
});
