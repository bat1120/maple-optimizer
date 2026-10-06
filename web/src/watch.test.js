import { describe, expect, it } from "vitest";
import { changedFraction, createWatcher, frameDiff, frameHash, tipHash, tipSame } from "./watch.js";

// 16×16 회색조 프레임 흉내: 값 하나로 채운 배열
const frame = (v, n = 256) => new Array(n).fill(v);

describe("screen watch", () => {
  it("같은 화면이 반복되면 분석하지 않는다 (첫 안정 화면 1회 뒤 0회)", () => {
    const w = createWatcher({ threshold: 8, stableFrames: 2, cooldownMs: 3000 });
    const calls = [0, 1500, 3000, 4500, 6000, 7500].map((t) => w.step(frame(100), t));
    expect(calls.filter(Boolean).length).toBe(1); // 처음 안정되었을 때 한 번만
  });

  it("툴팁이 바뀌면 2프레임 안정된 뒤에 한 번 분석한다", () => {
    const w = createWatcher({ threshold: 8, stableFrames: 2, cooldownMs: 3000 });
    w.step(frame(100), 0); w.step(frame(100), 1500);            // 첫 화면 분석(1회)
    const a = w.step(frame(180), 5000);                          // 바뀜 — 아직 안정 전
    const b = w.step(frame(181), 6500);                          // 안정 → 분석
    const c = w.step(frame(181), 8000);                          // 같은 화면 → 없음
    expect([a, b, c]).toEqual([false, true, false]);
  });

  it("쿨다운 3초 안에는 화면이 바뀌어도 다시 부르지 않는다", () => {
    const w = createWatcher({ threshold: 8, stableFrames: 2, cooldownMs: 3000 });
    w.step(frame(100), 0); expect(w.step(frame(100), 500)).toBe(true);
    w.step(frame(200), 1000);
    expect(w.step(frame(200), 1500)).toBe(false);                // 안정됐지만 쿨다운
    expect(w.step(frame(200), 3600)).toBe(true);                 // 쿨다운 지난 뒤
  });

  it("frameHash는 RGBA 픽셀을 16×16 회색조로 줄이고 frameDiff는 평균 절대 차이", () => {
    const w = 32, h = 32, data = new Uint8ClampedArray(w * h * 4).fill(255);
    const hash = frameHash({ width: w, height: h, data });
    expect(hash).toHaveLength(256);
    expect(hash.every((v) => v === 255)).toBe(true);
    expect(frameDiff(frame(10), frame(14))).toBe(4);
  });
  it("툴팁 부분만 바뀌어도(평균 차이는 작아도) 바뀐 화면으로 본다 — 2026-10-06 실측: 망토→신발 평균 3.8", () => {
    const w = createWatcher({ threshold: 6, stableFrames: 2, cooldownMs: 0, minChanged: 0.03 });
    const a = frame(100, 1024);
    const b = a.map((v, i) => (i < 60 ? 160 : v));               // 1024칸 중 60칸(5.9%)만 크게 바뀜, 평균 차이 3.5
    expect(frameDiff(a, b)).toBeLessThan(6);
    w.step(a, 0); expect(w.step(a, 500)).toBe(true);
    w.step(b, 1000);
    expect(w.step(b, 1500)).toBe(true);
  });

  it("마우스 커서만 움직인 정도(몇 칸)는 바뀐 화면이 아니다", () => {
    const w = createWatcher({ threshold: 6, stableFrames: 2, cooldownMs: 0, minChanged: 0.03 });
    const a = frame(100, 1024);
    const b = a.map((v, i) => (i < 6 ? 250 : v));                // 6칸(0.6%)
    w.step(a, 0); w.step(a, 500);
    w.step(b, 1000);
    expect(w.step(b, 1500)).toBe(false);
  });

  it("changedFraction은 크게 바뀐 칸의 비율", () => {
    expect(changedFraction(frame(100, 100), frame(100, 100).map((v, i) => (i < 5 ? 200 : v)))).toBe(0.05);
  });

});

// 256×144 RGBA 화면 흉내: 배경색 bg, (x0,y0)-(x1,y1)에 남회색 툴팁, 툴팁 안 글자 줄은 textRows(행 번호 집합)
function screenData({ bg = [200, 60, 220], tip = null, text = new Set(), effect = null } = {}) {
  const w = 256, h = 144, data = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let c = bg;
    if (effect && x >= effect[0] && x < effect[2] && y >= effect[1] && y < effect[3]) c = effect[4];
    if (tip && x >= tip[0] && x < tip[2] && y >= tip[1] && y < tip[3]) c = text.has(y) && x % 3 ? [235, 235, 235] : [50, 57, 66];
    const i = (y * w + x) * 4; data[i] = c[0]; data[i + 1] = c[1]; data[i + 2] = c[2]; data[i + 3] = 255;
  }
  return { width: w, height: h, data };
}

describe("tooltip-aware watch (2026-10-06: 소환수·이펙트가 움직이면 툴팁을 띄워도 '안 멈춤' — 실측 0/12)", () => {
  const box = [150, 20, 230, 120];
  it("툴팁을 띄운 채 배경 이펙트만 움직이면 같은 화면으로 본다", () => {
    const a = tipHash(screenData({ tip: box, text: new Set([30, 40]), effect: [0, 0, 100, 140, [250, 200, 30]] }));
    const b = tipHash(screenData({ tip: box, text: new Set([30, 40]), effect: [40, 10, 140, 140, [20, 240, 90]] }));
    expect(tipSame(a, b)).toBe(true);
  });
  it("툴팁 글자가 바뀌면(다른 템) 다른 화면으로 본다", () => {
    const a = tipHash(screenData({ tip: box, text: new Set([30, 40, 50]) }));
    const b = tipHash(screenData({ tip: box, text: new Set([35, 60, 70, 80, 90]) }));
    expect(tipSame(a, b)).toBe(false);
  });
  it("툴팁이 새로 뜨면 다른 화면으로 본다", () => {
    expect(tipSame(tipHash(screenData()), tipHash(screenData({ tip: box })))).toBe(false);
  });
  it("watcher에 same을 주면 그 기준으로 안정·변화를 판단한다", () => {
    const w = createWatcher({ stableFrames: 2, cooldownMs: 0, same: tipSame });
    const t1 = (eff) => tipHash(screenData({ tip: box, text: new Set([30]), effect: eff }));
    w.step(t1(null), 0);
    expect(w.step(t1([0, 0, 90, 140, [250, 200, 30]]), 250)).toBe(true);   // 이펙트가 움직여도 안정 → 보냄
    expect(w.step(t1([50, 0, 140, 140, [20, 240, 90]]), 500)).toBe(false); // 같은 툴팁 → 다시 안 보냄
  });
});

