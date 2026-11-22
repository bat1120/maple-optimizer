// 설치된 크롬을 headless로 띄워 CDP(Chrome DevTools Protocol)로 조종하는 아주 작은 클라이언트. 추가 설치 없음.
// 쓰는 곳: tools/design_review/capture.mjs(디자인 심사 캡처), tools/verify_ui/run.mjs(화면 검증 증거).
// Node 22+는 WebSocket이 내장이다. Node 20은 `node --experimental-websocket`으로 돌린다(verify_ui/run.mjs는 알아서 다시 실행한다).
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export class CDP {
  constructor(url) { this.ws = new WebSocket(url); this.id = 0; this.wait = new Map(); this.events = [];
    this.ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && this.wait.has(d.id)) { const { ok, ko } = this.wait.get(d.id); this.wait.delete(d.id); d.error ? ko(new Error(d.error.message)) : ok(d.result); } else this.events.push(d); };
    this.open = new Promise((r, j) => { this.ws.onopen = r; this.ws.onerror = j; }); }
  send(method, params = {}, sessionId) { const id = ++this.id; this.ws.send(JSON.stringify({ id, method, params, sessionId }));
    return new Promise((ok, ko) => this.wait.set(id, { ok, ko })); }
}

const CHROME_CANDIDATES = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium-browser",
  "/usr/bin/chromium",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
];

export function findChrome() {
  const found = [process.env.CHROME, ...CHROME_CANDIDATES].find((p) => p && fs.existsSync(p));
  if (!found) throw new Error("크롬을 찾지 못했어요 — CHROME 환경변수에 실행 파일 경로를 넣어 주세요");
  return found;
}

export async function launchChrome({ chromePath = findChrome(), port = 9333 } = {}) {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "mo-chrome-"));
  const args = ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run",
    "--hide-scrollbars", "--force-device-scale-factor=1"];
  if (process.platform === "linux") args.push("--no-sandbox"); // CI 러너(컨테이너)에서는 샌드박스를 못 쓴다
  const chrome = spawn(chromePath, [...args, "about:blank"], { stdio: "ignore" });
  let version;
  for (let i = 0; i < 50 && !version; i++) { await sleep(200); try { version = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json(); } catch { /* 아직 */ } }
  if (!version) { chrome.kill(); throw new Error("크롬 디버그 포트에 연결하지 못했어요"); }
  const cdp = new CDP(version.webSocketDebuggerUrl);
  await cdp.open;
  return { cdp, close: () => { cdp.ws.close(); chrome.kill(); } };
}
