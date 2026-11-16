import { useEffect, useState } from "react";
import { getArmorSets } from "./api.js";
import { formatPct } from "./format.js";
import { ErrorState, HowTo, PanelHead, RowsSkeleton } from "./ui/Guide.jsx";

// 방어구 세트 조합(2026-11-16 사용자: 카루타·앱솔·아케인·에테르넬을 어떤 조합으로 맞추는 게 나은지 — 3카5앱처럼).
// 계산은 서버 engine/market/armor_sets.py — 세트 구성이 같은 조합끼리는 템 자체 스탯이 가장 좋은 배치 하나만.
const STARS = [17, 18, 21, 22];
const FIRST = 10;

function piecesText(pieces) {
  return Object.entries(pieces)
    .filter(([, p]) => !p.kept)
    .map(([slot, p]) => `${slot} ${p.name} ${p.starforce}성`)
    .join(" · ");
}

export default function ArmorSetsPanel({ name, defense, autoLoad = false }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [star, setStar] = useState(18);
  const [more, setMore] = useState(false);

  const load = async (s = star) => {
    setBusy(true);
    setError(null);
    try {
      setData(await getArmorSets(name, defense, s));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => { if (autoLoad && name) load(); }, [autoLoad, name, defense]); // eslint-disable-line react-hooks/exhaustive-deps

  const all = data?.combos || [];
  const rows = more ? all : all.slice(0, FIRST);
  const isNow = (r) => Object.values(r.pieces).every((p) => p.kept);

  return (
    <section className="panel">
      <PanelHead title="방어구 세트 조합" icon="layers"
                 subtitle="방어구 7칸을 카루타·앱솔랩스·아케인셰이드·에테르넬로 어떻게 맞추면 실딜이 가장 높은지 비교해요(3카4앱, 4에테3아케인 같은 조합).">
        <label className="swap-star small">
          바꿀 템
          <select aria-label="바꿀 템 스타포스" value={star} disabled={busy}
                  onChange={(e) => { const s = Number(e.target.value); setStar(s); if (data || autoLoad) load(s); }}>
            {STARS.map((s) => <option key={s} value={s}>{s}성</option>)}
          </select>
        </label>
        <button type="button" className={autoLoad ? "ghost small" : undefined} onClick={() => load()} disabled={!name || busy}>
          {autoLoad ? (busy ? "계산 중…" : "다시 계산") : "조합 계산"}
        </button>
      </PanelHead>
      <HowTo steps={[
        <>조합 이름은 세트별 칸 수예요. 무기는 지금 무기 그대로라, 앱솔 무기를 끼는 3카5앱은 여기서 <strong>카루타 3 · 앱솔 4</strong>로 보여요.</>,
        <>바꾼 칸은 고른 스타포스로, 잠재·에디·추옵은 지금 그 칸 템 것을 옮긴다고 가정해요. 지금 템을 그대로 둔 칸은 적지 않아요.</>,
        <>세트 구성이 같은 조합 중에서는 가장 좋은 배치 하나만 보여 줘요. 가격은 안 봐요.</>,
      ]} />
      {busy && !data && <RowsSkeleton rows={4} />}
      {error && <ErrorState message={error.message} onRetry={() => load()} />}
      {data?.current && <p className="small">지금 세팅: <strong>{data.current.label}</strong> (0%)</p>}
      {data?.classics?.length > 0 && (
        <>
          <h4 className="small">대표 조합</h4>
          <table aria-label="대표 조합" className="paths-table">
            <thead>
              <tr><th>조합</th><th>세트 구성</th><th className="num">실딜</th><th>바꾸는 칸</th></tr>
            </thead>
            <tbody>
              {data.classics.map((r) => (
                <tr key={r.classic}>
                  <td><strong>{r.classic}</strong></td>
                  <td className="small">{r.label}</td>
                  <td className={`num ${r.delta_pct > 0 ? "pos" : r.delta_pct < 0 ? "neg" : ""}`}>{formatPct(r.delta_pct)}</td>
                  <td className="small">{piecesText(r.pieces) || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h4 className="small">전체 순위</h4>
        </>
      )}
      {rows.length > 0 && (
        <table aria-label="방어구 세트 조합" className="paths-table">
          <thead>
            <tr><th>#</th><th>조합</th><th className="num">실딜</th><th>바꾸는 칸</th><th>세트 변화</th></tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.label} className={isNow(r) ? "is-now" : undefined}>
                <td>{i + 1}</td>
                <td><strong>{r.label}</strong>{isNow(r) && <span className="muted small"> · 지금</span>}</td>
                <td className={`num ${r.delta_pct > 0 ? "pos" : r.delta_pct < 0 ? "neg" : ""}`}>{formatPct(r.delta_pct)}</td>
                <td className="small">{piecesText(r.pieces) || "—"}</td>
                <td className="small">{r.set_change.map((s) => `${s.set} ${s.before}→${s.after}`).join(", ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {all.length > FIRST && (
        <button type="button" className="ghost small" onClick={() => setMore((v) => !v)}>
          {more ? `위 ${FIRST}개만 보기` : `${all.length - FIRST}개 더 보기`}
        </button>
      )}
      {data?.note && <p className="muted small">{data.note}</p>}
    </section>
  );
}
