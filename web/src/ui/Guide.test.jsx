import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { EmptyState, ErrorState, HowTo, PanelHead } from "./Guide.jsx";
import Calc from "../pages/Calc.jsx";

afterEach(cleanup);

describe("안내 조각", () => {
  it("패널 머리말: 제목 + 할 수 있는 것 한 줄 + 동작", () => {
    render(<PanelHead title="보스 세팅 순위" subtitle="한 줄 설명"><button type="button">다시 계산</button></PanelHead>);
    expect(screen.getByRole("heading", { name: "보스 세팅 순위" })).toBeInTheDocument();
    expect(screen.getByText("한 줄 설명")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다시 계산" })).toBeInTheDocument();
  });
  it("사용 방법: 접혀 있고, 번호 단계를 순서대로 보여준다", () => {
    const { container } = render(<HowTo steps={["하나", "둘", "셋"]} />);
    const d = container.querySelector("details");
    expect(d.open).toBe(false);
    expect(within(d).getByText("사용 방법")).toBeInTheDocument();
    expect([...d.querySelectorAll("ol.steps > li")].map((li) => li.textContent)).toEqual(["하나", "둘", "셋"]);
  });
  it("빈 상태·오류 상태", () => {
    const retry = vi.fn();
    render(<><EmptyState title="아직 없어요">다음에 할 일</EmptyState><ErrorState message="서버 문구" onRetry={retry} /></>);
    expect(screen.getByText("아직 없어요")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("서버 문구");
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(retry).toHaveBeenCalledOnce();
  });
  it("계산기 페이지에 사용 방법과 패널별 한 줄 설명이 있다", () => {
    render(<Calc />);
    expect(screen.getByText("사용 방법")).toBeInTheDocument();
    for (const t of ["스타포스 비용", "잠재 재설정", "매물 vs 직작"]) {
      expect(screen.getByRole("heading", { name: t })).toBeInTheDocument();
    }
    expect(screen.getByText(/공식 확률표로 목표 옵션이 나올 확률/)).toBeInTheDocument();
  });
});
