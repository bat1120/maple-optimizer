// 환산 계산기(MapleScouter) 연동(2026-10-07): 우리 사이트에서 [환산용 복사] → MapleScouter 입력 화면에서 북마클릿 한 번.
// 북마클릿은 MapleScouter 화면의 칸을 '이름'으로 찾아(라벨 <span> → 위로 올라가 input) 지금 값에 템 교체 변화량을 더한다.
// 서버로 아무것도 보내지 않고, 그 페이지의 입력칸만 바꾼다(결과 보기·저장은 사용자가 누른다).
export const PREFIX = "MAPLEOPT1 ";
export const SCOUTER_INPUT_URL = "https://maplescouter.com/ko/input";

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
  return { changed: changed, missing: missing };
})`;

export function runFill(doc, payload) {
  return new Function(`return ${FILL_SOURCE}`)()(doc, payload); // eslint-disable-line no-new-func
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
  lines.push("MapleScouter 입력 화면에서 [검색 캐릭터 불러오기] 후 '환산 채우기' 북마크를 누르면 칸에 더해져요.");
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
var p=JSON.parse(line.slice(P.length));var r=(${FILL_SOURCE})(document,p);
toast("환산 채우기: "+p.slot+" "+(p.from||"")+" → "+p.to+" · "+r.changed+"칸 변경"+(r.missing.length?" · 못 찾은 칸: "+r.missing.join(", "):"")+" (되돌리려면 '되돌리기')");})();`;
  return `javascript:${encodeURIComponent(body)}`;
}
