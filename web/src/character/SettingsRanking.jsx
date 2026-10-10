import { SCOUTER_DIFF_NOTE, formatRelative, formatStat, settingLabel } from "../format.js";
import { PanelHead, RowsSkeleton } from "../ui/Guide.jsx";

export default function SettingsRanking({ ranking, loading = false }) {
  if (!ranking?.length) {
    if (!loading) return null;
    return (
      <section className="card" aria-busy="true">
        <PanelHead title="보스 세팅 순위" subtitle="프리셋 조합을 보스 실딜로 계산하는 중이에요…" />
        <RowsSkeleton rows={4} />
      </section>
    );
  }
  return (
    <section className="card">
      <PanelHead title="보스 세팅 순위" subtitle="장비·하이퍼·어빌 프리셋 조합을 보스 실딜로 줄 세웠어요. 위 5개만 보여요." />
      <table aria-label="보스 세팅 순위" className="rank-table">
        <thead><tr><th>#</th><th>조합</th><th className="num">현재 대비</th><th className="num">환산 주스탯</th></tr></thead>
        <tbody>
          {ranking.slice(0, 5).map((r, i) => (
            <tr key={settingLabel(r.setting)}>
              <td><span className={`medal medal-${i + 1}`}>{i + 1}</span></td>
              <td>{settingLabel(r.setting)}</td>
              <td className={`num ${r.relative_to_active > 1 ? "pos" : r.relative_to_active < 1 ? "neg" : ""}`}>
                {r.relative_to_active == null ? "—" : formatRelative(r.relative_to_active)}</td>
              <td className="num">{r.main_stat_vs_active == null ? "—" : formatStat(r.main_stat_vs_active)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">{SCOUTER_DIFF_NOTE}</p>
    </section>
  );
}
