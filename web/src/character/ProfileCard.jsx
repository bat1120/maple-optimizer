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
        <div className="profile-title">
          <h2>{p.name || name}</h2>
          {p.world && <span className="badge">{p.world}</span>}
        </div>
        <p className="profile-meta">
          <span className="meta-strong">Lv.{summary.level}</span>
          <span className="dot" aria-hidden="true" />
          <span>{summary.character_class}</span>
          {p.guild && <><span className="dot" aria-hidden="true" /><span className="muted">길드 {p.guild}</span></>}
        </p>
        <div className="stats-row">
          <div className="stat stat-primary"><span className="stat-label">스탯 공격력</span><strong>{formatBig(summary.stat_attack?.engine)}</strong></div>
          <div className="stat"><span className="stat-label">전투력(인게임 기록)</span><strong>{formatBig(summary.combat_power_reference)}</strong></div>
          <div className="stat"><span className="stat-label">적용 중인 세팅</span><strong className="small">{settingLabel(summary.active_setting)}</strong></div>
        </div>
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
