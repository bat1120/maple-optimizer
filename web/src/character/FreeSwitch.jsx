import { settingLabel } from "../format.js";

const AXIS = { equipment: "장비", hyper: "하이퍼", ability: "어빌", union: "유니온", link: "링크" };

// '먼저 무료로' 띠(2026-10-11 디자인 심사 4회차): 프리셋만 바꾸면 메소 없이 오르는 실딜이 업그레이드 1순위보다 클 수 있는데
// 왼쪽 표에 묻혀 있었다. 보스 세팅 1위가 지금 착용보다 셀 때만 보인다.
// 축별 상승폭(2026-11-16 사용자): +84.7%만 보고 장비가 빠져서인 줄 알았다 — 실제론 하이퍼·유니온 때문이었다.
// 2026-11-26 사용자: 전부 보스 기준 — 사냥용 세팅 대비 상승폭(+93% 등)과 축별 상승폭은 뺐다. 이 화면이 보스 세팅 기준이고,
// 지금 게임에서는 다른 프리셋을 끼고 있다는 사실(어느 축이 다른지)만 한 줄로 알린다.
export default function FreeSwitch({ ranking, breakdown }) {
  const best = ranking?.[0];
  if (!best || !(best.relative_to_active > 1)) return null;
  const rows = (breakdown || []).filter((x) => AXIS[x.axis]);
  return (
    <section className="free-switch" aria-label="보스 세팅 기준">
      <span className="pick-label">보스 세팅 기준</span>
      <span className="free-switch-body">
        이 화면은 보스 세팅 <strong>{settingLabel(best.setting)}</strong> 기준이에요
      </span>
      <span className="muted small">
        지금 게임에서는 다른 프리셋을 끼고 있어요{rows.length ? `(${rows.map((x) => `${AXIS[x.axis]} ${x.from}→${x.to}`).join(" · ")})` : ""} — 보스 갈 때 프리셋만 바꾸면 돼요
      </span>
    </section>
  );
}
