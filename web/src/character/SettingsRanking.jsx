import { SCOUTER_DIFF_NOTE, formatRelative, formatStat, settingLabel } from "../format.js";
import { PanelHead, RowsSkeleton } from "../ui/Guide.jsx";

// 조합은 글 한 줄 대신 숫자 칸(2026-10-11 심사 6회차: '장비 2 · 하이퍼 3 …'가 2~3줄로 꺾여 행끼리 비교가 안 됐다).
// 1위 조합과 다른 값만 진하게(2026-11-26 사용자: 전부 보스 기준 — 전에는 지금 착용과 비교했는데, 사냥용을 끼고 있으면 뜻이 없다).
const PARTS = [["equipment", "장비"], ["hyper", "하이퍼"], ["ability", "어빌"], ["union", "유니온"], ["link", "링크"]];

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
  const cols = PARTS.filter(([k]) => ranking.some((r) => r.setting[k] != null));
  const top = ranking[0];
  // 1위 대비: 서버 값(relative_to_best)이 있으면 그대로, 없으면 실딜 지수로 계산
  const rel = (r) => r.relative_to_best ?? (top.index > 0 && r.index != null ? r.index / top.index : null);
  return (
    <section className="card">
      <PanelHead title="보스 세팅 순위" subtitle="프리셋 번호 조합을 보스 실딜로 줄 세웠어요(위 5개). 1위가 이 화면의 기준(보스 세팅)이고, 진한 숫자는 1위와 다른 프리셋이에요." />
      <table aria-label="보스 세팅 순위" className="rank-table">
        <thead><tr><th>#</th>{cols.map(([k, name]) => <th key={k} className="combo-col">{name}</th>)}<th className="num">1위 대비</th><th className="num">환산 주스탯</th></tr></thead>
        <tbody>
          {ranking.slice(0, 5).map((r, i) => (
            <tr key={settingLabel(r.setting)} aria-label={settingLabel(r.setting)}>
              <td><span className={`medal medal-${i + 1}`}>{i + 1}</span></td>
              {cols.map(([k, name]) => (
                <td key={k} className={`combo-col${i > 0 && top.setting[k] !== r.setting[k] ? " diff" : ""}`} aria-label={`${name} ${r.setting[k]}`}>{r.setting[k]}</td>
              ))}
              <td className={`num ${i > 0 && rel(r) < 1 ? "neg" : ""}`}>
                {i === 0 ? "기준" : rel(r) == null ? "—" : formatRelative(rel(r))}</td>
              <td className="num">{i === 0 ? "기준" : r.main_stat_vs_best == null ? "—" : formatStat(r.main_stat_vs_best)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">{SCOUTER_DIFF_NOTE}</p>
    </section>
  );
}
