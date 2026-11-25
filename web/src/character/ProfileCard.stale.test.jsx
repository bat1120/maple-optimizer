import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import ProfileCard from "./ProfileCard.jsx";

afterEach(cleanup);
const summary = { character_class: "히어로", level: 280, date: null, profile: { name: "가" }, active_setting: { equipment: 1, hyper: 1, ability: 1 }, combat_power_reference: 1 };
const card = (extra) => render(<ProfileCard name="가" summary={{ ...summary, ...extra }} defense={300} onDefense={() => {}} onRefresh={() => {}} busy={false} />);

describe("데이터 시각 표시", () => {
  it("평소에는 약 15분 전 데이터", () => {
    card({ stale_minutes: null });
    expect(screen.getByText("약 15분 전 데이터")).toBeInTheDocument();
  });

  // 2026-11-25: 넥슨이 막히면 서버가 전에 받아 둔 값으로 답한다 — 얼마나 된 데이터인지 알려야 한다
  it("넥슨이 막혀 오래된 값을 보여 줄 때는 그 사실과 시간을 적는다", () => {
    card({ stale_minutes: 130 });
    expect(screen.getByText("넥슨 조회가 잠시 막혀 2시간 전 데이터를 보여 드려요")).toBeInTheDocument();
  });
});
