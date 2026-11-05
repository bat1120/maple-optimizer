// 템 교체 변화량을 사람이 읽는 글로(2026-10-13). 칸 이름은 흔한 환산 계산기 입력칸 이름을 따른다(STR 기본·% · %미적용 등).
// MapleScouter 화면에 자동으로 넣던 북마클릿·확장 코드는 뺐다 — 운영자가 연동은 어렵다고 답함(CLAUDE.md 금지 조항).
const LABEL = { "기본": "", "%": "%", "% 미적용": "(%미적용)" };
const sign = (x) => (x > 0 ? `+${x}` : `${x}`);

// 클립보드 글: 사람이 읽는 요약(템 교체 변화량)
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
  return lines.join("\n");
}

