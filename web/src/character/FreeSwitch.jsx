import { formatRelative, settingLabel } from "../format.js";

// '먼저 무료로' 띠(2026-10-11 디자인 심사 4회차): 프리셋만 바꾸면 메소 없이 오르는 실딜이 업그레이드 1순위보다 클 수 있는데
// 왼쪽 표에 묻혀 있었다. 보스 세팅 1위가 지금 착용보다 셀 때만 보인다.
export default function FreeSwitch({ ranking }) {
  const best = ranking?.[0];
  if (!best || !(best.relative_to_active > 1)) return null;
  return (
    <section className="free-switch" aria-label="먼저 무료로">
      <span className="free-switch-label">먼저 무료로</span>
      <span className="free-switch-body">
        보스 갈 때 <strong>{settingLabel(best.setting)}</strong>로 바꾸면
        <span className="free-switch-gain">실딜 {formatRelative(best.relative_to_active)}</span>
      </span>
      <span className="muted small">프리셋만 바꾸면 돼요 · 메소 0</span>
    </section>
  );
}
