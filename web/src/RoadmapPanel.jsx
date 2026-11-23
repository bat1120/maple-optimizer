import { Fragment, useEffect, useState } from "react";
import { getRoadmap } from "./api.js";
import { formatMeso, formatPct, settingLabel } from "./format.js";
import { EmptyState, HowTo, PanelHead, RowsSkeleton } from "./ui/Guide.jsx";
import { gradeClass } from "./character/grades.js";
import { hashFor } from "./router.js";
import { stepName } from "./flow.js";

// 휴대폰 → PC로 넘기기(2026-11-23 심사: '휴대폰에서는 여기까지'에서 흐름이 끊겼다)
function CopyLink() {
  const [done, setDone] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(window.location.href); setDone(true); } catch { setDone(false); }
  };
  return <button type="button" className="ghost small mobile-only-inline copy-link" onClick={copy}>{done ? "주소를 복사했어요" : "이 화면 주소 복사"}</button>;
}

// 전체 부위 로드맵: 부위마다 잠재·에디의 '다음 단계'(실딜이 처음 0.1% 이상 오르는 등급·줄 수)와 모든 단계를 보여 준다.
const KINDS = ["잠재", "에디"];
const TOP = 7; // 가격 대비 순위는 처음 7개만(1위 전체 폭 + 2단 3줄, 나머지는 [더 보기])
const label = (t) => `${t.grade} ${t.lines_good}줄`;
// 관측 시세: 화면 분석으로 쌓인 매물 중 이 단계 조건을 갖춘 것
const marketText = (m) => (m ? `시세 ${formatMeso(m.median)} (${m.count}건, 최저 ${formatMeso(m.min)}) · 억당 ${formatPct(m.per_100m)}` : "시세 없음");

function Next({ row, kind }) {
  const i = row.next?.[kind];
  if (i == null) return <span className="muted">—</span>;
  const t = row[kind][i];
  return <span>{label(t)} {formatPct(t.delta_pct)}<br /><span className="muted">{t.target.join(" / ")}</span></span>;
}

// onEvaluate(v): '이 조건으로 찾은 매물 평가하기' — 화면 공유 평가를 열고 찾는 조건을 넘긴다(없으면 버튼을 안 그린다)
export default function RoadmapPanel({ name, defense, autoLoad = false, active = null, onEvaluate = null, before = null, after = null, budget = null, watch = null }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const load = async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await getRoadmap(name, defense));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { if (autoLoad && name) load(); }, [autoLoad, name, defense]); // eslint-disable-line react-hooks/exhaustive-deps
  const best = Math.max(0, ...(data?.value_ranking || []).map((v) => v.per_100m || 0));
  // 예산을 넣었으면 큐브 평균이 예산 안인 것부터(4회차 심사: 50억을 넣어도 보이는 카드 7장이 전부 '예산 밖'이라 다음 단계로 갈 대상이 없었다).
  // 순위 번호(rank)는 원래 순서 그대로 둔다 — 번호가 바뀌면 다른 화면의 순위와 어긋난다
  const ranked = (data?.value_ranking || []).map((v, i) => ({ v, rank: i + 1, over: !!budget && v.cube_cost > budget }));
  const inside = ranked.filter((x) => !x.over);
  const ordered = budget && inside.length ? [...inside, ...ranked.filter((x) => x.over)] : ranked;
  const shown = showAll ? ordered : ordered.slice(0, budget && inside.length ? Math.min(TOP, inside.length) : TOP);

  return (
    <section className="panel">
      {/* 2026-10-11 심사 3회차: 1위 카드까지 제목 2개·접힘 2개를 지나야 했다 → 제목 하나, 기준은 접힘 하나 */}
      {before}
      <PanelHead title="가격 대비 업그레이드 순위" icon="trend"
                 subtitle="경매장에서 찾아볼 잠재·에디 순서예요 — 1억 메소당 보스 실딜이 많이 오르는 게 위. 추옵·스타포스처럼 내 템에 직접 하는 강화는 위 '내 메소로' 계산에 함께 들어 있어요.">
        <button type="button" className={autoLoad ? "ghost small" : undefined} onClick={load} disabled={!name || busy}>
          {autoLoad ? (busy ? "계산 중…" : "다시 계산") : "전체 부위 로드맵"}
        </button>
      </PanelHead>
      <HowTo steps={[
        <><strong>가격 대비 순위</strong>: 억당 효율 막대가 길수록 같은 메소로 실딜이 많이 올라요. 1위부터 보세요.</>,
        <><strong>부위별 다음 단계</strong>: 실딜이 처음 0.1% 이상 오르는 잠재·에디 등급과 줄 수예요.</>,
        <>표 아래 <strong>'○○ 모든 단계'</strong>를 펼치면 단계별 실딜·한 번에 나올 확률·관측 시세를 볼 수 있어요.</>,
      ]} />
      {busy && !data && <RowsSkeleton rows={5} />}
      {error && (
        <div role="alert" className="inline-error">
          <strong>{error.message}</strong>
          <span>{data ? "아래 순위는 마지막으로 성공한 계산이에요. 1분쯤 뒤에 [다시 계산]을 눌러 주세요." : "1분쯤 뒤에 [다시 계산]을 눌러 주세요."}</span>
        </div>
      )}
      {data && (
        <>
          {/* 2026-10-11 심사 4회차: 기준 세팅이 접힌 회색 줄에만 있어 '내 캐릭터 기준이 맞나' 의심 → 본문 글자로 보이고, 착용과 다르면 말한다 */}
          <p className="basis-line">
            <span className="basis-k">계산 기준</span> 보스 세팅 <strong>{settingLabel(data.evaluation_setting)}</strong>
            {active && settingLabel(active) !== settingLabel(data.evaluation_setting) && <span className="muted"> — 지금 착용과 달라요</span>}
          </p>
          {data.basis_warning && <p role="note" className="error small">{data.basis_warning}</p>}
          <details className="note basis">
            <summary>계산 방법 · 큐브 메소 재설정 비용 기준</summary>
            <p className="muted small">{data.note}</p>
            {data.value_ranking?.length > 0 && <p className="muted small">{data.value_note} {data.market_note}</p>}
          </details>
          {data.value_ranking?.length > 0 && (
            <>
              {/* 카드 2단 · 오른쪽 위는 실딜%(효과) 크게, 순위 기준인 1억 메소당은 아래 줄 — 2026-10-11 사용자 결정
                  (심사 6회차는 억당을, 7회차는 실딜을 크게 하라고 엇갈렸다) */}
              {budget && inside.length > 0 && inside.length < ranked.length && (
                <p className="rank-budget-note small"><span className="basis-k">내 메소 기준</span>직접 큐브 평균이 넣으신 메소 안에 드는 것부터 보여 드려요. 번호는 전체 순위 그대로예요.</p>
              )}
              <ol className="rank-cards" aria-label="가격 대비 순위">
                {shown.map(({ v, rank, over }, i) => (
                  <Fragment key={`${v.slot}-${v.kind}`}>
                  <li className={`rank-card${i === 0 ? " top1" : ""}${over ? " over-budget" : ""}`}>
                    <div className="rank-top">
                      <span className={`medal medal-${rank}`}>{rank}</span>
                      <span className="rank-slot"><strong>{v.slot} {v.kind}</strong><span className="muted">{v.name}</span></span>
                      <span className="rank-eff" title="이 단계까지 올리면 오르는 보스 실딜">
                        <span className="rank-eff-k">보스 실딜</span><strong className="num">{formatPct(v.delta_pct)}</strong></span>
                    </div>
                    {/* 칩 = 게임 경매장 상세 검색 칸 순서(부위 → 등급 → 1·2·3줄, 각 줄은 '이상') */}
                    {i === 0 && <span className="cond-head"><span className="step-tag">{stepName(2)}</span>게임 경매장 › 상세 검색에 이 조건을 넣어 검색해요</span>}
                    <ul className="rank-cond" aria-label="경매장 검색 조건">
                      <li className="cond-slot"><span className="cond-k">부위</span>{v.slot}</li>
                      <li className={`cond-grade ${gradeClass(v.grade)}`}><span className="cond-k">{v.kind}</span>{v.grade}</li>
                      {v.target.map((t, k) => <li key={k}><span className="cond-k">{k + 1}줄</span>{t} 이상</li>)}
                    </ul>
                    <div className="rank-cost">
                      <span className="eff-value" title="순위 기준">1억 메소당 <strong className="num">{formatPct(v.per_100m)}</strong></span>
                      <span className="muted" title="이 옵션을 내 템에 큐브로 직접 띄울 때 드는 평균 메소">직접 큐브 평균 <strong className="num">{v.cube_cost_text}</strong></span>
                    </div>
                    <span className="eff" aria-hidden="true"><span className="bar" style={{ width: `${best > 0 ? Math.max(4, (100 * (v.per_100m || 0)) / best) : 0}%` }} /></span>
                    {i === 0 && v.route !== "큐브" && v.cube_cost_text && (
                      <p className="rank-buy small">경매장에 이 조건의 매물이 <strong>{v.cube_cost_text}</strong>보다 싸면 사는 쪽이, 비싸면 큐브를 직접 돌리는 쪽이 이득이에요.</p>
                    )}
                    {/* 넣은 예산보다 큐브 평균이 비싸면 그렇게 말한다(3회차 심사: 50억을 넣어도 105억짜리 1위가 그대로 강조됐다) */}
                    {over && (
                      <p className="rank-over small"><span className="basis-k">예산 밖</span>직접 큐브로는 넣으신 메소를 넘어요 — 경매장에 예산 안의 매물이 있는지만 찾아보세요.</p>
                    )}
                    {v.market && <p className="rank-market muted small">{marketText(v.market)}</p>}
                    {/* 아래 줄(2026-10-17 사용자): 게임 경매장은 드롭다운이라 복사할 곳이 없다 → 칩대로 검색한 뒤
                        화면 공유로 매물을 평가하는 버튼(PC). 휴대폰은 화면 공유가 안 돼 안내만. 못 사는 템은 큐브 계산기 */}
                    <div className={`rank-foot${v.route !== "큐브" && i > 0 ? " foot-pc" : ""}`}>
                      {v.route !== "큐브" ? (onEvaluate && (
                        <>
                          {i === 0 && <span className="cond-head pc-only-inline"><span className="step-tag">{stepName(3)}</span>검색 결과가 보이면</span>}
                          <button type="button" className={`rank-copy pc-only-inline${i === 0 ? "" : " ghost small"}`} onClick={() => onEvaluate(v)}>
                            검색 화면 공유해서 매물 읽기</button>
                          {i === 0 && <span className="small mobile-only-inline rank-mobile-note">{stepName(3)}부터는 PC에서 돼요 — PC에서 이 주소를 열면 검색 화면을 읽어 실제 딜을 계산해요.</span>}
                          {i === 0 && <CopyLink />}
                        </>
                      )) : (
                        // 경매장에서 못 사는 템(5회차: 다음 행동이 없었다) → 같은 자리·같은 모양으로 큐브 비용 계산기
                        <>
                          <a className={i === 0 ? "button-link" : "button-ghost"} href={hashFor({ page: "character", name, tab: "calc" })}>큐브 비용 계산하기</a>
                          <span className="muted small">경매장 구매 불가 템 — 지금 템에 큐브</span>
                        </>
                      )}
                      {i === 0 && v.route !== "큐브" && <span className="small pc-only-inline rank-help">브라우저가 공유할 창을 물어봐요 — 메이플 창을 고르면 매물의 옵션·가격을 읽어, 끼웠을 때 오르는 실딜을 계산해요.</span>}
                    </div>
                  </li>
                  {/* 화면 공유 칸(3·4단계)은 1위 카드 바로 아래 — 누르는 곳과 결과가 나오는 곳이 붙어 있어야 한다(4회차: 700px 떨어져 있었다) */}
                  {i === 0 && watch && <li className="rank-watch">{watch}</li>}
                  </Fragment>
                ))}
              </ol>
              {ordered.length > shown.length || showAll ? (
                <button type="button" className="ghost more-ranks" onClick={() => setShowAll(!showAll)}>
                  {showAll ? "순위 접기" : budget && inside.length
                    ? `나머지 순위 ${ordered.length - shown.length}개 더 보기(예산 밖 포함)` : `순위 ${ordered.length - shown.length}개 더 보기`}
                </button>
              ) : null}
            </>
          )}
          {!data.value_ranking?.length && watch}
          {after}
          {data.value_ranking?.length === 0 && data.slots.length === 0 && (
            <EmptyState icon="trend" title="올릴 수 있는 단계를 찾지 못했어요">지금 장비 기준으로 계산된 단계가 없어요.</EmptyState>
          )}
          <details className="more">
          <summary>부위별 다음 단계·모든 단계 보기</summary>
          <table aria-label="부위별 다음 단계">
            <thead><tr><th>부위</th><th>지금</th><th>잠재 다음 단계</th><th>에디 다음 단계</th></tr></thead>
            <tbody>
              {data.slots.map((row) => (
                <tr key={row.slot}>
                  <td>
                    <strong>{row.slot}</strong>{row.route === "큐브" ? <span className="muted"> · 큐브(경매장 구매 불가 템)</span> : null}
                    <br /><span className="muted">{row.name}{row.starforce ? ` ${row.starforce}성` : ""}</span>
                  </td>
                  <td className="muted">{row.current["잠재"].join(" / ") || "—"}<br />{row.current["에디"].join(" / ") || "—"}</td>
                  {KINDS.map((k) => <td key={k}><Next row={row} kind={k} /></td>)}
                </tr>
              ))}
            </tbody>
          </table>
          {data.slots.map((row) => (
            <details key={row.slot}>
              <summary>{row.slot} 모든 단계</summary>
              {KINDS.map((k) => (
                <ul key={k} className="plain">
                  {row[k].map((t, i) => (
                    <li key={i}>{k} {label(t)} · {t.target.join(" / ")} · {formatPct(t.delta_pct)}
                      <span className="muted"> · 한 번에 나올 확률 {(t.probability * 100).toPrecision(2)}%{t.market ? ` · ${marketText(t.market)}` : ""}</span></li>
                  ))}
                </ul>
              ))}
            </details>
          ))}
          </details>
        </>
      )}
    </section>
  );
}
