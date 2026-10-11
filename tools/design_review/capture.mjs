// 디자인 심사 캡처(2026-10-11): 설치된 크롬을 headless로 띄워 CDP로 화면을 찍고, 기계로 잴 수 있는 항목을 판정한다.
// 추가 설치 없음(Node 22+ 내장 WebSocket). 결과: tools/design_review/out/<커밋>-<시각>/ (git 제외)
//   node tools/design_review/capture.mjs [--base http://127.0.0.1:5180] [--name 내신부레테] [--only home,summary]
// 우리 앱(로컬 개발 서버)만 찍는다 — 다른 사이트를 자동으로 열지 않는다(환산주스탯 약관 제15조).
import { spawn, execSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg("base", "http://localhost:5180");
const NAME = arg("name", "내신부레테");
const ONLY = arg("only", "");
const CHROME = arg("chrome", "C:/Program Files/Google/Chrome/Application/chrome.exe");
const PORT = 9333;
const PACE = Number(arg("pace", "3000")); // 촬영 사이 간격(ms) — 우리 서버 IP당 요청 제한(429)에 걸리지 않게
const MAX_H = 3200; // 전체 페이지 캡처 높이 상한(판사가 읽기 좋은 크기)

const c = encodeURIComponent(NAME);
// ready: 이 조건이 참이 되면 다 그려진 것(API 응답까지). act: 찍기 전에 할 동작.
export const SCREENS = [
  { id: "home", url: "/#/", ready: "!!document.querySelector('.hero-search')" },
  { id: "summary", url: `/#/c/${c}?tab=summary`, ready: "document.querySelectorAll('.equip-grid button.slot').length > 5" },
  { id: "summary-tooltip", url: `/#/c/${c}?tab=summary`, ready: "document.querySelectorAll('.equip-grid button.slot').length > 5",
    act: "document.querySelector('.equip-grid button.slot').click()", after: "!!document.querySelector('.tooltip')" },
  { id: "upgrade", url: `/#/c/${c}?tab=upgrade`, ready: "document.querySelectorAll('.rank-card').length > 0", settle: 4000 },
  { id: "calc", url: "/#/calc", ready: "!!document.querySelector('.calc-grid')" },
  { id: "scouter", url: "/#/scouter", ready: "!!document.querySelector('.scouter-page, h1')" },
  { id: "error", url: `/#/c/${encodeURIComponent("없는캐릭터zq9")}?tab=summary`, ready: "!!document.querySelector('[role=alert]')" },
];
const DEVICES = [
  { id: "pc", width: 1366, height: 900, mobile: false },
  { id: "mobile", width: 375, height: 812, mobile: true },
];
const THEMES = ["light", "dark"];

// 기계 판정(페이지 안에서 실행). AI에게 묻지 않는 항목만.
const CHECKS = `(() => {
  const W = document.documentElement.clientWidth, out = { hscroll: document.documentElement.scrollWidth > W + 1 };
  const vis = (el) => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); return r.width > 0 && r.height > 0 && r.bottom > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0; };
  const label = (el) => (el.getAttribute('aria-label') || el.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 40);
  // 화면 밖으로 넘치는 요소(가로)
  out.overflow = [...document.querySelectorAll('body *')].filter(el => { if (!vis(el)) return false; const r = el.getBoundingClientRect();
    if (r.right <= W + 1) return false; let p = el.parentElement; while (p) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden' || o === 'clip') return false; p = p.parentElement; } return true; })
    .slice(0, 10).map(el => el.tagName.toLowerCase() + '.' + [...el.classList].join('.') + ' "' + label(el) + '"');
  // 두 줄로 꺾인 버튼·탭·링크 버튼 — 글자(텍스트 노드)만 기준으로 줄 수를 센다(아이콘 높이 차이는 무시)
  const textTops = (el) => { const tops = []; const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) { if (!w.currentNode.textContent.trim()) continue; const r = document.createRange(); r.selectNodeContents(w.currentNode);
      for (const rc of r.getClientRects()) if (rc.width > 1) tops.push(rc.top); }
    return tops.sort((a, b) => a - b).filter((t, i, a) => i === 0 || t - a[i - 1] > 4).length; };
  out.two_line_click = [...document.querySelectorAll('button, [role=tab], .button-link, .nav-link, .bottom-tabs a')]
    .filter(el => vis(el) && el.innerText.trim() && textTops(el) > 1).slice(0, 10).map(label);
  // 글자 대비(WCAG): 색은 캔버스로 sRGB로 바꿔 계산(oklch 등 어떤 형식이든), 배경은 투명이면 부모로
  const cv = document.createElement('canvas'); cv.width = cv.height = 1; const cx = cv.getContext('2d', { willReadFrequently: true });
  const rgb = (s) => { cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = s; cx.fillRect(0, 0, 1, 1); const d = cx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; };
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const bgOf = (el) => { while (el) { const c = rgb(getComputedStyle(el).backgroundColor); if (c[3] > 0.5) return c; el = el.parentElement; } return rgb(getComputedStyle(document.body).backgroundColor); };
  const low = []; const seen = new Set();
  for (const el of document.querySelectorAll('body *')) {
    if (!vis(el) || ![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
    const s = getComputedStyle(el), fg = rgb(s.color);
    const bg = bgOf(el), L1 = lum(fg), L2 = lum(bg), ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const big = parseFloat(s.fontSize) >= 24 || (parseFloat(s.fontSize) >= 18.66 && parseInt(s.fontWeight) >= 700);
    if (ratio < (big ? 3 : 4.5)) { const k = s.color + '|' + bg.slice(0, 3).join(','); if (!seen.has(k)) { seen.add(k); low.push({ text: label(el), ratio: Math.round(ratio * 100) / 100, color: s.color }); } }
  }
  out.low_contrast = low.slice(0, 15);
  // 휴대폰: 너무 작은 터치 영역(32px 미만)
  out.small_targets = ${"__MOBILE__"} ? [...document.querySelectorAll('button, a[href], input, select, [role=tab]')].filter(el => { if (!vis(el)) return false;
    const t = el.closest('label') || el, r = t.getBoundingClientRect(); return (r.width < 32 || r.height < 32) && !el.closest('p, li, td'); }).slice(0, 15).map(el => label(el) || el.tagName.toLowerCase()) : [];
  out.fonts = [...new Set([...document.querySelectorAll('body *')].filter(vis).map(el => getComputedStyle(el).fontFamily.split(',')[0].replace(/["']/g, '').trim()))];
  out.page_height = document.documentElement.scrollHeight;
  return out;
})()`;

// ── 아주 작은 CDP 클라이언트 ──
class CDP {
  constructor(url) { this.ws = new WebSocket(url); this.id = 0; this.wait = new Map(); this.events = [];
    this.ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && this.wait.has(d.id)) { const { ok, ko } = this.wait.get(d.id); this.wait.delete(d.id); d.error ? ko(new Error(d.error.message)) : ok(d.result); } else this.events.push(d); };
    this.open = new Promise((r, j) => { this.ws.onopen = r; this.ws.onerror = j; }); }
  send(method, params = {}, sessionId) { const id = ++this.id; this.ws.send(JSON.stringify({ id, method, params, sessionId }));
    return new Promise((ok, ko) => this.wait.set(id, { ok, ko })); }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const commit = execSync("git rev-parse --short HEAD").toString().trim() + (execSync("git status --porcelain web").toString().trim() ? "-dirty" : "");
  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const dir = path.join("tools", "design_review", "out", `${commit}-${stamp}`);
  fs.mkdirSync(dir, { recursive: true });
  const prof = fs.mkdtempSync(path.join(os.tmpdir(), "dr-chrome-"));
  const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${prof}`, "--no-first-run",
    "--hide-scrollbars", "--force-device-scale-factor=1", "about:blank"], { stdio: "ignore" });
  let ver;
  for (let i = 0; i < 50 && !ver; i++) { await sleep(200); try { ver = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json(); } catch { /* 아직 */ } }
  if (!ver) throw new Error("크롬 디버그 포트에 연결하지 못했어요");
  const cdp = new CDP(ver.webSocketDebuggerUrl); await cdp.open;
  const manifest = { commit, base: BASE, name: NAME, time: new Date().toISOString(), shots: [] };
  const screens = SCREENS.filter((s) => !ONLY || ONLY.split(",").includes(s.id));
  for (const dev of DEVICES) for (const theme of THEMES) for (const sc of screens) {
    const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
    const { sessionId: S } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
    await cdp.send("Page.enable", {}, S);
    await cdp.send("Emulation.setDeviceMetricsOverride", { width: dev.width, height: dev.height, deviceScaleFactor: 1, mobile: dev.mobile }, S);
    await cdp.send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] }, S);
    if (dev.mobile) await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: true }, S);
    await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: "try{localStorage.setItem('maple-optimizer:theme','system')}catch(e){}" }, S);
    await cdp.send("Page.navigate", { url: BASE + sc.url }, S);
    const evalJs = async (expr) => (await cdp.send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, S)).result.value;
    let ok = false;
    for (let i = 0; i < 300 && !ok; i++) { await sleep(300); try { ok = await evalJs(sc.ready); } catch { /* 이동 중 */ } }
    if (ok && sc.act) { await evalJs(sc.act); for (let i = 0; i < 30; i++) { await sleep(200); if (await evalJs(sc.after)) break; } }
    await sleep(sc.settle || 700); // 글꼴·애니메이션 정착(무거운 화면은 더)
    const checks = await evalJs(CHECKS.replace('"__MOBILE__"', String(dev.mobile)).replace("__MOBILE__", String(dev.mobile)));
    const h = Math.min(checks?.page_height || dev.height, MAX_H);
    const shot = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width: dev.width, height: h, scale: 1 } }, S);
    const file = `${sc.id}__${dev.id}__${theme}.png`;
    fs.writeFileSync(path.join(dir, file), Buffer.from(shot.data, "base64"));
    manifest.shots.push({ screen: sc.id, device: dev.id, theme, file, ready: !!ok, checks });
    console.log(`${ok ? "찍음" : "준비 안 됨(시간 초과)"} ${file}`);
    await cdp.send("Target.closeTarget", { targetId });
    await sleep(PACE);
  }
  fs.writeFileSync(path.join(dir, "manifest.json"), JSON.stringify(manifest, null, 2));
  // 컨택트 시트(사람용): 화면 × (기기·테마) 격자
  const cells = manifest.shots.map((s) => `<figure><img src="${s.file}" loading="lazy"><figcaption>${s.screen} · ${s.device} · ${s.theme}${s.ready ? "" : " · 준비 안 됨"}</figcaption></figure>`).join("");
  fs.writeFileSync(path.join(dir, "contact.html"), `<!doctype html><meta charset="utf-8"><title>디자인 심사 ${commit}</title><style>body{font:13px sans-serif;margin:16px;background:#eee}main{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}figure{margin:0;background:#fff;padding:6px}img{width:100%;height:260px;object-fit:cover;object-position:top}</style><h1>${commit} · ${manifest.time}</h1><main>${cells}</main>`);
  cdp.ws.close(); chrome.kill();
  console.log(`완료: ${dir}`);
}
main().catch((e) => { console.error(e); process.exit(1); });
