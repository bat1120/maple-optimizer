import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import Scouter from "./Scouter.jsx";

afterEach(cleanup);

describe("scouter guide page", () => {
  it("끌어서 북마크에 놓는 '환산 채우기' 버튼과 순서 안내", () => {
    render(<Scouter />);
    const link = screen.getByRole("link", { name: "환산 채우기" });
    expect(link.getAttribute("href").startsWith("javascript:")).toBe(true);
    expect(screen.getByText(/내 캐릭터 스탯으로 교체/)).toBeInTheDocument();
    expect(screen.getByText(/환산용 복사/)).toBeInTheDocument();
  });

  it("[테스트용 복사]: 경매장 데이터 없이 견본(보스 +10%, 크뎀 +5%)을 복사한다", async () => {
    const { act, fireEvent } = await import("@testing-library/react");
    const writeText = (await import("vitest")).vi.fn().mockResolvedValue();
    Object.assign(navigator, { clipboard: { writeText } });
    render(<Scouter />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "테스트용 복사" })); });
    const text = writeText.mock.calls[0][0];
    const json = JSON.parse(text.split("\n").find((l) => l.startsWith("MAPLEOPT1 ")).slice(10));
    expect(json.fields).toEqual({ "보스 데미지": 10, "크리 데미지": 5 });
    expect(screen.getByText(/견본을 복사했어요/)).toBeInTheDocument();
  });

  it("MapleScouter 입력 화면으로 가는 링크(새 탭)", () => {
    render(<Scouter />);
    const a = screen.getAllByRole("link", { name: /MapleScouter 입력 화면 열기/ })[0];
    expect(a).toHaveAttribute("href", "https://maplescouter.com/ko/input");
    expect(a).toHaveAttribute("target", "_blank");
    expect(a.getAttribute("rel")).toContain("noopener");
  });
  it("크롬 확장 설치 안내(개발자 모드 · extension 폴더)", () => {
    render(<Scouter />);
    expect(screen.getByRole("heading", { name: /크롬 확장 프로그램/ })).toBeInTheDocument();
    expect(screen.getByText("chrome://extensions")).toBeInTheDocument();
  });
});
