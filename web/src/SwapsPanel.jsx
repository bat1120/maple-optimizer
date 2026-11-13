import { useEffect, useState } from "react";
import { getSwaps } from "./api.js";
import { formatPct } from "./format.js";
import { EmptyState, ErrorState, HowTo, PanelHead, RowsSkeleton } from "./ui/Guide.jsx";

// 다른 템으로 갈아타기(2026-11-13): 부위마다 다른 템(다른 세트)을 끼면 실딜이 어떻게 되는지와 손익분기(추옵·잠재).
// 가정한 템 수치는 넥슨 API 실측(그 템을 낀 캐릭터들의 장비) — 서버 engine/market/swaps.py

const best = (r) => (r.flame?.median ?? r.same);

export function potentialText(r) {
  const p = r.potential || {};
  if (p.none != null && p.none > 0) return "잠재 없어도 이득";
  if (p.break_even) return `${p.break_even.grade} ${p.break_even.target.join(" / ")} 이상`;
  if (r.same > 0) return `지금 잠재를 그대로 옮겨야 이득${p.ladder_skips?.length ? ` (${p.ladder_skips.join(", ")} 줄 유지)` : ""}`;
  return "어떤 잠재로도 손해";
}

// 보통 매물 기준(2026-11-13 실사용: 에디 없는 18성 레전드리 INT 3줄 커포링이 +0.08%뿐): 지금 템 추옵·에디는 옮길 수 없다 —
// 착용자 가운데 추옵 + 에디 없음일 때 잠재가 이 단계 이상이어야 이득
export function marketText(r) {
  const m = r.market;
  if (!m) return "—";
  if (m.none != null && m.none > 0) return "잠재 없어도 이득";
  if (m.break_even) return `${m.break_even.grade} ${m.break_even.target.join(" / ")} 이상`;
  return "어떤 잠재로도 손해";
}

function flameText(f) {
  if (!f || f.none) return "추옵 없음(안 붙는 템)";
  if (!f.samples) return "표본 없음";
  return `중앙 ${formatPct(f.median)} · ${Math.round(f.better_share * 100)}%가 이득 (${f.samples}명)`;
}

export default function SwapsPanel({ name, defense, autoLoad = false }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showLoss, setShowLoss] = useState(false);

  const load = async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await getSwaps(name, defense));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => { if (autoLoad && name) load(); }, [autoLoad, name, defense]); // eslint-disable-line react-hooks/exhaustive-deps

  const all = data?.swaps || [];
  const gain = all.filter((r) => best(r) > 0);
  const loss = all.length - gain.length;
  const rows = showLoss ? all : gain;

  return (
    <section className="panel">
      <PanelHead title="다른 템으로 갈아타기" icon="layers"
                 subtitle="지금 템 대신 다른 템(다른 세트)을 끼면 세트 효과까지 바뀌어 실딜이 어떻게 되는지, 어느 수준 이상이어야 이득인지 알려 드려요.">
        <button type="button" className={autoLoad ? "ghost small" : undefined} onClick={load} disabled={!name || busy}>
          {autoLoad ? (busy ? "계산 중…" : "다시 계산") : "갈아타기 계산"}
        </button>
      </PanelHead>
      <HowTo steps={[
        <><strong>그대로 옮기면</strong> = 성·잠재·에디·추옵·주문서를 지금 템과 같게 두고 템만 바꿨을 때의 실딜이에요. 세트 효과 변화가 들어가 있어요.</>,
        <><strong>추옵</strong> = 그 템을 실제로 낀 캐릭터들의 추옵으로 바꿔 본 분포예요. '%가 이득'은 그중 지금보다 나아지는 비율이에요.</>,
        <><strong>잠재</strong> = 그 템에 이 단계 이상을 띄우면 지금보다 나아져요(추옵·에디는 지금 템과 같게).</>,
        <><strong>보통 매물이면</strong> = 추옵은 착용자들 가운데 수준, 에디는 없는 매물일 때 잠재가 이 단계 이상이어야 이득이에요. 경매장에서 고를 때는 이 기준을 보세요.</>,
        <>템 수치는 넥슨 API 실측이고, 레벨이 높은 템은 잠재·추옵이 더 높게 나올 수 있어 보수적인 값이에요. 익셉셔널은 옮기지 않아요.</>,
      ]} />
      {busy && !data && <RowsSkeleton rows={4} />}
      {error && <ErrorState message={error.message} onRetry={load} />}
      {data && !gain.length && !showLoss && (
        <EmptyState title="지금 장비보다 나은 갈아타기 후보가 없어요">
          {loss ? "세트 효과를 잃는 손해가 더 커요." : "비교할 수 있는 템이 없어요."}
        </EmptyState>
      )}
      {rows.length > 0 && (
        <table aria-label="다른 템으로 갈아타기" className="paths-table">
            <thead>
              <tr><th>부위</th><th>지금 → 바꿀 템</th><th>세트 변화</th><th className="num">그대로 옮기면</th><th>추옵</th><th>잠재(추옵·에디 그대로)</th><th>보통 매물이면</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.slot}-${r.name}`}>
                  <td>{r.slot}</td>
                  <td>{r.current.name} → {r.name}<div className="muted small">{r.level}레벨 · {r.starforce}성으로 가정</div></td>
                  <td className="small">{r.set_change.map((s) => `${s.set} ${s.before}→${s.after}`).join(", ") || "변화 없음"}</td>
                  <td className={`num ${r.same > 0 ? "pos" : "neg"}`}>{formatPct(r.same)}</td>
                  <td className="small">{flameText(r.flame)}</td>
                  <td className="small">{potentialText(r)}</td>
                  <td className="small">{marketText(r)}</td>
                </tr>
              ))}
            </tbody>
        </table>
      )}
      {data && loss > 0 && (
        <button type="button" className="ghost small" onClick={() => setShowLoss((v) => !v)}>
          {showLoss ? "이득인 후보만 보기" : `손해인 후보도 보기 (${loss})`}
        </button>
      )}
      {data?.note && <p className="muted small">{data.note}</p>}
    </section>
  );
}
