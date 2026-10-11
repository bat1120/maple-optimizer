import { useEffect, useState } from "react";
import { getRoadmap } from "./api.js";
import { formatMeso, formatPct, settingLabel } from "./format.js";
import { EmptyState, HowTo, PanelHead, RowsSkeleton } from "./ui/Guide.jsx";
import { gradeClass } from "./character/grades.js";
import { hashFor } from "./router.js";

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

export default function RoadmapPanel({ name, defense, autoLoad = false, active = null }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [copied, setCopied] = useState(null);
  const [copiedText, setCopiedText] = useState("");
  // 경매장 검색 조건 그대로(게임 경매장에서 이 조건으로 찾는다) — 2026-10-11 심사: 순위 카드에서 바로 경매장으로
  const condition = (v) => `${v.slot} · ${v.kind} ${v.grade} · ${v.target.join(" / ")}`;
  const copy = async (v) => { try { await navigator.clipboard.writeText(condition(v)); setCopied(`${v.slot}-${v.kind}`); setCopiedText(condition(v)); } catch { /* 복사 못 하면 조용히 */ } };

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

  return (
    <section className="panel">
      {/* 2026-10-11 심사 3회차: 1위 카드까지 제목 2개·접힘 2개를 지나야 했다 → 제목 하나, 기준은 접힘 하나 */}
      <PanelHead title="가격 대비 업그레이드 순위" icon="trend"
                 subtitle="잠재·에디를 올렸을 때 1억 메소당 보스 실딜이 많이 오르는 순서예요(같은 메소로 더 많이 오르는 게 위).">
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
          <details className="note basis">
            <summary>계산 방법 · 큐브 메소 재설정 비용 기준</summary>
            <p className="muted small">{data.note}</p>
            {data.value_ranking?.length > 0 && <p className="muted small">{data.value_note} {data.market_note}</p>}
          </details>
          {data.value_ranking?.length > 0 && (
            <>
              {/* 카드 2단 · 오른쪽 위는 실딜%(효과) 크게, 순위 기준인 1억 메소당은 아래 줄 — 2026-10-11 사용자 결정
                  (심사 6회차는 억당을, 7회차는 실딜을 크게 하라고 엇갈렸다) */}
              <ol className="rank-cards" aria-label="가격 대비 순위">
                {(showAll ? data.value_ranking : data.value_ranking.slice(0, TOP)).map((v, i) => (
                  <li key={`${v.slot}-${v.kind}`} className={`rank-card${i === 0 ? " top1" : ""}`}>
                    <div className="rank-top">
                      <span className={`medal medal-${i + 1}`}>{i + 1}</span>
                      <span className="rank-slot"><strong>{v.slot} {v.kind}</strong><span className="muted">{v.name}</span></span>
                      <span className="rank-eff" title="이 단계까지 올리면 오르는 보스 실딜">
                        <span className="rank-eff-k">보스 실딜</span><strong className="num">{formatPct(v.delta_pct)}</strong></span>
                    </div>
                    {/* 칩 = 게임 경매장 상세 검색 칸 순서(부위 → 등급 → 1·2·3줄, 각 줄은 '이상') */}
                    {i === 0 && <span className="cond-head">경매장 상세 검색</span>}
                    <ul className="rank-cond" aria-label="경매장 검색 조건">
                      <li className="cond-slot"><span className="cond-k">부위</span>{v.slot}</li>
                      <li className={`cond-grade ${gradeClass(v.grade)}`}><span className="cond-k">{v.kind}</span>{v.grade}</li>
                      {v.target.map((t, k) => <li key={k}><span className="cond-k">{k + 1}줄</span>{t} 이상</li>)}
                    </ul>
                    <div className="rank-cost">
                      <span className="eff-value" title="순위 기준">1억 메소당 <strong className="num">{formatPct(v.per_100m)}</strong></span>
                      <span className="muted">큐브 평균 <strong className="num">{v.cube_cost_text}</strong></span>
                    </div>
                    <span className="eff" aria-hidden="true"><span className="bar" style={{ width: `${best > 0 ? Math.max(4, (100 * (v.per_100m || 0)) / best) : 0}%` }} /></span>
                    {v.market && <p className="rank-market muted small">{marketText(v.market)}</p>}
                    {/* 아래 줄은 모든 카드가 같은 높이: 살 수 있으면 복사, 못 사면 같은 자리에 안내 칩 */}
                    <div className="rank-foot">
                      {v.route !== "큐브" ? (
                        <button type="button" className={`rank-copy${i === 0 ? "" : " ghost small"}`} onClick={() => copy(v)}>
                          {copied === `${v.slot}-${v.kind}` ? "복사됨 ✓" : "경매장 검색 조건 복사"}</button>
                      ) : (
                        // 경매장에서 못 사는 템(5회차: 다음 행동이 없었다) → 같은 자리·같은 모양으로 큐브 비용 계산기
                        <>
                          <a className={i === 0 ? "button-link" : "button-ghost"} href={hashFor({ page: "character", name, tab: "calc" })}>큐브 비용 계산하기</a>
                          <span className="muted small">경매장 구매 불가 템 — 지금 템에 큐브</span>
                        </>
                      )}
                      {i === 0 && v.route !== "큐브" && <span className="muted small">게임 경매장 › 상세 검색에서 위 칩 순서대로 고르세요</span>}
                    </div>
                  </li>
                ))}
              </ol>
              <p className="copy-status muted small" role="status">
                {copied ? `복사했어요: ${copiedText} — 메모해 두고 게임 경매장 › 상세 검색에서 칩 순서대로 고르세요.` : ""}
              </p>
              {data.value_ranking.length > TOP && (
                <button type="button" className="ghost more-ranks" onClick={() => setShowAll(!showAll)}>
                  {showAll ? "순위 접기" : `순위 ${data.value_ranking.length - TOP}개 더 보기`}
                </button>
              )}
            </>
          )}
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
