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
});
