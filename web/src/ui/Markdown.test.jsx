import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Markdown, { blocks } from "./Markdown.jsx";

const ANSWER = `**먼저 귀고리 추옵을 올리는 게 효율적이에요.** 억당 효율이 가장 높아요.

| 순서 | 업그레이드 | 실딜 상승 |
|---|---|---:|
| 1 | 에스텔라 이어링 추옵 재설정 | +0.16% |
| 2 | 도미네이터 펜던트 추옵 재설정 | **+0.13%** |

## 실행 순서
1. 저비용부터
2. 그다음 스타포스

- 방어율 300% 기준
- 프리셋은 그대로`;

describe("Markdown", () => {
  it("답변을 문단·표·제목·목록으로 나눈다", () => {
    expect(blocks(ANSWER).map((b) => b.type)).toEqual(["para", "table", "heading", "numbers", "bullets"]);
  });

  it("마크다운 기호가 화면 글자에 남지 않는다", () => {
    const { container } = render(<Markdown text={ANSWER} />);
    expect(container.textContent).not.toMatch(/\*\*|\||^#|---/m);
    expect(screen.getByText("먼저 귀고리 추옵을 올리는 게 효율적이에요.").tagName).toBe("STRONG");
    expect(container.querySelectorAll("table tbody tr")).toHaveLength(2);
    expect(container.querySelectorAll("th")).toHaveLength(3);
    expect(screen.getByText("+0.13%").tagName).toBe("STRONG");
    expect(container.querySelectorAll("ol li")).toHaveLength(2);
    expect(container.querySelectorAll("ul li")).toHaveLength(2);
  });

  it("평범한 글은 그대로, 줄바꿈은 유지한다", () => {
    const { container } = render(<Markdown text={"첫 줄\n둘째 줄\n\n가격 a|b 는 표가 아니다"} />);
    expect(container.querySelectorAll("p")).toHaveLength(2);
    expect(container.querySelectorAll("br")).toHaveLength(1);
    expect(container.querySelector("table")).toBeNull();
    expect(container.textContent).toContain("가격 a|b 는 표가 아니다");
  });

  it("백틱은 기호만 떼고 글자는 남긴다", () => {
    const { container } = render(<Markdown text={"**`도미네이터 펜던트` 추옵부터** 추천해요. `마이스터링` 18→19성"} />);
    expect(container.textContent).toBe("도미네이터 펜던트 추옵부터 추천해요. 마이스터링 18→19성");
    expect(screen.getByText("도미네이터 펜던트 추옵부터").tagName).toBe("STRONG");
  });

  it("빈 답변에도 깨지지 않는다", () => {
    const { container } = render(<Markdown text={undefined} />);
    expect(container.querySelector(".answer").children).toHaveLength(0);
  });
});
