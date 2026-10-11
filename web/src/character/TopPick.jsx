import { useEffect, useState } from "react";
import { getRoadmap } from "../api.js";
import { formatPct } from "../format.js";
import { hashFor } from "../router.js";
import Icon from "../ui/icons.jsx";

// 요약 탭 위 '업그레이드 1순위' 한 줄(2026-10-11 디자인 심사: 서비스의 답이 기본 탭 밖에 묻혀 있었다).
// 가격 대비 순위 1위만 보여 주고, 전체는 업그레이드 탭. 못 불러오면 아무것도 그리지 않는다(요약은 그대로).
export default function TopPick({ name, defense }) {
  const [top, setTop] = useState(undefined); // undefined = 계산 중, null = 없음
  useEffect(() => {
    let alive = true;
    setTop(undefined);
    getRoadmap(name, defense).then((d) => alive && setTop(d?.value_ranking?.[0] || null)).catch(() => alive && setTop(null));
    return () => { alive = false; };
  }, [name, defense]);
  if (top === null) return null;
  return (
    <section className="top-pick" aria-label="업그레이드 1순위" aria-busy={top === undefined}>
      <span className="top-pick-label">업그레이드 1순위</span>
      {top === undefined ? (
        <span className="muted small">가격 대비 순위를 계산하는 중이에요…</span>
      ) : (
        <span className="top-pick-body">
          <strong>{top.slot} {top.kind}</strong>
          <span className="muted">{top.grade} {top.lines_good}줄 · {top.target.join(" / ")}</span>
          {/* 업그레이드 탭 카드와 같은 규칙: 실딜은 배지, 순위 기준인 억당 효율은 주황 큰 숫자 */}
          <span className="score-badge top-pick-gain">실딜 {formatPct(top.delta_pct)}</span>
          <span className="top-pick-eff">1억 메소당 <strong className="num">{formatPct(top.per_100m)}</strong>
            {top.cube_cost_text && <span className="muted"> · 큐브 평균 {top.cube_cost_text}</span>}</span>
        </span>
      )}
      <a className="top-pick-go" href={hashFor({ page: "character", name, tab: "upgrade" })}>순위 전체 보기<Icon name="chevron" size={14} /></a>
    </section>
  );
}
