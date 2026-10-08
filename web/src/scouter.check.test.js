// @vitest-environment-options {"url": "https://maplescouter.com/ko/input"}
import { describe, expect, it } from "vitest";
import { runCheck } from "./scouter.js";

// MapleScouter 직접입력 → [결과] → 요약 창 [상세조회] → /ko/result 보스컷 카드(이미지 extreme_lotus.png + "불가능 41,084 34.52%")
function inputPage(onResult) {
  window.history.pushState({}, "", "/ko/input");
  document.body.innerHTML = `<main><button type="button">결과</button></main>`;
  document.querySelector("button").onclick = () => {
    document.body.insertAdjacentHTML("beforeend", `<div role="dialog"><button type="button">상세조회</button></div>`);
    document.querySelector("[role=dialog] button").onclick = () => setTimeout(() => {
      window.history.pushState({}, "", "/ko/result");
      document.body.innerHTML = `<main><div><div><img alt="boss" src="/boss/extreme_lotus.png"><span>불가능</span><span>41,084</span><span>${onResult()}</span></div></div>
        <div><div><img alt="boss" src="/boss/hard_will.png"><span>솔플 여유컷</span><span>43,638</span><span>814.1%</span></div></div></main>`;
    }, 5);
  };
}
const tick = () => new Promise((r) => setTimeout(r, 2));

describe("MapleScouter 보스 배율 읽기", () => {
  it("[결과] → [상세조회] → 고른 보스 카드의 %를 숫자로", async () => {
    inputPage(() => "34.52%");
    expect(await runCheck(document, "extreme_lotus", tick)).toBe(34.52);
  });
  it("그 보스 카드가 없으면 null", async () => {
    inputPage(() => "34.52%");
    expect(await runCheck(document, "extreme_nothing", tick)).toBeNull();
  });
});

describe("MapleScouter 크확 경고", () => {
  it("'크확 100%미만!!' 창이 뜨면 기다리지 않고 null + 이유를 남긴다", async () => {
    window.history.pushState({}, "", "/ko/input");
    document.body.innerHTML = `<main><button type="button">결과</button></main>`;
    document.querySelector("button").onclick = () => document.body.insertAdjacentHTML("beforeend", `<div role="dialog">크확 100%미만!!<button>Close</button></div>`);
    expect(await runCheck(document, "extreme_lotus", tick)).toBeNull();
    expect(window.__mapleoptWarn).toBe("크확 100% 미만");
  });
});
