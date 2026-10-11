// 주요 스탯(츄츄지지 '스탯' 칸 문법). 2026-10-11 심사 4회차: 요약 PC 왼쪽 단 아래가 비어 있었다.
// 값은 서버가 계산한 지금 착용 기준 합계(summary.final) 그대로.
const n = (v) => (v == null ? "—" : Math.round(v).toLocaleString("ko-KR"));
const pct = (v) => (v == null ? "—" : `${Number(v).toFixed(v % 1 ? 1 : 0)}%`);

export default function StatSummary({ final }) {
  if (!final) return null;
  const four = ["STR", "DEX", "INT", "LUK"].map((k) => [k, final.stats?.[k]]);
  const rows = [
    ...four.map(([k, v]) => [k, n(v)]),
    ["공격력", n(final.atk)], ["마력", n(final.matk)],
    ["데미지", pct(final.dmg)], ["보스 몬스터 데미지", pct(final.boss)],
    ["방어율 무시", pct(final.ied)], ["크리티컬 데미지", pct(final.cd)],
  ];
  return (
    <section className="card stat-summary">
      <h3 className="panel-title">주요 스탯</h3>
      <p className="panel-sub">지금 착용 기준 합계예요(버프·도핑 제외).</p>
      <dl className="stat-grid">
        {rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd className="num">{v}</dd></div>)}
      </dl>
    </section>
  );
}
