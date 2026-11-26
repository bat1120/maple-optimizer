import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import SettingsRanking from "./SettingsRanking.jsx";

afterEach(cleanup);

// 2026-10-10: 환산주스탯(MapleScouter)과 숫자가 다른 이유를 화면에서 바로 알 수 있게(그쪽은 도핑·버프를 모두 켠 기준)
describe("settings ranking", () => {
  it("환산 주스탯이 이 사이트 기준이라 환산주스탯 사이트와 숫자가 다를 수 있다고 알린다", () => {
    const setting = { equipment: 1, hyper: 1, ability: 1, union: 1, link: 1 };
    render(<SettingsRanking ranking={[{ setting, relative_to_active: 1.01, main_stat_vs_active: 120 }]} />);
    expect(screen.getByText(/환산주스탯\(MapleScouter\)은 도핑·버프를 모두 켠 기준/)).toBeInTheDocument();
  });

  // 2026-10-11 심사 6회차: 조합 글이 2~3줄로 꺾여 비교가 안 됐다 → 프리셋 번호 칸.
  // 2026-11-26 사용자: 전부 보스 기준 — 비교 대상은 지금 착용(사냥용일 수 있다)이 아니라 1위 조합이다
  it("조합은 프리셋 번호 칸으로, 1위와 다른 칸만 diff로 표시하고 숫자도 1위 대비로 보여 준다", () => {
    const best = { equipment: 2, hyper: 3, ability: 1, union: 2, link: 2 };
    const second = { equipment: 2, hyper: 3, ability: 2, union: 3, link: 2 };
    render(<SettingsRanking ranking={[
      { setting: best, index: 1000, relative_to_active: 2.4, main_stat_vs_active: 7000, relative_to_best: 1, main_stat_vs_best: 0 },
      { setting: second, index: 989, relative_to_active: 2.37, main_stat_vs_active: 6900, relative_to_best: 0.989, main_stat_vs_best: -95 },
    ]} />);
    expect(screen.getByRole("columnheader", { name: "1위 대비" })).toBeInTheDocument();
    expect(screen.queryByText("지금 대비")).toBeNull();
    const top = screen.getByRole("row", { name: "장비 2 · 하이퍼 3 · 어빌 1 · 유니온 2 · 링크 2" });
    expect(top.querySelectorAll("td.combo-col.diff")).toHaveLength(0);
    expect(top).toHaveTextContent("기준");
    expect(top.textContent).not.toMatch(/140|7,000/);            // 사냥용 세팅 대비 숫자는 보여 주지 않는다
    const row = screen.getByRole("row", { name: "장비 2 · 하이퍼 3 · 어빌 2 · 유니온 3 · 링크 2" });
    expect([...row.querySelectorAll("td.combo-col.diff")].map((td) => td.getAttribute("aria-label"))).toEqual(["어빌 2", "유니온 3"]);
    expect(row).toHaveTextContent("-1.1%");
    expect(row).toHaveTextContent("-95");
    expect(screen.getByRole("columnheader", { name: "유니온" })).toBeInTheDocument();
  });
});
