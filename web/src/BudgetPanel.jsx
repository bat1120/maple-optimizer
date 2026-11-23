import { useState } from "react";
import { getBudgetRoadmap } from "./api.js";
import { parsePrice } from "./format.js";
import { RowsSkeleton } from "./ui/Guide.jsx";

// 내 메소로 어디까지(2026-11-23): 이 서비스의 목적은 '지금 가진 재화로 스펙을 어디까지 올리는 게 적당한가'인데
// 화면에 메소를 넣는 칸이 없었다(디자인 심사: 1위가 평균 105억이라 50억 가진 사람에게는 쓸 수 없는 추천).
// 계산은 서버(예산 로드맵) — 여기서는 금액을 메소로 바꿔 보내고 결과를 그대로 보여 준다.
const QUICK = ["10억", "50억", "100억", "300억"];
const MIN = 10_000;
const pct = (x) => `+${Number(x).toFixed(2)}%`;

export function stepLabel(s) {
  if (s.path === "스타포스") return `${s.name} ${s.from_star}→${s.to_star}성`;
  if (s.path === "추옵") return `${s.slot} 추옵 재설정`;
  if (s.path === "큐브") return `${s.slot} ${s.kind} ${s.grade || ""}`.trim();
  if (s.path === "심볼") return s.from_level != null ? `${s.name} ${s.from_level}→${s.to_level}레벨` : s.name;
  return s.name;
}
const stepSub = (s) => (s.path === "큐브" && s.target?.length ? s.target.join(" / ") : s.path === "추옵" ? s.name : null);
// 그 단계를 어디서 하는지 — 목록만 있고 다음 행동이 없었다(2026-11-23 심사 2회차)
export const HOW = { 추옵: "게임에서 추가옵션 재설정", 스타포스: "게임에서 스타포스 강화", 큐브: "경매장 구매 또는 큐브 — 아래 순위", 심볼: "게임에서 심볼 강화" };
const how = (s) => HOW[s.path] || (String(s.path).startsWith("HEXA") ? "게임에서 HEXA 강화" : s.path);

export default function BudgetPanel({ name, defense }) {
  const [text, setText] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const run = async (value) => {
    const meso = parsePrice(value);
    if (!meso || meso < MIN) {
      setError({ message: "가진 메소를 '50억'이나 '12억 5000만'처럼 적어 주세요." });
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setData(await getBudgetRoadmap(name, defense, meso));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const submit = (e) => { e.preventDefault(); run(text); };
  const pick = (q) => { setText(q); run(q); };

  return (
    <section className="budget-panel" aria-label="내 메소로 어디까지">
      <form className="budget-form" onSubmit={submit}>
        <h3 className="budget-title">내 메소로 어디까지 올릴 수 있을까?</h3>
        <input aria-label="가진 메소" inputMode="text" autoComplete="off" placeholder="예: 50억" value={text}
               aria-invalid={error && !data ? "true" : undefined} onChange={(e) => setText(e.target.value)} />
        <button type="submit" disabled={busy}>{busy ? "계산 중…" : "계산하기"}</button>
        <span className="budget-quick" aria-label="자주 쓰는 금액">
          {QUICK.map((q) => <button key={q} type="button" className="pill" disabled={busy} onClick={() => pick(q)}>{q}</button>)}
        </span>
      </form>
      {error && <p role="alert" className="inline-error"><strong>{error.message}</strong></p>}
      {busy && !data && <RowsSkeleton rows={3} />}
      {data && (
        <div className="budget-result" aria-live="polite">
          {data.steps.length > 0 ? (
            <p className="budget-headline">
              <span><strong>{data.budget_text}</strong>이면 보스 실딜</span>
              <strong className="budget-gain num">{pct(data.gain_pct)}</strong>
              <span>까지 올릴 수 있어요</span>
              <span className="muted small budget-spend">{data.spent_text} 사용 · {data.left_text} 남음</span>
            </p>
          ) : (
            <p className="budget-headline"><span><strong>{data.budget_text}</strong>으로는 지금 할 수 있는 단계가 없어요.</span></p>
          )}
          {data.steps.length > 0 && (
            <p className="budget-cols muted small" aria-hidden="true"><span>순서 · 무엇을</span><span>평균 비용</span><span>여기까지 쓴 메소 · 누적 실딜</span></p>
          )}
          {data.steps.length > 0 && (
            <ol className="budget-steps" aria-label="예산 안에서 할 순서">
              {data.steps.map((s, i) => (
                <li key={i}>
                  <span className="budget-no">{i + 1}</span>
                  <span className="budget-what"><strong>{stepLabel(s)}</strong><span className="muted small">{[stepSub(s), how(s)].filter(Boolean).join(" · ")}</span></span>
                  <span className="budget-cost num">{s.cost_text}</span>
                  <span className="budget-sum muted small">여기까지 {s.total_cost_text} · <strong className="num">{pct(s.gain_pct_after)}</strong></span>
                </li>
              ))}
            </ol>
          )}
          {data.steps.length > 0 && <p className="muted small budget-rel">위 순서는 추옵·스타포스·심볼 같은 내 템 강화까지 포함해 같은 메소로 가장 많이 오르는 순서예요. 아래 순위는 그중 경매장에서 찾아볼 잠재·에디만 모은 거예요.</p>}
          {data.next_step && (
            <p className="budget-next">
              <span className="basis-k">다음 목표</span>
              <strong>{stepLabel(data.next_step)}</strong> — 평균 {data.next_step.cost_text}, <strong>{data.next_step.short_text}</strong> 더 모으면 할 수 있어요.
            </p>
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
