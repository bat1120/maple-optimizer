import { formatRelative, formatStat, settingLabel } from "../format.js";

export default function SettingsRanking({ ranking }) {
  if (!ranking?.length) return null;
  return (
    <section className="card">
      <h3>보스 세팅 순위 <span className="muted small">프리셋 조합</span></h3>
      <table aria-label="보스 세팅 순위" className="rank-table">
        <thead><tr><th>#</th><th>조합</th><th className="num">현재 대비</th><th className="num">환산 주스탯</th></tr></thead>
        <tbody>
          {ranking.slice(0, 5).map((r, i) => (
            <tr key={settingLabel(r.setting)}>
              <td><span className={`medal medal-${i + 1}`}>{i + 1}</span></td>
              <td>{settingLabel(r.setting)}</td>
              <td className="num">{r.relative_to_active == null ? "—" : formatRelative(r.relative_to_active)}</td>
              <td className="num">{r.main_stat_vs_active == null ? "—" : formatStat(r.main_stat_vs_active)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
