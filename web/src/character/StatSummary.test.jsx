import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import StatSummary from "./StatSummary.jsx";

const final = { stats: { STR: 4418, DEX: 2893, INT: 2276, LUK: 2271, HP: 1125834.25 }, atk: 4539, matk: 862, dmg: 82, boss: 309, ied: 94.46, cd: 51.15 };

afterEach(cleanup);

describe("주요 스탯", () => {
  // 2026-11-25 운영 화면: 데몬어벤져인데 주스탯인 HP가 빠져 있었다
  it("주스탯이 HP인 직업은 HP를 맨 앞에 보여 준다(되짚은 실제 값)", () => {
    render(<StatSummary final={final} hpMain />);
    const labels = [...document.querySelectorAll("dt")].map((x) => x.textContent);
    expect(labels.slice(0, 2)).toEqual(["HP", "STR"]);
    expect(screen.getByText("1,125,834")).toBeInTheDocument();
  });

  it("다른 직업은 HP를 보여 주지 않는다", () => {
    render(<StatSummary final={final} />);
    expect(screen.queryByText("HP")).toBeNull();
  });
});
