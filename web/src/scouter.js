// 환산 계산기(MapleScouter) 연동(2026-10-07): 우리 사이트에서 [환산용 복사] → MapleScouter 입력 화면에서 북마클릿 한 번.
// 북마클릿은 MapleScouter 화면의 칸을 '이름'으로 찾아(라벨 <span> → 위로 올라가 input) 지금 값에 템 교체 변화량을 더한다.
// 서버로 아무것도 보내지 않고, 그 페이지의 입력칸만 바꾼다(결과 보기·저장은 사용자가 누른다).
export const PREFIX = "MAPLEOPT1 ";
export const SCOUTER_INPUT_URL = "https://maplescouter.com/ko/input";

// 경매장 데이터 없이 시험하는 견본: 직업과 상관없이 모든 캐릭터에 있는 칸만(보스 데미지·크리 데미지). who로 캐릭터를 붙이면 자동 교체까지 시험된다.
export function sampleScouter(who = {}) {
  return { v: 1, slot: "견본", from: "지금 템", to: "테스트 템(보스 +10%, 크뎀 +5%)", ...who,
    rows: { main: [], sub: [], attack: "마력" }, fields: { "보스 데미지": 10, "크리 데미지": 5 }, ied_add: [], ied_remove: [] };
}

// 채우기 코드 — 북마클릿과 테스트가 이 문자열 하나를 같이 쓴다(브라우저 그대로 실행되도록 외부 참조 없음).
export const FILL_SOURCE = `(function (doc, p) {
  var setter = Object.getOwnPropertyDescriptor(doc.defaultView.HTMLInputElement.prototype, "value").set;
  function num(el) { var x = parseFloat(String(el.value).replace(/,/g, "")); return isNaN(x) ? 0 : x; }
  function fmt(x) { return String(Math.round(x * 10000) / 10000); }
  function put(el, x) {
    setter.call(el, fmt(x));
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }
  function rowInputs(label, need) {
    var spans = Array.prototype.filter.call(doc.querySelectorAll("span"), function (s) {
      return s.children.length === 0 && s.textContent.trim() === label;
    });
    for (var i = 0; i < spans.length; i++) {
      var el = spans[i];
      for (var k = 0; k < 5 && el; k++) {
        el = el.parentElement;
        if (!el) break;
        var ins = el.querySelectorAll("input");
        if (ins.length) { if (!need || ins.length === need) return Array.prototype.slice.call(ins); break; }
      }
    }
    return null;
  }
  // 안전장치: MapleScouter에 불러와진 캐릭터의 직업·레벨이 복사한 캐릭터와 같은지(2026-10-07 — 다른 캐릭터에 더하는 실수 방지)
  function near(label, sel) {
    var spans = Array.prototype.filter.call(doc.querySelectorAll("span"), function (s) {
      return s.children.length === 0 && s.textContent.trim() === label;
    });
    for (var i = 0; i < spans.length; i++) {
      var el = spans[i];
      for (var k = 0; k < 5 && el; k++) { el = el.parentElement; if (el && el.querySelector(sel)) return el.querySelector(sel); }
    }
    return null;
  }
  function norm(x) { return String(x || "").replace(/[\\s()（）]/g, ""); }
  var note = "";
  if (p.job) {
    var jobEl = near("직업", "[role=combobox], select, button");
    var pageJob = jobEl ? (jobEl.value || jobEl.textContent || "").trim() : "";
    var lvEl = near("레벨", "input");
    var pageLv = lvEl ? parseInt(lvEl.value, 10) : NaN;
    if (pageJob && norm(pageJob) !== norm(p.job)) {
      var who = (p.name ? p.name + "(" : "(") + p.job + (p.level ? " Lv." + p.level : "") + ")";
      var ok = doc.defaultView.confirm("MapleScouter에 " + pageJob + (isNaN(pageLv) ? "" : " Lv." + pageLv) +
        "이(가) 불러와져 있어요. 복사한 템은 " + who + " 기준이에요.\\n먼저 [검색 캐릭터 불러오기]로 그 캐릭터를 불러오는 게 맞아요. 그래도 지금 칸에 더할까요?");
      if (!ok) return { changed: 0, missing: [], cancelled: true, note: "직업이 달라 채우지 않았어요" };
    } else if (p.level && !isNaN(pageLv) && pageLv !== p.level) {
      note = "레벨이 달라요(MapleScouter Lv." + pageLv + " / 복사 Lv." + p.level + ") — 같은 캐릭터인지 확인해 주세요";
    }
  }
  var f = p.fields, changed = 0, missing = [];
  function add(el, d) { if (d) { put(el, num(el) + d); changed++; } }
  function statRow(name, key) {
    var b = f[key + "|기본"] || 0, pc = f[key + "|%"] || 0, u = f[key + "|% 미적용"] || 0;
    if (!b && !pc && !u) return;
    var ins = rowInputs(name, 3);
    if (!ins) { missing.push(name); return; }
    add(ins[0], b); add(ins[1], pc); add(ins[2], u);
  }
  p.rows.main.concat(p.rows.sub).forEach(function (m) { statRow(m, m); });
  statRow(p.rows.attack, p.rows.attack);
  ["데미지", "보스 데미지", "크리티컬 확률", "크리 데미지", "초"].forEach(function (name) {
    var d = f[name] || 0;
    if (!d) return;
    var ins = rowInputs(name);
    if (!ins) { missing.push(name); return; }
    add(ins[0], d);
  });
  if (f["최종 데미지"]) {
    var fd = rowInputs("최종 데미지");
    if (!fd) missing.push("최종 데미지");
    else { put(fd[0], ((1 + num(fd[0]) / 100) * (1 + f["최종 데미지"] / 100) - 1) * 100); changed++; }
  }
  if ((p.ied_add || []).length || (p.ied_remove || []).length) {
    var ied = rowInputs("방어율 무시");
    if (!ied) missing.push("방어율 무시");
    else {
      var remain = 100 - num(ied[0]);
      (p.ied_add || []).forEach(function (a) { remain *= 1 - a / 100; });
      (p.ied_remove || []).forEach(function (r) { remain /= 1 - r / 100; });
      put(ied[0], 100 - remain); changed++;
    }
  }
  return { changed: changed, missing: missing, note: note };
})`;

export function runFill(doc, payload) {
  return new Function(`return ${FILL_SOURCE}`)()(doc, payload); // eslint-disable-line no-new-func
}

// 내 캐릭터로 자동 전환(2026-10-07 실사이트 확인): MapleScouter는 /ko/info?name=<닉네임>을 열면 그 캐릭터가 '최근 검색'이 되고,
// 입력 화면으로 가면 "최근에 검색한 [KMS] 월드@닉네임 의 스탯으로 교체할까요?" 창을 띄운다.
// 그래서 우리 링크는 info 화면을 열고, 북마크는 ① info 화면이면 '직접입력' 링크로 이동(같은 페이지 안 이동이라 북마크가 계속 돈다)
// ② 교체 창의 닉네임이 복사한 캐릭터와 같을 때만 [교체] ③ 그다음 FILL_SOURCE로 채운다. 다른 닉네임이면 누르지 않는다.
export const scouterInfoUrl = (name) => (name ? `https://maplescouter.com/ko/info?name=${encodeURIComponent(name)}` : SCOUTER_INPUT_URL);

export const PREP_SOURCE = `(async function (doc, p, sleep) {
  sleep = sleep || function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var win = doc.defaultView;
  function dialog() {
    return Array.prototype.filter.call(doc.querySelectorAll("[role=dialog]"), function (d) { return d.textContent.indexOf("교체할까요") >= 0; })[0] || null;
  }
  function mine(d) {
    if (!p.name) return false;
    var t = d.textContent, i = t.indexOf("@" + p.name);
    if (i < 0) return false;
    var next = t.charAt(i + 1 + p.name.length);
    return next === "" || next === " " || next === "(";
  }
  function levelInput() { // 입력 화면이 그려졌는지: '레벨' 라벨 근처의 input
    var spans = Array.prototype.filter.call(doc.querySelectorAll("span"), function (s) { return s.children.length === 0 && s.textContent.trim() === "레벨"; });
    for (var i = 0; i < spans.length; i++) {
      var el = spans[i];
      for (var k = 0; k < 5 && el; k++) { el = el.parentElement; if (el && el.querySelector("input")) return el.querySelector("input"); }
    }
    return null;
  }
  var moved = false;
  if (win.location.pathname.indexOf("/info") >= 0) { // info 화면에도 '직업' 글자가 있어서 주소로 판단(2026-10-07 실사이트)
    var a = doc.querySelector('a[href$="/input"]');
    var to = win.location.pathname.slice(0, win.location.pathname.indexOf("/info")) + "/input"; // 정규식은 이 템플릿 문자열 안에서 역슬래시가 사라져 쓰지 않는다
    if (a) a.click();
    else if (win.next && win.next.router && win.next.router.push) win.next.router.push(to); // 링크가 안 보이는 화면 배치 대비 — 페이지를 다시 읽지 않는 이동
    else return { switched: false, moved: false };
    moved = true;
  }
  // 교체 창을 기다린다. 입력칸이 2초 넘게 떠 있는데 창이 없으면 이미 그 캐릭터이거나 창이 안 뜨는 경우
  var d = null, seen = 0;
  for (var i = 0; i < (moved ? 60 : 4) && !d; i++) {
    d = dialog();
    if (d) break;
    if (levelInput() && ++seen >= 8) break;
    await sleep(250);
  }
  var switched = false;
  if (d && mine(d)) {
    var btn = Array.prototype.filter.call(d.querySelectorAll("button"), function (b) { return b.textContent.trim() === "교체"; })[0];
    if (btn) { btn.click(); switched = true; }
  }
  // 교체 뒤 스탯을 불러오는 동안 입력칸이 잠깐 사라진다(2026-10-07 사용자 PC에서 '입력칸을 못 찾았어요') — 다시 나타나고 레벨이 맞을 때까지
  for (var k = 0; k < 60; k++) {
    var lv = levelInput();
    if (!dialog() && lv && (!switched || !p.level || parseInt(lv.value, 10) === p.level)) break;
    await sleep(250);
  }
  if (switched) await sleep(300);
  return { switched: switched, moved: moved };
})`;

export function runPrep(doc, payload, sleep) {
  return new Function(`return ${PREP_SOURCE}`)()(doc, payload, sleep); // eslint-disable-line no-new-func
}

const LABEL = { "기본": "", "%": "%", "% 미적용": "(%미적용)" };
const sign = (x) => (x > 0 ? `+${x}` : `${x}`);

// 클립보드 글: 사람이 읽는 요약 + 마지막 줄에 북마클릿이 읽는 PREFIX JSON
export function clipboardText(payload, info = {}) {
  const parts = Object.entries(payload.fields).filter(([, v]) => v).map(([k, v]) => {
    const [name, col] = k.split("|");
    return col ? `${name}${LABEL[col]} ${sign(v)}` : `${k} ${sign(v)}${k === "초" ? "" : "%"}`;
  });
  if (payload.ied_add?.length) parts.push(`방무 줄 추가 ${payload.ied_add.join("·")}%`);
  if (payload.ied_remove?.length) parts.push(`방무 줄 빠짐 ${payload.ied_remove.join("·")}%`);
  const lines = [
    `[메이플 장비 최적화] ${payload.slot}: ${payload.from || "(빈 칸)"} → ${payload.to}`,
    parts.length ? parts.join(" · ") : "스탯 변화 없음",
  ];
  if (info.price) lines.push(`가격 ${Math.round(info.price / 1e8).toLocaleString("ko-KR")}억 · 우리 계산 실딜 ${info.delta_pct >= 0 ? "+" : ""}${info.delta_pct?.toFixed?.(3)}%`);
  lines.push(payload.name
    ? `MapleScouter에서 ${payload.name} 화면을 연 뒤 '환산 채우기' 북마크를 누르면 내 캐릭터로 교체하고 칸에 더해요.`
    : "MapleScouter 입력 화면에서 [검색 캐릭터 불러오기] 후 '환산 채우기' 북마크를 누르면 칸에 더해져요.");
  lines.push(PREFIX + JSON.stringify(payload));
  return lines.join("\n");
}

// 북마크 주소: 클립보드(못 읽으면 붙여넣기 창)에서 PREFIX 줄을 찾아 채우고, 결과를 화면 위에 잠깐 띄운다
export function bookmarkletHref() {
  const body = `(async function(){var P=${JSON.stringify(PREFIX)};var t="";try{t=await navigator.clipboard.readText();}catch(e){}
if(t.indexOf(P)<0){t=prompt("메이플 장비 최적화에서 [환산용 복사]한 내용을 붙여넣어 주세요(Ctrl+V)")||"";}
var line=t.split("\\n").filter(function(l){return l.indexOf(P)===0;})[0];
function toast(m){var d=document.createElement("div");d.textContent=m;d.style.cssText="position:fixed;z-index:99999;left:50%;top:16px;transform:translateX(-50%);background:#1b1f2a;color:#fff;padding:10px 14px;border-radius:10px;font:14px sans-serif;box-shadow:0 4px 16px rgba(0,0,0,.3)";document.body.appendChild(d);setTimeout(function(){d.remove();},6000);}
if(!line){toast("복사한 매물 정보가 없어요 — [환산용 복사]를 먼저 눌러 주세요");return;}
var p=JSON.parse(line.slice(P.length));
if(location.hostname.indexOf("maplescouter.com")<0){var u=${JSON.stringify("https://maplescouter.com/ko/info?name=")}+encodeURIComponent(p.name||"");if(!p.name)u=${JSON.stringify(SCOUTER_INPUT_URL)};if(!window.open(u,"_blank"))location.href=u;toast("MapleScouter "+(p.name||"입력")+" 화면을 열었어요 — 그 탭에서 '환산 채우기'를 한 번 더 눌러 주세요");return;}
var s=await (${PREP_SOURCE})(document,p);var r=(${FILL_SOURCE})(document,p);
if(r.cancelled){toast("환산 채우기를 취소했어요 — "+r.note);return;}
if(!r.changed&&r.missing.length){toast("입력칸을 못 찾았어요 — MapleScouter 내 캐릭터 화면이나 입력 화면에서 눌러 주세요. 계속 이러면 '환산 채우기' 북마크를 새로 설치해 주세요(메이플 장비 최적화 #/scouter)");return;}
toast((s.switched?p.name+" 스탯으로 교체 후 ":"")+"환산 채우기: "+p.slot+" "+(p.from||"")+" → "+p.to+" · "+r.changed+"칸 변경"+(r.missing.length?" · 못 찾은 칸: "+r.missing.join(", "):"")+(r.note?" · "+r.note:"")+" (되돌리려면 '되돌리기')");})();`;
  return `javascript:${encodeURIComponent(body)}`;
}
