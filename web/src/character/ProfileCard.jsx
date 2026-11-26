import { formatBig, settingLabel } from "../format.js";
import Icon from "../ui/icons.jsx";
import BossPicker, { ForceNote } from "./BossPicker.jsx";

// 넥슨이 막혀 서버가 전에 받아 둔 값으로 답할 때(stale_minutes) 얼마나 된 데이터인지
const ago = (m) => (m < 60 ? `${Math.max(m, 1)}분` : m < 1440 ? `${Math.floor(m / 60)}시간` : `${Math.floor(m / 1440)}일`);

// 요약 카드: 아바타 · 이름 · 월드 · 길드 · 직업 · 레벨 + 큰 숫자. 이미지는 넥슨 Open API 주소 그대로(저장하지 않는다).
// defense: 보스 id(보스 목록) 또는 방어율 숫자(직접 입력). force: 서버가 계산한 포스 보정(요구·지금·피해 %)
export default function ProfileCard({ name, summary, best = null, pending = false, defense, onDefense, onRefresh, busy, bosses = [], force = null }) {
  const p = summary.profile || {};
  return (
    <section className="card profile">
      <div className="avatar">
        {p.image ? <img src={p.image} alt={`${p.name || name} 캐릭터`} />
          : <span data-testid="avatar-fallback" aria-hidden="true">{(summary.character_class || "?").slice(0, 1)}</span>}
      </div>
      <div className="profile-main">
        <div className="profile-chips">
          {p.world && <span className="badge">{p.world}</span>}
          <span className="badge badge-quiet">{summary.character_class}</span>
        </div>
        <h2 className="profile-name">{p.name || name}</h2>
        <p className="profile-meta">
          <span className="meta-strong">Lv.{summary.level}</span>
          {p.guild && <><span className="dot" aria-hidden="true" /><span>길드 {p.guild}</span></>}
        </p>
        {/* 숫자 칸: 레퍼런스(환산주스탯·츄츄지지)처럼 세로선으로 나눈 칸, 핵심 숫자는 주황 */}
        <dl className="kpi-strip">
          {/* 기본은 보스 세팅(2026-10-17 사용자). 세팅 순위가 오기 전에는 '계산 중'(2026-11-26: 지금 착용 = 사냥용 세팅을 먼저 보여 주지 않는다).
              세팅 순위를 못 받았을 때만 지금 착용 값 */}
          {/* 큰 숫자는 넥슨이 준 전투력 그대로(2026-11-07 사용자). 세팅별 전투력은 API에 없고 계산하지 않는다 */}
          {/* 2026-11-26: 이 숫자는 게임에서 마지막으로 낀 세팅의 기록이다 — 사냥용을 끼고 나오면 보스 세팅보다 훨씬 낮다
              (실사용: 하루 사이 1억 9,301만 → 1억 409만). 보스 세팅과 다를 때는 그 사실을 붙여 적는다(보스 세팅 전투력은 API에 없다) */}
          <div className="kpi kpi-primary"><dt>전투력(인게임 기록)</dt><dd>{formatBig(summary.combat_power_reference)}
            {best && settingLabel(best.setting) !== settingLabel(summary.active_setting) && (
              <span className="kpi-sub">게임에서 마지막으로 낀 세팅의 기록이라 보스 세팅 전투력과 달라요</span>
            )}</dd></div>
          <div className="kpi"><dt>{best || pending ? "보스 세팅" : "지금 착용 중인 세팅"}</dt>
            <dd className="kpi-text">{pending && !best ? "계산 중…" : settingLabel(best ? best.setting : summary.active_setting)}</dd></div>
        </dl>
      </div>
      <div className="profile-side">
        <BossPicker value={defense} bosses={bosses} onChange={onDefense} />
        <ForceNote force={force} />
        <button type="button" className="ghost" onClick={onRefresh} disabled={busy}>
          <Icon name="refresh" size={16} className={busy ? "spin" : ""} />정보 갱신
        </button>
        <span className="muted small updated"><Icon name="clock" size={13} />{summary.date ? `${summary.date} 기준` : summary.stale_minutes != null ? `넥슨 조회가 잠시 막혀 ${ago(summary.stale_minutes)} 전 데이터를 보여 드려요` : "약 15분 전 데이터"}</span>
      </div>
    </section>
  );
}
