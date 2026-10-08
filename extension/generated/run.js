// 자동 생성 파일 — web/src/scouter.js 에서 만든다(web 폴더에서 npm run ext). 직접 고치지 마세요.
export function mapleoptRun(p) {
  return ((async function (doc, p) {
  var toast = ((function (doc) {
  return function (m) {
    var d = doc.createElement("div");
    d.textContent = m;
    d.style.cssText = "position:fixed;z-index:99999;left:50%;top:16px;transform:translateX(-50%);max-width:min(92vw,720px);background:#1b1f2a;color:#fff;padding:10px 14px;border-radius:10px;font:14px/1.5 sans-serif;box-shadow:0 4px 16px rgba(0,0,0,.3)";
    doc.body.appendChild(d);
    setTimeout(function () { d.remove(); }, 6000);
  };
}))(doc);
  var win = doc.defaultView;
  var s = await ((async function (doc, p, sleep) {
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
  // MapleScouter의 '최근 검색' 캐릭터 이름(localStorage character-store). 읽을 수 없으면 null — 그때는 기다리거나 불러오지 않는다
  function recent() {
    try {
      var st = JSON.parse(win.localStorage.getItem("character-store") || "null");
      st = st && st.state;
      if (!st) return null;
      var info = st.searchResult && st.searchResult.userApiData && st.searchResult.userApiData.info;
      return { name: info ? info.character_name : "", loading: !!st.isLoading };
    } catch (e) { return null; }
  }
  function isMine() { var r = recent(); return !!(r && p.name && !r.loading && r.name === p.name); }
  function jobText() {
    var spans = Array.prototype.filter.call(doc.querySelectorAll("span"), function (s) { return s.children.length === 0 && s.textContent.trim() === "직업"; });
    for (var i = 0; i < spans.length; i++) {
      var el = spans[i];
      for (var k = 0; k < 5 && el; k++) { el = el.parentElement; var c = el && el.querySelector("[role=combobox], select, button"); if (c) return (c.value || c.textContent || "").replace(/[ ()（）]/g, ""); }
    }
    return "";
  }
  var moved = false;
  if (win.location.pathname.indexOf("/info") >= 0) {
    // 정보 화면이 그 캐릭터를 '최근 검색'으로 저장할 때까지(2026-10-07: 너무 일찍 넘어가면 교체 창이 안 뜬다)
    if (p.name && recent()) for (var q = 0; q < 60 && !isMine(); q++) await sleep(250); // info 화면에도 '직업' 글자가 있어서 주소로 판단(2026-10-07 실사이트)
    var to = win.location.pathname.slice(0, win.location.pathname.indexOf("/info")) + "/input"; // 정규식은 이 템플릿 문자열 안에서 역슬래시가 사라져 쓰지 않는다
    // 확장은 탭이 막 열렸을 때 돈다 — 사이트 라우터가 준비되기 전에 링크를 누르면 페이지를 통째로 다시 읽어 이 코드가 끊긴다
    function router() { return win.next && win.next.router && win.next.router.push ? win.next.router : null; }
    for (var w = 0; w < 20 && !router(); w++) await sleep(250);
    var a = doc.querySelector('a[href$="/input"]');
    if (router()) router().push(to); // 페이지를 다시 읽지 않는 이동
    else if (a) a.click();
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
  } else if (!d && isMine()) {
    // 교체 창이 안 떴다: 최근 검색이 그 캐릭터인데 칸은 다른 캐릭터(레벨·직업이 다름)면 [검색 캐릭터 불러오기]
    var lv0 = levelInput();
    var other = lv0 && ((p.level && parseInt(lv0.value, 10) !== p.level) || (p.job && jobText() && jobText() !== String(p.job).replace(/[ ()（）]/g, "")));
    var load = Array.prototype.filter.call(doc.querySelectorAll("button"), function (b) { return b.textContent.trim().indexOf("검색 캐릭터 불러오기") === 0; })[0];
    if (other && load) { load.click(); switched = true; }
  }
  // 교체 뒤 스탯을 불러오는 동안 입력칸이 잠깐 사라진다(2026-10-07 사용자 PC에서 '입력칸을 못 찾았어요') — 다시 나타나고 레벨이 맞을 때까지
  for (var k = 0; k < 60; k++) {
    var lv = levelInput();
    if (!dialog() && lv && (!switched || !p.level || parseInt(lv.value, 10) === p.level)) break;
    await sleep(250);
  }
  if (switched) await sleep(300);
  return { switched: switched, moved: moved };
}))(doc, p);
  var check = p.check && p.check.boss ? ((async function (doc, boss, sleep) {
  sleep = sleep || function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  function button(text) { return Array.prototype.filter.call(doc.querySelectorAll("button"), function (b) { return b.textContent.trim() === text; })[0] || null; }
  function card() {
    var im = Array.prototype.filter.call(doc.querySelectorAll("img"), function (x) { return (x.getAttribute("src") || "").indexOf(boss) >= 0; })[0];
    var el = im;
    for (var k = 0; k < 6 && el; k++) { el = el.parentElement; if (el && el.textContent.indexOf("%") >= 0 && el.textContent.length < 200) return el; }
    return null;
  }
  function pct(text) {
    var i = text.lastIndexOf("%"), j = i;
    while (j > 0 && "0123456789.,".indexOf(text.charAt(j - 1)) >= 0) j--;
    var v = parseFloat(text.slice(j, i).replace(/,/g, ""));
    return isNaN(v) ? null : v;
  }
  var go = button("결과");
  if (!go) return null;
  go.click();
  var detail = null;
  for (var i = 0; i < 60 && !detail; i++) { detail = button("상세조회"); if (!detail) await sleep(250); }
  if (!detail) return null;
  detail.click();
  for (var w = 0; w < 160; w++) {
    if (doc.defaultView.location.pathname.indexOf("/result") >= 0) {
      var c = card();
      if (c) {
        await sleep(300); c = card();
        if (!c) return null;
        var leaf = Array.prototype.filter.call(c.querySelectorAll("*"), function (x) { return x.children.length === 0 && x.textContent.indexOf("%") >= 0; }).pop();
        return pct((leaf || c).textContent);  // 칸끼리 붙으면 환산 숫자와 %가 이어진다 — %가 든 가장 안쪽 칸만
      }
      if (doc.querySelectorAll("img[alt=boss]").length > 3) return null;  // 카드는 그려졌는데 그 보스가 없다
    }
    await sleep(250);
  }
  return null;
})) : null;
  var before = null;
  async function backToInput() {  // 보스컷 화면 → 직접입력(넣던 값은 MapleScouter 초안에 남는다)
    var to = win.location.pathname.slice(0, win.location.pathname.indexOf("/result")) + "/input";
    if (win.next && win.next.router) win.next.router.push(to);
    for (var i = 0; i < 60; i++) {
      var keep = Array.prototype.filter.call(doc.querySelectorAll("[role=dialog] button"), function (b) { return b.textContent.trim() === "유지"; })[0];
      if (keep) { keep.click(); await new Promise(function (r) { setTimeout(r, 500); }); }
      if (win.location.pathname.indexOf("/input") >= 0 && Array.prototype.some.call(doc.querySelectorAll("span"), function (x) { return x.textContent.trim() === "레벨"; })) break;
      await new Promise(function (r) { setTimeout(r, 250); });
    }
    await new Promise(function (r) { setTimeout(r, 800); });
  }
  if (check) {
    toast((p.check.label || "보스") + " 지금 배율을 읽는 중…");
    before = await check(doc, p.check.boss);
    await backToInput();
  }
  var r = ((function (doc, p) {
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
  function norm(x) { return String(x || "").replace(/[\s()（）]/g, ""); }
  var note = "";
  if (p.job) {
    var jobEl = near("직업", "[role=combobox], select, button");
    var pageJob = jobEl ? (jobEl.value || jobEl.textContent || "").trim() : "";
    var lvEl = near("레벨", "input");
    var pageLv = lvEl ? parseInt(lvEl.value, 10) : NaN;
    if (pageJob && norm(pageJob) !== norm(p.job)) {
      var who = (p.name ? p.name + "(" : "(") + p.job + (p.level ? " Lv." + p.level : "") + ")";
      var ok = doc.defaultView.confirm("MapleScouter에 " + pageJob + (isNaN(pageLv) ? "" : " Lv." + pageLv) +
        "이(가) 불러와져 있어요. 복사한 템은 " + who + " 기준이에요.\n먼저 [검색 캐릭터 불러오기]로 그 캐릭터를 불러오는 게 맞아요. 그래도 지금 칸에 더할까요?");
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
}))(doc, p);
  if (r.cancelled) { toast("환산 채우기를 취소했어요 — " + r.note); return { s: s, r: r }; }
  if (!r.changed && r.missing.length) {
    toast("입력칸을 못 찾았어요 — MapleScouter 내 캐릭터 화면이나 입력 화면에서 눌러 주세요. 계속 이러면 '환산 채우기'를 새로 설치해 주세요(메이플 장비 최적화 #/scouter)");
    return { s: s, r: r };
  }
  if (check) {
    toast("변화량을 넣었어요(" + r.changed + "칸) — " + (p.check.label || "보스") + " 배율을 다시 읽는 중…");
    var after = await check(doc, p.check.boss);
    var f = function (v) { return v == null ? "못 읽음" : v + "%"; };
    toast((p.check.label || "보스") + " 배율: 지금 " + f(before) + " → 적용 후 " + f(after) +
      (p.check.expected ? " (우리 추정 " + Math.round(p.check.expected * 100) / 100 + "%)" : "") +
      (r.missing.length ? " · 못 찾은 칸: " + r.missing.join(", ") : "") + " — 입력 화면 '되돌리기'로 원래대로");
    return { s: s, r: r, before: before, after: after };
  }
  toast((s.switched ? p.name + " 스탯으로 교체 후 " : "") + "환산 채우기: " + p.slot + " " + (p.from || "") + " → " + p.to + " · " + r.changed + "칸 변경" +
    (r.missing.length ? " · 못 찾은 칸: " + r.missing.join(", ") : "") + (r.note ? " · " + r.note : "") + " (되돌리려면 '되돌리기')");
  return { s: s, r: r };
}))(document, p);
}
