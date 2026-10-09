import { formatBig, settingLabel } from "../format.js";
import Icon from "../ui/icons.jsx";

// 요약 카드: 아바타 · 이름 · 월드 · 길드 · 직업 · 레벨 + 큰 숫자. 이미지는 넥슨 Open API 주소 그대로(저장하지 않는다).
export default function ProfileCard({ name, summary, defense, onDefense, onRefresh, busy }) {
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
          <div className="kpi kpi-primary"><dt>스탯 공격력</dt><dd>{formatBig(summary.stat_attack?.engine)}</dd></div>
          <div className="kpi"><dt>전투력(인게임 기록)</dt><dd>{formatBig(summary.combat_power_reference)}</dd></div>
          <div className="kpi"><dt>적용 중인 세팅</dt><dd className="kpi-text">{settingLabel(summary.active_setting)}</dd></div>
        </dl>
      </div>
      <div className="profile-side">
        <label className="field">보스 방어율(%)
          <input type="number" inputMode="numeric" value={defense} onChange={(e) => onDefense(Number(e.target.value) || 0)} />
        </label>
        <button type="button" className="ghost" onClick={onRefresh} disabled={busy}>
          <Icon name="refresh" size={16} className={busy ? "spin" : ""} />정보 갱신
        </button>
        <span className="muted small updated"><Icon name="clock" size={13} />{summary.date ? `${summary.date} 기준` : "최신(약 15분 지연)"}</span>
      </div>
    </section>
  );
}
