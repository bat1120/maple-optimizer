import { describe, expect, it } from "vitest";
import { changedFraction, createWatcher, frameDiff, frameHash } from "./watch.js";

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
