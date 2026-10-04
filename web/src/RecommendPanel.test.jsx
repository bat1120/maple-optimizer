import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import RecommendPanel from "./RecommendPanel.jsx";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const body = {
  evaluation_setting: { equipment: 2, hyper: 3, ability: 2, union: 3, link: 2 },
  boss: { name: "기준", defense: 300 },
  note: "윗잠만 목표 잠재로 바꾼 같은 템 기준이에요.",
  recommendations: [
    { slot: "보조무기", category: "보조무기", target_potentials: ["마력 +12%", "보스 몬스터 데미지 +40%", "마력 +9%"],
      min_starforce: 0, delta_pct: 6.6118, kind: "에디", grade: "유니크", lines_good: 3, kept: [], search: "보조무기 · 잠재 마력 +12% / 보스 몬스터 데미지 +40% / 마력 +9% · 0성 이상",
      current: { name: "녹스 마법깃펜", starforce: 0, potentials: ["보스 몬스터 데미지 +40%", "보스 몬스터 데미지 +35%"] } },
    { slot: "반지1", category: "반지", target_potentials: ["INT +12%", "INT +9%", "INT +9%"],
      min_starforce: 17, delta_pct: 1.2, kind: "잠재", grade: "레전드리", lines_good: 3, kept: ["스킬 재사용 대기시간 -2초"], search: "반지 · 잠재 INT +12% / INT +9% / INT +9% · 17성 이상",
      current: { name: "이터널 플레임 링", starforce: 17, potentials: ["INT +12%", "INT +9%", "최대 HP +9%"] } },
  ],
};

describe("recommend panel", () => {
  it("보스 세팅 기준 검색 조건 카드를 실딜 상승과 함께 보여준다", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => body });
    render(<RecommendPanel name="내신부레테" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "검색 추천 받기" })); });
    expect(f.mock.calls[0][0]).toBe(`/api/character/${encodeURIComponent("내신부레테")}/recommend?boss_defense=300&top=5`);
    const cards = screen.getAllByRole("listitem");
    expect(cards).toHaveLength(2);
    expect(cards[0]).toHaveTextContent("보조무기");
    expect(cards[0]).toHaveTextContent("에디 유니크 3줄");
    expect(cards[0]).toHaveTextContent("실딜 +6.612%");
    expect(cards[0]).toHaveTextContent("마력 +12% / 보스 몬스터 데미지 +40% / 마력 +9%");
    expect(cards[0]).toHaveTextContent("지금: 녹스 마법깃펜");
    expect(cards[1]).toHaveTextContent("17성 이상");
    expect(screen.getByText(/장비 2 · 하이퍼 3/)).toBeInTheDocument();
  });

  it("캐릭터를 조회하기 전에는 버튼이 꺼져 있다", () => {
    render(<RecommendPanel name="" defense={300} />);
    expect(screen.getByRole("button", { name: "검색 추천 받기" })).toBeDisabled();
  });

  it("추천이 없으면 안내한다", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => ({ ...body, recommendations: [] }) });
    render(<RecommendPanel name="x" defense={300} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "검색 추천 받기" })); });
    expect(screen.getByText(/잠재만 바꿔서 오르는 부위가 없어요/)).toBeInTheDocument();
  });

  it("다음 단계와 유지한 쿨감 줄을 보여주고, 쿨감 환산값을 넣으면 함께 보낸다", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => body });
    render(<RecommendPanel name="내신부레테" defense={300} />);
    fireEvent.change(screen.getByLabelText("쿨감 1초 = 주스탯 %"), { target: { value: "8" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "검색 추천 받기" })); });
    expect(f.mock.calls[0][0]).toBe(`/api/character/${encodeURIComponent("내신부레테")}/recommend?boss_defense=300&top=5&cooldown_main_pct=8`);
    const cards = screen.getAllByRole("listitem");
    expect(cards[1]).toHaveTextContent("잠재 레전드리 3줄");
    expect(cards[1]).toHaveTextContent("유지: 스킬 재사용 대기시간 -2초");
  });
});
