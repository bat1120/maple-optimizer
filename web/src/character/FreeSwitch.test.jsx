import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import FreeSwitch from "./FreeSwitch.jsx";

describe("먼저 무료로 띠", () => {
  it("보스 세팅 1위가 지금 착용보다 세면 그 조합과 상승폭을 보여 준다", () => {
    render(<FreeSwitch ranking={[{ setting: { equipment: 2, hyper: 3, ability: 2 }, relative_to_active: 2.409 }]} />);
    const r = screen.getByRole("region", { name: "먼저 무료로" });
    expect(r).toHaveTextContent("장비 2 · 하이퍼 3 · 어빌 2");
    expect(r).toHaveTextContent("+140.9%");
  });

  it("지금 착용이 이미 1위면(또는 순위가 없으면) 그리지 않는다", () => {
    const { container } = render(<FreeSwitch ranking={[{ setting: { equipment: 1, hyper: 1, ability: 1 }, relative_to_active: 1 }]} />);
    expect(container).toBeEmptyDOMElement();
    const { container: c2 } = render(<FreeSwitch ranking={undefined} />);
    expect(c2).toBeEmptyDOMElement();
  });
});
