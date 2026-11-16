import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import FreeSwitch from "./FreeSwitch.jsx";

describe("먼저 무료로 띠", () => {
  it("보스 세팅 1위가 지금 착용보다 세면 그 조합과 상승폭을 보여 준다", () => {
    render(<FreeSwitch ranking={[{ setting: { equipment: 2, hyper: 3, ability: 2 }, relative_to_active: 2.409 }]} />);
    const r = screen.getByRole("region", { name: "먼저 무료로" });
    expect(r).toHaveTextContent("장비 2 · 하이퍼 3 · 어빌 2");
    expect(r).toHaveTextContent("+140.9%");
  });

  it("어느 프리셋 때문에 오르는지 축별 상승폭을 큰 순으로 보여 준다", () => {
    // 2026-11-16 사용자: +84.7%를 보고 장비가 빠져서인 줄 알았다 — 실제론 하이퍼·유니온 때문
    const breakdown = [
      { axis: "hyper", from: 1, to: 3, relative_to_active: 1.351 },
      { axis: "union", from: 2, to: 1, relative_to_active: 1.348 },
      { axis: "equipment", from: 2, to: 1, relative_to_active: 1.027 },
    ];
    render(<FreeSwitch ranking={[{ setting: { equipment: 1, hyper: 3, ability: 1 }, relative_to_active: 1.847 }]}
                       breakdown={breakdown} />);
    const list = screen.getByRole("list", { name: "어디서 오르나" });
    const rows = within(list).getAllByRole("listitem").map((li) => li.textContent);
    expect(rows).toEqual(["하이퍼 1→3 +35.1%", "유니온 2→1 +34.8%", "장비 2→1 +2.7%"]);
  });

  it("지금 착용이 이미 1위면(또는 순위가 없으면) 그리지 않는다", () => {
    const { container } = render(<FreeSwitch ranking={[{ setting: { equipment: 1, hyper: 1, ability: 1 }, relative_to_active: 1 }]} />);
    expect(container).toBeEmptyDOMElement();
    const { container: c2 } = render(<FreeSwitch ranking={undefined} />);
    expect(c2).toBeEmptyDOMElement();
  });
});
