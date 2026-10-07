import { afterEach, describe, expect, it } from "vitest";
import { FILL_SOURCE, PREFIX, PREP_SOURCE, bookmarkletHref, clipboardText, runFill, runPrep, scouterInfoUrl } from "./scouter.js";

// MapleScouter 입력 화면 흉내(2026-10-07 실제 구조): <span>라벨</span> → 세 단계 위 div 안에 input
function row(label, values) {
  return `<div class="flex w-full"><div><div><span class="text-sm">${label}</span></div></div>${values.map((v) => `<input type="text" value="${v}">`).join("")}</div>`;
}
function jobRows(job, level) {
  return `<div><div><div><span>레벨</span></div></div><input type="text" value="${level}"></div>
    <div><div><div><span>직업</span></div></div><button type="button" role="combobox">${job}</button></div>`;
}
function page(job = "레테", level = 288) {
  document.body.innerHTML = `<main>${jobRows(job, level)}
    ${row("INT", [5503, 423, 27310])}${row("LUK", [2633, 132, 660])}${row("마력", [3074, 63, 0])}
    ${row("데미지", [91])}${row("최종 데미지", [188.93])}${row("보스 데미지", [438])}${row("방어율 무시", [95.2782])}
    ${row("크리티컬 확률", [103])}${row("마력", [5010])}${row("크리 데미지", [87])}${row("초", [2])}
  </main>`;
}
const vals = () => [...document.querySelectorAll("input")].slice(1).map((i) => i.value); // 0번은 레벨
afterEach(() => { document.body.innerHTML = ""; });

const PAYLOAD = {
  v: 1, to: "에테르넬 메이지글러브", from: "도전자의 장갑", slot: "장갑",
  rows: { main: ["INT"], sub: ["LUK"], attack: "마력" },
  fields: { "INT|기본": 30, "INT|%": 9, "INT|% 미적용": 0, "LUK|기본": 10, "LUK|%": 0, "LUK|% 미적용": 0,
            "마력|기본": 12, "마력|%": 0, "데미지": 0, "보스 데미지": 30, "최종 데미지": 0, "크리티컬 확률": 0, "크리 데미지": 8, "초": 0 },
  ied_add: [40], ied_remove: [],
};

describe("scouter fill (MapleScouter 입력칸 채우기)", () => {
  it("칸 이름으로 찾아 변화량을 더한다(두 번째 '마력' 한 칸짜리는 건드리지 않는다)", () => {
    page();
    const r = runFill(document, PAYLOAD);
    const v = vals();
    expect(v.slice(0, 3)).toEqual(["5533", "432", "27310"]);
    expect(v[3]).toBe("2643");
    expect(v[6]).toBe("3086");
    expect(v[10]).toBe("188.93");                  // 최종 데미지 변화 0 → 그대로
    expect(v[11]).toBe("468");                     // 보스 데미지 438 + 30
    expect(v[14]).toBe("5010");                    // 아래쪽 '마력'(한 칸)은 그대로
    expect(v[15]).toBe("95");                      // 크리 데미지 87 + 8
    expect(r.changed).toBeGreaterThanOrEqual(6);
  });
  it("방무는 곱연산: 100 − (100−기존)×(1−더한 줄)", () => {
    page();
    runFill(document, PAYLOAD);
    expect(Number(vals()[12])).toBeCloseTo(100 - (100 - 95.2782) * 0.6, 4);
  });
  it("칸을 못 찾으면 그 칸만 건너뛰고 알려 준다", () => {
    document.body.innerHTML = `<main>${jobRows("레테", 288)}${row("INT", [1, 2, 3])}</main>`;
    const r = runFill(document, PAYLOAD);
    expect(vals()).toEqual(["31", "11", "3"]);
    expect(r.missing).toContain("보스 데미지");
  });
  it("복사 글: 사람이 읽는 요약 + 북마클릿이 읽는 한 줄(PREFIX JSON)", () => {
    const t = clipboardText(PAYLOAD, { price: 10_000_000_000, delta_pct: 0.84, per_100m: 0.084 });
    expect(t).toContain("장갑: 도전자의 장갑 → 에테르넬 메이지글러브");
    expect(t).toContain("INT +30");
    const line = t.split("\n").find((l) => l.startsWith(PREFIX));
    expect(JSON.parse(line.slice(PREFIX.length))).toEqual(PAYLOAD);
  });
  it("북마클릿 주소는 같은 채우기 코드를 담는다", () => {
    const href = bookmarkletHref();
    expect(href.startsWith("javascript:")).toBe(true);
    expect(decodeURIComponent(href)).toContain(FILL_SOURCE.slice(0, 40));
  });

  it("MapleScouter에 다른 직업이 불러와져 있으면 묻고, 취소하면 아무 칸도 바꾸지 않는다", () => {
    page("메르세데스", 286);
    let asked = "";
    window.confirm = (m) => { asked = m; return false; };
    const r = runFill(document, { ...PAYLOAD, job: "레테", level: 288, name: "내신부레테" });
    expect(asked).toContain("메르세데스");
    expect(asked).toContain("내신부레테");
    expect(r.changed).toBe(0) ;
    expect(r.cancelled).toBe(true);
    expect(vals().slice(0, 3)).toEqual(["5503", "423", "27310"]);
  });
  it("직업 표기 차이(괄호·띄어쓰기)는 같은 직업으로 본다", () => {
    page("아크메이지 (불,독)", 288);
    window.confirm = () => { throw new Error("묻지 않아야 한다"); };
    const r = runFill(document, { ...PAYLOAD, job: "아크메이지(불,독)", level: 288 });
    expect(r.changed).toBeGreaterThan(0);
  });
  it("레벨만 다르면 막지 않고 알려 준다", () => {
    page("레테", 287);
    window.confirm = () => { throw new Error("묻지 않아야 한다"); };
    const r = runFill(document, { ...PAYLOAD, job: "레테", level: 288 });
    expect(r.changed).toBeGreaterThan(0);
    expect(r.note).toContain("레벨");
  });
});


// 내 캐릭터로 자동 전환(2026-10-07 실사이트 구조): info 화면의 '직접입력' 링크 → 입력 화면 + "…@닉네임 (live) 의 스탯으로 교체할까요?" 창
function replaceDialog(who) {
  return `<div role="dialog">검색 캐릭터 스탯으로 교체 최근에 검색한 [KMS] 크로아@${who} (live) 의 스탯으로 교체할까요?
    <button type="button">유지</button><button type="button">교체</button></div>`;
}
function infoPage(who) {
  window.history.pushState({}, "", "/ko/info?name=x");
  document.body.innerHTML = `<main><h1>${who}</h1>${jobRows("레테", 288)}<a href="/ko/input">직접입력</a></main>`; // info 화면에도 '직업' 칸이 있다
  document.querySelector("a").addEventListener("click", (e) => {
    e.preventDefault();
    window.history.pushState({}, "", "/ko/input");
    page("메르세데스", 286);
    document.body.insertAdjacentHTML("beforeend", replaceDialog(who));
    const [keep, swap] = document.querySelectorAll("[role=dialog] button");
    keep.onclick = () => document.querySelector("[role=dialog]").remove();
    swap.onclick = () => { document.querySelector("[role=dialog]").remove(); page("레테", 288); };
  });
}
const fast = () => Promise.resolve();
const ME = { ...PAYLOAD, job: "레테", level: 288, name: "내신부레테" };

describe("scouter prep (내 캐릭터로 교체)", () => {
  it("우리 링크는 그 캐릭터의 info 화면(이름 없으면 입력 화면)", () => {
    expect(scouterInfoUrl("내신부레테")).toBe("https://maplescouter.com/ko/info?name=%EB%82%B4%EC%8B%A0%EB%B6%80%EB%A0%88%ED%85%8C");
    expect(scouterInfoUrl(undefined)).toBe("https://maplescouter.com/ko/input");
  });
  it("info 화면에서: 입력 화면으로 가서 같은 닉네임이면 [교체] → 채우기는 교체된 캐릭터에", async () => {
    infoPage("내신부레테");
    let asked = false;
    window.confirm = () => { asked = true; return false; };
    expect(await runPrep(document, ME, fast)).toEqual({ switched: true, moved: true });
    expect(document.querySelector("[role=dialog]")).toBeNull();
    const r = runFill(document, ME);
    expect(asked).toBe(false);                   // 직업이 맞으니 묻지 않는다
    expect(r.changed).toBeGreaterThan(0);
  });
  it("교체 창의 닉네임이 다르면(이름이 앞부분만 같아도) 누르지 않는다", async () => {
    infoPage("내신부레테2");
    expect(await runPrep(document, ME, fast)).toEqual({ switched: false, moved: true });
    expect(document.querySelector("[role=dialog]")).not.toBeNull();
  });
  it("이미 입력 화면이고 교체 창이 없으면 아무것도 누르지 않는다", async () => {
    window.history.pushState({}, "", "/ko/input");
    page("레테", 288);
    expect(await runPrep(document, ME, fast)).toEqual({ switched: false, moved: false });
  });
  it("복사 글에 이름이 없으면 교체 창이 떠 있어도 누르지 않는다", async () => {
    page("메르세데스", 286);
    document.body.insertAdjacentHTML("beforeend", replaceDialog("내신부레테"));
    expect((await runPrep(document, PAYLOAD, fast)).switched).toBe(false);
  });
  it("교체 뒤 스탯을 불러오는 동안 입력칸이 잠깐 사라져도, 다시 나타나고 레벨이 맞을 때까지 기다렸다 채운다", async () => {
    window.history.pushState({}, "", "/ko/info?name=x");
    document.body.innerHTML = `<main><a href="/ko/input">직접입력</a></main>`;
    document.querySelector("a").addEventListener("click", (e) => {
      e.preventDefault();
      window.history.pushState({}, "", "/ko/input");
      page("메르세데스", 286);
      document.body.insertAdjacentHTML("beforeend", replaceDialog("내신부레테"));
      document.querySelectorAll("[role=dialog] button")[1].onclick = () => {
        document.body.innerHTML = "<main>불러오는 중</main>"; // 교체 창이 닫히고 입력칸이 잠깐 사라진다
        setTimeout(() => page("레테", 288), 30);
      };
    });
    const tick = () => new Promise((r) => setTimeout(r, 2));
    expect((await runPrep(document, ME, tick)).switched).toBe(true);
    expect(runFill(document, ME).changed).toBeGreaterThan(0);
  });
  it("info 화면에 '직접입력' 링크가 없으면 사이트 라우터(next.router.push)로 입력 화면에 간다", async () => {
    window.history.pushState({}, "", "/ko/info?name=x");
    document.body.innerHTML = "<main>정보</main>";
    const pushed = [];
    window.next = { router: { push: (u) => { pushed.push(u); window.history.pushState({}, "", u); page("레테", 288); } } };
    const s = await runPrep(document, ME, fast);
    delete window.next;
    expect(pushed).toEqual(["/ko/input"]);
    expect(s.moved).toBe(true);
  });
  it("입력칸을 하나도 못 찾으면(입력 화면이 아님) 어디서 누르는지 알려 준다", async () => {
    window.history.pushState({}, "", "/ko/info?name=x");
    document.body.innerHTML = `<main><span>보스 데미지</span> 448</main>`; // info 화면: 이름은 있어도 입력칸이 없다, 직접입력 링크도 없음
    Object.assign(navigator, { clipboard: { readText: async () => clipboardText(ME) } });
    await eval(decodeURIComponent(bookmarkletHref().slice(11))); // eslint-disable-line no-eval
    const t = document.body.lastElementChild.textContent;
    expect(t).toContain("입력칸을 못 찾았어요");
    expect(t).toContain("새로 설치");
  });
  it("북마클릿은 전환 코드도 담는다", () => {
    expect(decodeURIComponent(bookmarkletHref())).toContain(PREP_SOURCE.slice(0, 40));
  });
});
