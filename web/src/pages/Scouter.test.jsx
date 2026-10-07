import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import Scouter from "./Scouter.jsx";

afterEach(cleanup);

describe("scouter guide page", () => {
  it("끌어서 북마크에 놓는 '환산 채우기' 버튼과 순서 안내", () => {
    render(<Scouter />);
    const link = screen.getByRole("link", { name: "환산 채우기" });
    expect(link.getAttribute("href").startsWith("javascript:")).toBe(true);
    expect(screen.getByText(/검색 캐릭터 불러오기/)).toBeInTheDocument();
    expect(screen.getByText(/환산용 복사/)).toBeInTheDocument();
  });
});
