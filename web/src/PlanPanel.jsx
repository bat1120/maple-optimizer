import { useEffect, useState } from "react";
import { getBudgetRoadmap } from "./api.js";
import { parsePrice } from "./format.js";
import { hashFor } from "./router.js";
import { stepName } from "./flow.js";
import { EmptyState, PanelHead, RowsSkeleton } from "./ui/Guide.jsx";

// 내 업그레이드 계획(2026-11-23 사용자: 계획 하나로 합친다).
// 전에는 '내 메소로' 계획표와 '가격 대비 순위' 카드가 따로 있어, 메소를 넣으면 서로 다른 답을 냈다(디자인 심사 5회차 공통 지적).
// 이제 답은 이 목록 하나다: 같은 메소로 실딜이 많이 오르는 순서. 가진 메소를 넣으면 그 안에서 끊는다.
// 경매장에서 살 수 있는 줄(큐브 · route '경매장')은 눌러서 2단계(검색 조건) → 3단계(화면 공유) → 4단계(실딜)로 이어진다.
const QUICK = ["10억", "50억", "100억", "300억"];
const MIN = 10_000;
const FIRST = 6; // 처음에 보이는 줄 수
const pct = (x, d = 2) => `+${Number(x).toFixed(d)}%`;

export function stepLabel(s) {
  if (s.path === "스타포스") return `${s.name} ${s.from_star}→${s.to_star}성`;
  if (s.path === "추옵") return `${s.slot} 추옵 재설정`;
  if (s.path === "큐브") return `${s.slot} ${s.kind} ${s.grade || ""}${s.lines_good ? ` ${s.lines_good}줄` : ""}`.trim();
  if (s.path === "심볼") return s.from_level != null ? `${s.name} ${s.from_level}→${s.to_level}레벨` : s.name;
  return s.name;
}
// 그 줄을 어디서 하는지 — 목록만 있고 다음 행동이 없었다(심사 2회차)
export const HOW = { 추옵: "게임에서 추가옵션 재설정", 스타포스: "게임에서 스타포스 강화", 심볼: "게임에서 심볼 강화" };
const how = (s) => (s.path === "큐브" ? (s.route === "경매장" ? "경매장에서 사거나 큐브" : "지금 템에 큐브(경매장 구매 불가 템)")
  : HOW[s.path] || (String(s.path).startsWith("HEXA") ? "게임에서 HEXA 강화" : s.path));
const stepSub = (s) => (s.path === "큐브" && s.target?.length ? s.target.join(" / ") : s.path === "추옵" || s.path === "큐브" ? s.name : null);
export const buyable = (s) => s.path === "큐브" && s.route === "경매장";

// 휴대폰 → PC로 넘기기(심사 2회차: '휴대폰에서는 여기까지'에서 흐름이 끊겼다)
function CopyLink() {
  const [done, setDone] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(window.location.href); setDone(true); } catch { setDone(false); }
  };
  return <button type="button" className="ghost small mobile-only-inline copy-link" onClick={copy}>{done ? "주소를 복사했어요" : "이 화면 주소 복사"}</button>;
}

// onEvaluate(step): 그 줄의 조건으로 화면 공유 평가를 연다. watch: 화면 공유 칸(하나뿐인 인스턴스 — 공유 세션이 끊기지 않게
// 다시 만들지 않고, CSS order로 고른 줄 바로 아래에 보이게만 한다). onStage(n): 지금 단계(1 추천 · 2 검색 조건 · 3 화면 공유)
export default function PlanPanel({ name, defense, onEvaluate = null, watch = null, onStage = null }) {
  const [text, setText] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [all, setAll] = useState(false);
  const [open, setOpen] = useState(null);     // 검색 조건을 펼친 줄
  const [shared, setShared] = useState(null); // 화면 공유를 누른 줄 — 그 아래에 공유 칸이 온다

  const load = async (meso) => {
    setBusy(true);
    setError(null);
    try {
      setData(await getBudgetRoadmap(name, defense, meso));
      setOpen(null); setShared(null); setAll(false);
      onStage?.(1);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => { if (name) load(null); }, [name, defense]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = (value) => {
    const meso = parsePrice(value);
    if (!meso || meso < MIN) {
      setError({ message: "가진 메소를 '50억'이나 '12억 5000만'처럼 적어 주세요." });
      return;
    }
    load(meso);
  };
  const submit = (e) => { e.preventDefault(); run(text); };
  const pick = (q) => { setText(q); run(q); };
  const toggle = (i) => { const next = open === i ? null : i; setOpen(next); if (shared == null) onStage?.(next == null ? 1 : 2); };
  const share = (s, i) => { setShared(i); onStage?.(3); onEvaluate?.(s); };

  // 예산이 모자라 건너뛴 다음 목표도 같은 목록의 마지막 줄로 둔다 — 경매장에서 살 수 있으면 예산 안의 매물을 찾아볼 수 있다
  // 계획에 경매장에서 살 수 있는 줄이 하나도 없으면 '경매장에서 찾는다면'(살 수 있는 것 중 효율 1위)을 마지막에 붙인다 —
  // 실제 캐릭터에서 추옵·스타포스·심볼만으로 계획이 차서 2~4단계로 갈 길이 없었다(2026-11-23)
  const planned = [...(data?.steps || []), ...(data?.next_step ? [{ ...data.next_step, isNext: true }] : [])];
  const steps = [...planned, ...(data?.auction_pick && !planned.some(buyable) ? [{ ...data.auction_pick, isPick: true }] : [])];
  const done = data?.steps?.length || 0;
  // 처음엔 앞의 FIRST줄 + 경매장에서 살 수 있는 첫 줄(뒤쪽에 있어도) — 그 줄이 안 보이면 2~4단계로 갈 길이 없다
  const firstBuy = steps.findIndex(buyable);
  const keep = new Set([firstBuy, open, shared, data?.next_step ? done : null].filter((i) => i != null && i >= 0));
  // 메소를 넣었으면 그 메소로 하는 줄을 전부 보여 준다 — '47억을 쓴다'면서 6줄(18억)까지만 보이면 무엇을 사는지 알 수 없다(6회차 심사)
  const first = data?.budget_text ? done : FIRST;
  const shown = steps.map((s, i) => ({ s, i })).filter(({ i }) => all || i < first || keep.has(i));
  return (
    <section className="panel plan-panel" aria-label="내 업그레이드 계획">
      <PanelHead title="내 업그레이드 계획" icon="trend"
                 subtitle="같은 메소로 보스 실딜이 많이 오르는 순서예요. 위에서부터 하면 돼요." />
      <form className="budget-form" onSubmit={submit}>
        <label className="budget-label" htmlFor="plan-budget">가진 메소를 넣으면 그 안에서 끊어 드려요</label>
        <input id="plan-budget" aria-label="가진 메소" inputMode="text" autoComplete="off" placeholder="예: 50억" value={text}
               onChange={(e) => setText(e.target.value)} />
        <button type="submit" disabled={busy}>{busy ? "계산 중…" : "계산하기"}</button>
        <span className="budget-quick" aria-label="자주 쓰는 금액">
          {QUICK.map((q) => <button key={q} type="button" className="pill" disabled={busy} onClick={() => pick(q)}>{q}</button>)}
        </span>
      </form>
      {error && <p role="alert" className="inline-error"><strong>{error.message}</strong></p>}
      {busy && !data && <RowsSkeleton rows={5} />}
      {data && (
        <div className="budget-result" aria-live="polite">
          {data.budget_text && (done > 0 ? (
            <p className="budget-headline">
              <span><strong>{data.budget_text}</strong>이면 보스 실딜</span>
              <strong className="budget-gain num">{pct(data.gain_pct)}</strong>
              <span>까지 올릴 수 있어요</span>
              <span className="muted small budget-spend">{data.spent_text} 사용 · {data.left_text} 남음</span>
            </p>
          ) : (
            <p className="budget-headline"><span><strong>{data.budget_text}</strong>으로는 지금 할 수 있는 단계가 없어요.</span></p>
          ))}
          {!data.budget_text && steps.length === 0 && (
            <EmptyState icon="trend" title="올릴 수 있는 단계를 찾지 못했어요">지금 장비 기준으로 계산된 단계가 없어요.</EmptyState>
          )}
          {steps.length > 0 && (
            <>
              <p className="plan-cols muted small" aria-hidden="true"><span>순서 · 무엇을</span><span>1억 메소당</span><span>평균 비용</span><span>여기까지 · 누적 실딜</span></p>
              <ol className="plan-steps" aria-label="할 순서">
                {shown.map(({ s, i }, n) => (
                  <li key={i} className={`plan-row${open === i ? " is-open" : ""}${(n > 0 && shown[n - 1].i !== i - 1) || s.isPick ? " after-gap" : ""}`}
                      style={{ order: i * 2 }} data-gap={n > 0 && shown[n - 1].i !== i - 1 ? `${shown[n - 1].i + 2}~${i}번은 '모두 보기'에 있어요${i === firstBuy ? " — 아래는 경매장에서 살 수 있는 첫 순서라 먼저 보여 드려요" : ""}` : s.isPick ? "위 순서에는 경매장에서 살 수 있는 것이 없어요 — 경매장에서 찾아본다면 효율이 가장 좋은 것은" : undefined}>
                    <div className="plan-line">
                      <span className={`plan-no${s.isNext || s.isPick ? " is-next" : ""}`}>{s.isNext ? "다음" : s.isPick ? "경매장" : i + 1}</span>
                      <span className="plan-what"><strong>{stepLabel(s)}</strong>
                        <span className="muted small">{[stepSub(s), how(s)].filter(Boolean).join(" · ")}</span></span>
                      {/* 큰 숫자 = 순서의 기준인 1억 메소당 효율(2026-11-23 사용자 결정 — 전에는 보스 실딜이 커서 순서가 틀린 것처럼 보였다) */}
                      <span className="plan-eff" title="이 순서의 기준: 1억 메소를 쓸 때 오르는 보스 실딜"><strong className="num">{pct(s.per_100m, 3)}</strong></span>
                      {/* 비용·누적은 한 묶음: PC에서는 칸 두 개(display: contents), 휴대폰에서는 한 줄로 나란히 */}
                      <span className="plan-meta">
                        <span className="plan-cost num">{s.cost_text}</span>
                        {s.isPick
                          ? <span className="plan-sum muted small">경매장에서 찾는다면 이것부터</span>
                          : s.isNext
                          ? <span className="plan-sum muted small">큐브로는 <strong className="plan-short">{s.short_text}</strong> 더 필요</span>
                          : <span className="plan-sum muted small">{s.total_cost_text} · <strong className="num">{pct(s.gain_pct_after)}</strong></span>}
                      </span>
                      <span className="plan-act">
                        {buyable(s) ? (
                          <button type="button" className={open === i || i === firstBuy ? "small" : "ghost small"} aria-expanded={open === i} onClick={() => toggle(i)}>
                            {open === i ? "접기" : "경매장에서 찾기"}</button>
                        ) : s.path === "큐브" ? (
                          <a className="button-ghost" href={hashFor({ page: "character", name, tab: "calc" })}>큐브 비용 계산</a>
                        ) : null}
                      </span>
                    </div>
                    {open === i && (
                      <div className="plan-detail">
                        <p className="cond-head"><span className="step-tag">{stepName(2)}</span>게임 경매장 › 상세 검색에 이 조건을 넣어 검색해요</p>
                        {/* 칸 = 게임 경매장 상세 검색 칸 순서(부위 → 등급 → 1·2·3줄, 각 줄은 '이상') */}
                        <ul className="rank-cond cond-form" aria-label="경매장 검색 조건">
                          <li className="cond-slot"><span className="cond-k">부위</span>{s.slot}</li>
                          <li><span className="cond-k">{s.kind} 등급</span>{s.grade}</li>
                          {(s.target || []).map((t, k) => <li key={k}><span className="cond-k">옵션 {k + 1}</span>{t} 이상</li>)}
                        </ul>
                        <p className="rank-buy small">매물이 <strong>{s.cost_text}</strong>보다 싸면 사는 쪽이, 비싸면 내 템에 큐브를 직접 돌리는 쪽이 이득이에요.</p>
                        <p className="cond-head pc-only-inline"><span className="step-tag">{stepName(3)}</span>검색 결과가 보이면
                          <button type="button" className="rank-copy" onClick={() => share(s, i)}>화면 공유 칸 열기</button></p>
                        <p className="small rank-help pc-only-inline">바로 아래에 공유 칸이 열려요. 거기서 [경매장 화면 연결]을 누르고 메이플 창을 고르면, 매물의 옵션·가격을 읽어 끼웠을 때 오르는 실딜을 보여 드려요.</p>
                        <p className="small mobile-only-inline rank-mobile-note">{stepName(3)}부터는 PC에서 돼요 — PC에서 이 주소를 열면 검색 화면을 읽어 실제 딜을 계산해요.</p>
                        <CopyLink />
                      </div>
                    )}
                  </li>
                ))}
                {/* 화면 공유 칸(3·4단계): 공유를 누른 줄 바로 아래에 보인다. 다른 곳(잠재·에디 순위)에서 열면 목록 맨 아래 */}
                {watch && <li className="plan-watch" style={{ order: shared != null ? shared * 2 + 1 : 9999 }}>{watch}</li>}
              </ol>
              {steps.length > shown.length || all ? (
                <button type="button" className="ghost more-ranks" onClick={() => setAll(!all)}>
                  {all ? "처음 단계만 보기" : `${done}단계 모두 보기`}
                </button>
              ) : null}
            </>
          )}
          {data.basis_warning && <p role="note" className="error small">{data.basis_warning}</p>}
          <details className="note basis">
            <summary>계산 방법 · 들어 있지 않은 비용</summary>
            <p className="muted small">{data.note}</p>
          </details>
        </div>
      )}
    </section>
  );
}
