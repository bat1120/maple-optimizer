import { formatRelative, settingLabel } from "../format.js";

const AXIS = { equipment: "장비", hyper: "하이퍼", ability: "어빌", union: "유니온", link: "링크" };

// '먼저 무료로' 띠(2026-10-11 디자인 심사 4회차): 프리셋만 바꾸면 메소 없이 오르는 실딜이 업그레이드 1순위보다 클 수 있는데
// 왼쪽 표에 묻혀 있었다. 보스 세팅 1위가 지금 착용보다 셀 때만 보인다.
// 축별 상승폭(2026-11-16 사용자): +84.7%만 보고 장비가 빠져서인 줄 알았다 — 실제론 하이퍼·유니온 때문이었다.
export default function FreeSwitch({ ranking, breakdown }) {
  const best = ranking?.[0];
  if (!best || !(best.relative_to_active > 1)) return null;
  const rows = (breakdown || []).filter((x) => AXIS[x.axis]);
  return (
    <section className="free-switch" aria-label="먼저 무료로">
      <span className="pick-label">먼저 무료로</span>
      <span className="free-switch-body">
        보스 갈 때 <strong>{settingLabel(best.setting)}</strong>로 바꾸면
        <span className="free-switch-gain">실딜 {formatRelative(best.relative_to_active)}</span>
      </span>
      <span className="muted small">프리셋만 바꾸면 돼요 · 메소 0</span>
      {rows.length > 1 && (
        <span className="free-switch-breakdown small">
          <span className="muted">하나씩만 바꾸면</span>
          <ul aria-label="어디서 오르나">
            {rows.map((x) => (
              <li key={x.axis}>{`${AXIS[x.axis]} ${x.from}→${x.to} ${formatRelative(x.relative_to_active)}`}</li>
            ))}
          </ul>
          <span className="muted">같이 바꾸면 서로 곱해져 합보다 커요</span>
        </span>
      )}
    </section>
  );
}
