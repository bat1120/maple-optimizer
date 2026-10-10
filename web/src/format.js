// 표시·입력 변환. 계산은 서버(engine)가 한다.

// 환산 숫자가 환산주스탯(MapleScouter)과 다른 이유(2026-10-10) — 환산이 나오는 화면에 같은 문구를 쓴다
export const SCOUTER_DIFF_NOTE = "환산 주스탯은 이 사이트 기준(지금 상태·보스 세팅의 실딜)이에요. 환산주스탯(MapleScouter)은 도핑·버프를 모두 켠 기준이라, 같은 템이라도 오르는 숫자가 달라요.";

export function formatMeso(meso) {
  const eok = Math.floor(meso / 100_000_000);
  const man = Math.floor((meso % 100_000_000) / 10_000);
  const parts = [];
  if (eok) parts.push(`${eok}억`);
  if (man) parts.push(`${man}만`);
  return parts.length ? parts.join(" ") : `${meso}`;
}

// 큰 숫자 카드용: 억·만 단위에 쉼표(1,234억 5,678만). 만 미만은 그대로
export function formatBig(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const v = Math.round(Number(n));
  if (Math.abs(v) < 10_000) return v.toLocaleString("ko-KR");
  const eok = Math.floor(v / 100_000_000);
  const man = Math.floor((v % 100_000_000) / 10_000);
  return [eok ? `${eok.toLocaleString("ko-KR")}억` : "", man ? `${man.toLocaleString("ko-KR")}만` : ""].filter(Boolean).join(" ");
}

// "45억 3000만", "4.5억", "1,000,000" → 메소. 해석 불가면 null.
export function parsePrice(text) {
  const t = String(text ?? "").replace(/[,\s]/g, "");
  if (!t) return null;
  if (/^\d+$/.test(t)) return Number(t);
  const m = t.match(/^(?:(\d+(?:\.\d+)?)억)?(?:(\d+)만)?$/);
  if (!m || (!m[1] && !m[2])) return null;
  return Math.round(Number(m[1] ?? 0) * 100_000_000 + Number(m[2] ?? 0) * 10_000);
}

export function formatPct(x) {
  return `${x >= 0 ? "+" : ""}${x.toFixed(3)}%`;
}

export function formatRelative(ratio) {
  const pct = (ratio - 1) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

export function formatStat(n) {
  const r = Math.round(n);
  return `${r >= 0 ? "+" : "-"}${Math.abs(r).toLocaleString("en-US")}`;
}

export function parsePotentials(text) {
  return String(text ?? "").split("\n").map((s) => s.trim()).filter(Boolean);
}

export function settingLabel(s) {
  const base = `장비 ${s.equipment} · 하이퍼 ${s.hyper} · 어빌 ${s.ability}`;
  const withUnion = s.union ? `${base} · 유니온 ${s.union}` : base;
  return s.link ? `${withUnion} · 링크 ${s.link}` : withUnion;
}
