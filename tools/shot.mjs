// 화면 한 장 찍기(결과 보고서용). 설치된 크롬을 화면 없이 띄워 주소를 열고, 고른 부분만 잘라 JPEG으로 저장한다.
//   node tools/shot.mjs --url <주소> --out <파일.jpg> [--width 1100] [--selector ".plan-panel"] [--wait "글자"] [--pad 8] [--max-height 1400] [--click "레전드리 3줄|보기"]
// --selector: 그 요소만 자른다(없으면 화면 위에서부터 --max-height까지). --wait: 이 글자가 화면에 보일 때까지 기다린다(최대 30초).
// 운영 주소를 열면 서버가 넥슨을 부를 수 있다(캐시가 비었을 때 캐릭터 1회 조회) — 한 번에 여러 캐릭터를 찍지 않는다.
import fs from "node:fs";
import { spawnSync } from "node:child_process";

if (typeof WebSocket === "undefined") { // Node 20: 내장 WebSocket이 꺼져 있다 — 켜서 다시 실행
  const again = spawnSync(process.execPath, ["--experimental-websocket", ...process.argv.slice(1)], { stdio: "inherit" });
  process.exit(again.status ?? 1);
}
const { launchChrome, sleep } = await import("./cdp.mjs");

const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d; };
const url = arg("url"), out = arg("out");
if (!url || !out) { console.error("--url 과 --out 이 필요해요"); process.exit(2); }
const width = Number(arg("width", "1100")), pad = Number(arg("pad", "8")), maxH = Number(arg("max-height", "1400"));
const selector = arg("selector", ""), waitText = arg("wait", "");
const clicks = arg("click", "").split("|").filter(Boolean);

const chrome = await launchChrome({ port: 9335 });
let code = 0;
try {
  const { cdp } = chrome;
  const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
  const { sessionId: S } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
  for (const domain of ["Page", "Runtime"]) await cdp.send(`${domain}.enable`, {}, S);
  await cdp.send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width < 600 }, S);
  await cdp.send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] }, S);
  const evalJs = async (expr) => (await cdp.send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, S)).result.value;
  await cdp.send("Page.navigate", { url }, S);
  const want = JSON.stringify(waitText);
  let ready = false;
  for (let i = 0; i < 100 && !ready; i++) {
    await sleep(300);
    try {
      ready = await evalJs(`document.readyState === "complete" && (${want} === "" || document.body.innerText.includes(${want}))`
        + (selector ? ` && !!document.querySelector(${JSON.stringify(selector)})` : ""));
    } catch { /* 이동 중 */ }
  }
  if (!ready) { console.error(`기다린 내용이 나오지 않았어요: ${waitText || selector || url}`); code = 1; }
  // --click "글자1|글자2": 그 글자가 든 버튼·탭·체크 칸(aria-label 포함)을 차례로 누른다(펼친 화면을 찍을 때)
  for (const label of clicks) {
    const hit = await evalJs(`(() => { const want = ${JSON.stringify(label)};
      const els = [...document.querySelectorAll("button, [role=tab], input[type=checkbox], summary")];
      const e = els.find((x) => (x.getAttribute("aria-label") || x.innerText || "").includes(want)); if (!e) return false; e.click(); return true; })()`);
    if (!hit) { console.error(`누를 곳을 찾지 못했어요: ${label}`); code = 1; }
    await sleep(500);
  }
  await sleep(800); // 글꼴·그림이 자리 잡을 시간
  let clip = { x: 0, y: 0, width, height: Math.min(await evalJs("document.documentElement.scrollHeight"), maxH), scale: 1 };
  if (selector) {
    const r = await evalJs(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); if (!e) return null;
      const b = e.getBoundingClientRect(); return { x: b.left + scrollX, y: b.top + scrollY, w: b.width, h: b.height }; })()`);
    if (r) clip = { x: Math.max(0, r.x - pad), y: Math.max(0, r.y - pad), width: Math.min(width, r.w + pad * 2), height: Math.min(r.h + pad * 2, maxH), scale: 1 };
    else { console.error(`요소를 찾지 못했어요: ${selector}`); code = 1; }
  }
  const shot = await cdp.send("Page.captureScreenshot", { format: "jpeg", quality: 82, captureBeyondViewport: true, clip }, S);
  fs.writeFileSync(out, Buffer.from(shot.data, "base64"));
  console.log(`저장: ${out} (${Math.round(clip.width)}x${Math.round(clip.height)})`);
} finally {
  chrome.close();
}
process.exit(code);
