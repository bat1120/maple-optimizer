import { describe, expect, it } from "vitest";
import { bookmarkletHref, clipboardText, sampleScouter, scouterInfoUrl } from "./scouter.js";

// 북마크를 MapleScouter가 아닌 곳(2026-10-07 사용자: 우리 사이트에서 눌러 '입력칸을 못 찾았어요')에서 누른 경우 — jsdom 주소는 localhost
describe("bookmarklet on another site", () => {
  it("복사한 캐릭터의 MapleScouter 화면을 새 탭으로 열고, 거기서 한 번 더 누르라고 알린다", async () => {
    document.body.innerHTML = "<main>메이플 장비 최적화</main>";
    Object.assign(navigator, { clipboard: { readText: async () => clipboardText(sampleScouter({ name: "내신부레테", job: "레테", level: 288 })) } });
    const opened = [];
    window.open = (u) => { opened.push(u); return {}; };
    await eval(decodeURIComponent(bookmarkletHref().slice(11))); // eslint-disable-line no-eval
    expect(opened).toEqual([scouterInfoUrl("내신부레테")]);
    expect(document.body.lastElementChild.textContent).toContain("한 번 더");
  });
});
