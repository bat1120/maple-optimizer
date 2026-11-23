import { useEffect, useState } from "react";
import { getBudgetRoadmap } from "../api.js";
import { formatPct } from "../format.js";
import { hashFor } from "../router.js";
import { HOW, stepLabel } from "../PlanPanel.jsx";
import Icon from "../ui/icons.jsx";

// 요약 탭 위 '가장 먼저 할 것' 한 줄(2026-10-11 디자인 심사: 서비스의 답이 기본 탭 밖에 묻혀 있었다).
// 2026-11-23: 업그레이드 계획의 1번 줄을 그대로 보여 준다 — 전에는 잠재·에디 순위 1위(평균 105억)를 보여 줘서
// 계획표의 첫 줄(추옵 재설정 4395만)과 '먼저 할 일'이 서로 달랐다. 못 불러오면 아무것도 그리지 않는다(요약은 그대로).
export default function TopPick({ name, defense, after = false }) {
  const [top, setTop] = useState(undefined); // undefined = 계산 중, null = 없음
  useEffect(() => {
    let alive = true;
    setTop(undefined);
    getBudgetRoadmap(name, defense, null, 1).then((d) => alive && setTop(d?.steps?.[0] || null)).catch(() => alive && setTop(null));
    return () => { alive = false; };
  }, [name, defense]);
  if (top === null) return null;
  const where = top && (top.path === "큐브" ? top.target?.join(" / ") : HOW[top.path] || top.path);
  return (
    <section className="top-pick" aria-label="업그레이드 1순위" aria-busy={top === undefined}>
      <span className="pick-label">{after ? "다음으로 메소를 쓴다면" : "업그레이드 1순위"}</span>
      {top === undefined ? (
        <span className="muted small">업그레이드 계획을 계산하는 중이에요…</span>
      ) : (
        <span className="top-pick-body">
          <strong>{stepLabel(top)}</strong>
          <span className="muted">{where}</span>
          {/* 강조는 하나: 순서의 기준인 1억 메소당 효율만 주황 큰 숫자 */}
          <span className="top-pick-eff">1억 메소당 <strong className="num">{formatPct(top.per_100m)}</strong>
            <span className="muted"> · 평균 {top.cost_text} · 실딜 {formatPct(top.delta_pct)}</span></span>
        </span>
      )}
      <a className="top-pick-go" href={hashFor({ page: "character", name, tab: "upgrade" })}>내 업그레이드 계획 보기<Icon name="chevron" size={14} /></a>
    </section>
  );
}
