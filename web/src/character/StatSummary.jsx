// 주요 스탯(츄츄지지 '스탯' 칸 문법). 2026-10-11 심사 4회차: 요약 PC 왼쪽 단 아래가 비어 있었다.
// 값은 서버 계산 그대로: 보스 세팅 예측(settings.best.final), 없으면 지금 착용(summary.final).
import { settingLabel } from "../format.js";
const n = (v) => (v == null ? "—" : Math.round(v).toLocaleString("ko-KR"));
const pct = (v) => (v == null ? "—" : `${Number(v).toFixed(v % 1 ? 1 : 0)}%`);

// hpMain: 주스탯이 HP인 직업(데몬어벤져)은 HP를 맨 앞에 보여 준다 — 2026-11-25 운영 화면에서 빠져 있었다.
// 스탯창 HP는 500,000에서 멈추지만 여기 값은 서버가 스탯공격력에서 되짚은 실제 HP다.
export default function StatSummary({ final, setting = null, hpMain = false }) {
  if (!final) return null;
  const four = [...(hpMain ? ["HP"] : []), "STR", "DEX", "INT", "LUK"].map((k) => [k, final.stats?.[k]]);
  const rows = [
    ...four.map(([k, v]) => [k, n(v)]),
    ["공격력", n(final.atk)], ["마력", n(final.matk)],
    ["데미지", pct(final.dmg)], ["보스 몬스터 데미지", pct(final.boss)],
    ["방어율 무시", pct(final.ied)], ["크리티컬 데미지", pct(final.cd)],
  ];
  return (
    <section className="card stat-summary">
      <h3 className="panel-title">주요 스탯</h3>
      <p className="panel-sub">{setting ? `보스 세팅(${settingLabel(setting)}) 기준 예측 합계예요(버프·도핑 제외).` : "지금 착용 기준 합계예요(버프·도핑 제외)."}</p>
      <dl className="stat-grid">
        {rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd className="num">{v}</dd></div>)}
      </dl>
    </section>
  );
}
