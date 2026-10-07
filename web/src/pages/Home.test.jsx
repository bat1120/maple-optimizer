import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import Home from "./Home.jsx";
import { addRecent } from "../recent.js";

afterEach(() => { cleanup(); vi.restoreAllMocks(); localStorage.clear(); window.location.hash = ""; });

describe("home page", () => {
  it("검색하면 캐릭터 주소로 가고 최근 검색에 남는다", () => {
    render(<Home />);
    fireEvent.change(screen.getByRole("searchbox", { name: "캐릭터 닉네임" }), { target: { value: " 내신부레테 " } });
    fireEvent.submit(screen.getByRole("search"));
    expect(window.location.hash).toBe(`#/c/${encodeURIComponent("내신부레테")}`);
    expect(JSON.parse(localStorage.getItem("maple-optimizer:recent"))).toEqual(["내신부레테"]);
  });
  it("최근 검색을 눌러 다시 볼 수 있다", () => {
    addRecent("레테");
    render(<Home />);
    expect(screen.getByRole("link", { name: "레테" })).toHaveAttribute("href", `#/c/${encodeURIComponent("레테")}`);
  });
  it("/ 키로 검색창에 바로 들어간다", () => {
    render(<Home />);
    fireEvent.keyDown(window, { key: "/" });
    expect(document.activeElement).toBe(screen.getByRole("searchbox", { name: "캐릭터 닉네임" }));
  });
  it("계산기 바로가기", () => {
    render(<Home />);
    expect(screen.getByRole("link", { name: /스타포스·큐브 계산기/ })).toHaveAttribute("href", "#/calc");
  });

  it("처음 오면 사용 안내(검색·탭 설명)가 보이고, 닫으면 다시 안 뜬다", () => {
    render(<Home />);
    const hint = screen.getByRole("region", { name: /처음이신가요/ });
    for (const t of ["닉네임 검색", "요약 탭", "업그레이드 탭", "계산기 탭"]) expect(hint).toHaveTextContent(t);
    fireEvent.click(screen.getByRole("button", { name: "안내 닫기" }));
    expect(screen.queryByRole("region", { name: /처음이신가요/ })).toBeNull();
    cleanup();
    render(<Home />);
    expect(screen.queryByRole("region", { name: /처음이신가요/ })).toBeNull();
  });
  it("최근 검색 지우기", () => {
    addRecent("레테");
    render(<Home />);
    fireEvent.click(screen.getByRole("button", { name: "지우기" }));
    expect(screen.queryByRole("link", { name: "레테" })).toBeNull();
    expect(localStorage.getItem("maple-optimizer:recent")).toBeNull();
  });

  it("모인 경매장 관측 수를 보여준다(공개 통계)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => ({ total: 1234, by_category: {}, first_day: "2026-10-07" }) });
    render(<Home />);
    expect(await screen.findByText(/경매장 관측 1,234건/)).toBeInTheDocument();
  });
});

