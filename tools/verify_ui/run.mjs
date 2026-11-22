// 화면 검증 증거: 픽스처 서버로 실제 앱을 띄우고, 기능 지도(features.json)대로 열어 확인한 뒤 화면을 찍는다.
// 사람은 코드 대신 결과 페이지(index.html)를 본다. 넥슨·AI 키가 필요 없고 추가 설치도 없다(설치된 크롬 사용).
//   node tools/verify_ui/run.mjs [--only home,summary] [--no-build] [--port 8765] [--out <폴더>] [--features <기능 지도.json>] [--with-ai]
// --with-ai(이 PC 전용, 비용 발생): AI 상담을 실제 모델에 연결해 requires가 "ai"인 기능까지 확인한다. 없으면 그 기능은 건너뛴다.
// 결과: tools/verify_ui/out/<커밋>-<시각>/ (git 제외) — index.html(사람용), result.json(기계용), 스크린샷.
// 종료 코드: 모두 통과 0, 하나라도 실패 1.
import { execSync, spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

if (typeof WebSocket === "undefined") { // Node 20: 내장 WebSocket이 꺼져 있다 — 켜서 다시 실행
  const again = spawnSync(process.execPath, ["--experimental-websocket", ...process.argv.slice(1)], { stdio: "inherit" });
  process.exit(again.status ?? 1);
}

const { launchChrome, sleep } = await import("../cdp.mjs");

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d; };
const flag = (k) => process.argv.includes(`--${k}`);
const PORT = Number(arg("port", "8765"));
const BASE = `http://127.0.0.1:${PORT}`;
const ONLY = arg("only", "");
const WITH_AI = flag("with-ai");
const MAX_H = 3200;
const DEVICES = [
  { id: "pc", label: "PC 1366px", width: 1366, height: 900, mobile: false },
  { id: "mobile", label: "휴대폰 375px", width: 375, height: 812, mobile: true },
];

const map = JSON.parse(fs.readFileSync(arg("features", path.join(HERE, "features.json")), "utf-8"));
const fill = (s) => s.replaceAll("{character}", map.character);
const pageUrl = (u) => BASE + fill(u).replace(/[^\x00-\x7F]+/g, encodeURIComponent);
const html = (s) => String(s).replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));

function startServer() {
  const child = spawn("uv", ["run", "python", path.join("tools", "verify_ui", "serve.py"), "--port", String(PORT), ...(WITH_AI ? ["--with-ai"] : [])],
    { cwd: ROOT, stdio: ["ignore", "ignore", "pipe"], env: { ...process.env, PYTHONUTF8: "1" } });
  let log = "";
  child.stderr.on("data", (d) => { log = (log + d).slice(-4000); });
  const stop = () => {
    if (process.platform === "win32") spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    else child.kill();
  };
  return { child, stop, log: () => log };
}

async function waitHealthy(server) {
  for (let i = 0; i < 120; i++) {
    if (server.child.exitCode !== null) throw new Error(`검증 서버가 뜨지 못했어요:\n${server.log()}`);
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch { /* 아직 */ }
    await sleep(500);
  }
  throw new Error(`검증 서버가 60초 안에 응답하지 않았어요:\n${server.log()}`);
}

async function runFeature(cdp, feature, device) {
  const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
  const { sessionId: S } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
  const firstEvent = cdp.events.length;
  for (const domain of ["Page", "Runtime", "Network", "Log"]) await cdp.send(`${domain}.enable`, {}, S);
  await cdp.send("Emulation.setDeviceMetricsOverride", { width: device.width, height: device.height, deviceScaleFactor: 1, mobile: device.mobile }, S);
  await cdp.send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] }, S);
  if (device.mobile) await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: true }, S);
  const evalJs = async (expr) => (await cdp.send("Runtime.evaluate", { expression: fill(expr), returnByValue: true, awaitPromise: true }, S)).result.value;
  const until = async (expr, tries = 100) => {
    for (let i = 0; i < tries; i++) { await sleep(300); try { if (await evalJs(expr)) return true; } catch { /* 이동 중 */ } }
    return false;
  };

  const problems = [];
  await cdp.send("Page.navigate", { url: pageUrl(feature.url) }, S);
  const ready = await until(feature.ready);
  if (!ready) problems.push("화면이 다 그려지지 않았어요(30초 초과)");

  for (const step of ready ? feature.steps || [] : []) {
    if (step.js) await evalJs(step.js);
    if (step.type) await cdp.send("Input.insertText", { text: fill(step.type) }, S);
    if (step.press === "Enter") {
      const key = { key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, text: "\r" };
      await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", ...key }, S);
      await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", ...key }, S);
    }
    if (step.wait && !(await until(step.wait, Math.ceil((step.timeout || 18) / 0.3)))) problems.push(`동작 뒤 기다린 상태가 오지 않았어요: ${step.wait}`);
  }
  await sleep(feature.settle || 700);

  const checks = [];
  for (const e of ready ? feature.expect || [] : []) {
    let ok = false;
    try { ok = !!(await evalJs(e.js)); } catch { ok = false; }
    checks.push({ what: e.what, ok });
    if (!ok) problems.push(`확인 실패: ${e.what}`);
  }

  const allowed = new Set(feature.allow_status || []);
  for (const ev of cdp.events.slice(firstEvent).filter((x) => x.sessionId === S)) {
    if (ev.method === "Runtime.exceptionThrown") problems.push(`화면 오류: ${ev.params.exceptionDetails.exception?.description?.split("\n")[0] || ev.params.exceptionDetails.text}`);
    if (ev.method === "Network.responseReceived" && ev.params.response.url.includes("/api/") && ev.params.response.status >= 400
        && !allowed.has(ev.params.response.status)) {
      problems.push(`API ${ev.params.response.status}: ${decodeURIComponent(new URL(ev.params.response.url).pathname)}`);
    }
    if (ev.method === "Network.loadingFailed" && !ev.params.canceled) problems.push(`요청 실패: ${ev.params.errorText}`);
  }

  const height = Math.min((await evalJs("document.documentElement.scrollHeight")) || device.height, MAX_H);
  const shot = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width: device.width, height, scale: 1 } }, S);
  await cdp.send("Target.closeTarget", { targetId });
  return { device: device.id, ok: problems.length === 0, problems: [...new Set(problems)], checks, png: Buffer.from(shot.data, "base64") };
}

function evidencePage(result) {
  const failed = result.features.filter((f) => !f.ok);
  const cards = result.features.map((f) => `
    <section class="card ${f.ok ? "pass" : "fail"}" id="${html(f.id)}">
      <h2><span class="badge">${f.ok ? "통과" : "실패"}</span> ${html(f.title)}</h2>
      <p class="url">${html(f.url)}</p>
      ${f.runs.flatMap((r) => r.problems.map((p) => `<p class="problem">${html(DEVICES.find((d) => d.id === r.device).label)} — ${html(p)}</p>`)).join("")}
      <ul>${(f.runs[0]?.checks || []).map((c, i) => `<li class="${f.runs.every((r) => r.checks[i]?.ok) ? "ok" : "no"}">${html(c.what)}</li>`).join("")}</ul>
      <div class="shots">${f.runs.map((r) => `<figure class="${r.device}"><a href="${r.file}"><img src="${r.file}" loading="lazy" alt="${html(f.title)} ${r.device}"></a><figcaption>${html(DEVICES.find((d) => d.id === r.device).label)}</figcaption></figure>`).join("")}</div>
    </section>`).join("");
  return `<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>화면 검증 ${html(result.commit)}</title>
<style>
:root{--bg:#f4f5f7;--card:#fff;--ink:#1c2330;--muted:#5d6878;--line:#dfe3ea;--ok:#12733f;--okbg:#e3f5ea;--no:#b3261e;--nobg:#fde8e6}
@media (prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1b2029;--ink:#e8ecf2;--muted:#9aa5b5;--line:#2d3440;--ok:#6fd49b;--okbg:#153324;--no:#ff9a92;--nobg:#3c1b19}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,"Malgun Gothic",sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{font-size:22px;margin:0 0 4px}.meta{color:var(--muted);margin:0 0 16px}
.verdict{display:inline-block;padding:6px 14px;border-radius:999px;font-weight:700;margin-bottom:16px}
.verdict.pass,.pass .badge{background:var(--okbg);color:var(--ok)}.verdict.fail,.fail .badge{background:var(--nobg);color:var(--no)}
nav{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:20px}nav a{padding:3px 10px;border:1px solid var(--line);border-radius:999px;color:inherit;text-decoration:none;font-size:13px}
nav a.fail{border-color:var(--no);color:var(--no)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}.card.fail{border-color:var(--no)}
h2{font-size:17px;margin:0 0 2px}.badge{font-size:12px;padding:2px 8px;border-radius:999px;margin-right:6px;vertical-align:2px}
.url{color:var(--muted);font:13px ui-monospace,Consolas,monospace;margin:0 0 8px;word-break:break-all}
.problem{color:var(--no);margin:4px 0;font-weight:600}ul{margin:8px 0 12px;padding-left:20px}li.ok::marker{content:"✓  ";color:var(--ok)}li.no{color:var(--no)}li.no::marker{content:"✗  "}
.shots{display:flex;gap:12px;align-items:flex-start;overflow-x:auto}figure{margin:0;flex:none}figure.pc{width:min(72%,760px)}figure.mobile{width:min(24%,230px)}
img{display:block;width:100%;max-height:560px;object-fit:cover;object-position:top;border:1px solid var(--line);border-radius:8px}figcaption{color:var(--muted);font-size:12px;margin-top:4px}
</style>
<main>
<h1>화면 검증 — ${html(result.commit)}</h1>
<p class="meta">${html(result.time)} · 픽스처 캐릭터 「${html(result.character)}」 · ${result.with_ai ? "넥슨 연결 없음 · AI 상담은 실제 모델" : "넥슨·AI 연결 없음"}</p>
<div class="verdict ${failed.length ? "fail" : "pass"}">${failed.length ? `실패 ${failed.length}개 / 전체 ${result.features.length}개` : `전체 ${result.features.length}개 통과`}</div>
<nav>${result.features.map((f) => `<a class="${f.ok ? "" : "fail"}" href="#${html(f.id)}">${html(f.id)}</a>`).join("")}</nav>
${cards}
</main></html>`;
}

async function main() {
  if (!flag("no-build")) execSync("npm --prefix web run build", { cwd: ROOT, stdio: "ignore" });
  const dirty = execSync("git status --porcelain", { cwd: ROOT }).toString().trim() ? "-dirty" : "";
  const commit = execSync("git rev-parse --short HEAD", { cwd: ROOT }).toString().trim() + dirty;
  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const dir = arg("out", path.join(HERE, "out", `${commit}-${stamp}`));
  fs.mkdirSync(dir, { recursive: true });

  const server = startServer();
  let chrome;
  const result = { commit, time: new Date().toISOString(), character: map.character, with_ai: WITH_AI, features: [] };
  try {
    await waitHealthy(server);
    chrome = await launchChrome({ port: 9334 });
    const wanted = map.features.filter((f) => (!ONLY || ONLY.split(",").includes(f.id)) && (f.requires !== "ai" || WITH_AI));
    for (const feature of wanted) {
      const runs = [];
      for (const device of DEVICES.filter((d) => !feature.devices || feature.devices.includes(d.id))) {
        const { png, ...run } = await runFeature(chrome.cdp, feature, device);
        run.file = `${feature.id}__${device.id}.png`;
        fs.writeFileSync(path.join(dir, run.file), png);
        runs.push(run);
      }
      const ok = runs.every((r) => r.ok);
      result.features.push({ id: feature.id, title: feature.title, url: fill(feature.url), ok, runs });
      console.log(`${ok ? "통과" : "실패"} ${feature.id}${ok ? "" : " — " + runs.flatMap((r) => r.problems).join(" / ")}`);
    }
  } finally {
    chrome?.close();
    server.stop();
  }
  result.ok = result.features.length > 0 && result.features.every((f) => f.ok);
  fs.writeFileSync(path.join(dir, "result.json"), JSON.stringify(result, null, 2));
  fs.writeFileSync(path.join(dir, "index.html"), evidencePage(result));
  console.log(`${result.ok ? "화면 검증 통과" : "화면 검증 실패"}: ${path.join(dir, "index.html")}`);
  process.exit(result.ok ? 0 : 1);
}

main().catch((e) => { console.error(e.message || e); process.exit(1); });
