import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import FreeSwitch from "./FreeSwitch.jsx";

afterEach(cleanup);

// 2026-11-26 사용자: 전부 보스 기준 — 사냥용 세팅 대비 상승폭(+140.9% 같은 큰 숫자)과 축별 상승폭은 보여 주지 않는다.
// (전에는 '먼저 무료로' 띠가 지금 착용 대비 상승폭을 크게 보여 줬다: 2026-10-11·2026-11-16 결정을 이 결정이 대신한다)
describe("보스 세팅 기준 띠", () => {
  it("지금 착용이 보스 세팅과 다르면: 이 화면이 보스 세팅 기준이라는 것과 어느 프리셋이 다른지만 알린다", () => {
    const breakdown = [
      { axis: "hyper", from: 1, to: 3, relative_to_active: 1.351 },
      { axis: "equipment", from: 1, to: 2, relative_to_active: 1.027 },
    ];
    render(<FreeSwitch ranking={[{ setting: { equipment: 2, hyper: 3, ability: 2 }, relative_to_active: 2.409 }]} breakdown={breakdown} />);
    const r = screen.getByRole("region", { name: "보스 세팅 기준" });
    expect(r).toHaveTextContent("이 화면은 보스 세팅 장비 2 · 하이퍼 3 · 어빌 2 기준이에요");
    expect(r).toHaveTextContent("지금 게임에서는 다른 프리셋을 끼고 있어요(하이퍼 1→3 · 장비 1→2)");
    expect(r.textContent).not.toMatch(/[+]\d|%/);            // 사냥용 세팅 대비 상승폭은 없다
  });

  it("지금 착용이 이미 1위면(또는 순위가 없으면) 그리지 않는다", () => {
    const { container } = render(<FreeSwitch ranking={[{ setting: { equipment: 1, hyper: 1, ability: 1 }, relative_to_active: 1 }]} />);
    expect(container).toBeEmptyDOMElement();
    const { container: c2 } = render(<FreeSwitch ranking={undefined} />);
    expect(c2).toBeEmptyDOMElement();
  });
});
