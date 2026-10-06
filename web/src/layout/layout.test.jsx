import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import TopBar from "./TopBar.jsx";
import BottomTabs from "./BottomTabs.jsx";

afterEach(() => { cleanup(); localStorage.clear(); window.location.hash = ""; document.documentElement.removeAttribute("data-theme"); });

describe("top bar", () => {
  it("로고는 첫 화면으로, 검색하면 캐릭터 주소로 간다", () => {
    render(<TopBar route={{ page: "calc" }} />);
    expect(screen.getByRole("link", { name: /메이플 장비 최적화/ })).toHaveAttribute("href", "#/");
    fireEvent.change(screen.getByRole("searchbox", { name: "캐릭터 검색" }), { target: { value: "내신부레테" } });
    fireEvent.submit(screen.getByRole("search"));
    expect(window.location.hash).toBe(`#/c/${encodeURIComponent("내신부레테")}`);
  });
  it("첫 화면에서는 작은 검색창을 숨긴다(가운데 큰 검색창이 있다)", () => {
    render(<TopBar route={{ page: "home" }} />);
    expect(screen.queryByRole("searchbox")).toBeNull();
  });
  it("테마 버튼: 시스템 → 라이트 → 다크, 저장·적용", () => {
    render(<TopBar route={{ page: "home" }} />);
    const b = screen.getByRole("button", { name: /테마/ });
    expect(b).toHaveTextContent("시스템");
    fireEvent.click(b);
    expect(b).toHaveTextContent("라이트");
    expect(document.documentElement.dataset.theme).toBe("light");
    fireEvent.click(b);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("maple-optimizer:theme")).toBe("dark");
  });
});

describe("bottom tabs", () => {
  it("탭 3개가 캐릭터 주소로 연결되고 현재 탭이 표시된다", () => {
    render(<BottomTabs route={{ page: "character", name: "레테", tab: "upgrade" }} />);
    const links = screen.getAllByRole("link");
    expect(links.map((a) => a.textContent)).toEqual(["요약", "업그레이드", "계산기"]);
    expect(links[1]).toHaveAttribute("aria-current", "page");
    expect(links[2]).toHaveAttribute("href", `#/c/${encodeURIComponent("레테")}?tab=calc`);
  });
});
