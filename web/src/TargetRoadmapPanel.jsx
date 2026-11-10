import { useState } from "react";
import { getTargetRoadmap } from "./api.js";
import { clipboardText } from "./scouter.js";
import { HowTo, PanelHead } from "./ui/Guide.jsx";

// 목표 보스 배율 로드맵(2026-10-09): MapleScouter 효율·보스컷의 배율(예: 익스트림 스우 34.52%)에서 목표(50%)까지.
// 지금 배율은 사용자가 직접 보고 넣는다. MapleScouter에 자동으로 넣어 읽던 확장 연동은 뺐다(2026-10-13, 운영자 연동 불가).
// 보스 선택: 지금 배율을 본 그 보스로 계산한다. 키는 사용자가 배율을 확인하는 보스컷의 보스 구분
export const BOSSES = [
  ["extreme_lotus", "익스트림 스우"], ["extreme_adversary", "익스트림 최초의 대적자"], ["extreme_kaling", "익스트림 카링"],
  ["extreme_kalos", "익스트림 칼로스"], ["extreme_seren", "익스트림 세렌"], ["extreme_blackMage", "익스트림 검은 마법사"],
  ["destiny_seren", "데스티니 세렌"], ["champion_kalos", "챔피언 칼로스"], ["champion_seren", "챔피언 세렌"],
  ["champion_blackMage", "챔피언 검은 마법사"],
];
// MapleScouter 보스 → 우리 보스 목록 id(engine/data/bosses.json). 계산(방어율·요구 포스)을 이 보스로 한다(2026-10-17 —
// 전에는 패널 보스가 MapleScouter 확인에만 쓰이고 계산은 페이지 위쪽 보스였다). 목록에 없는 보스는 위쪽 보스로 계산
export const ENGINE_BOSS = {
  extreme_lotus: "lotus-extreme", extreme_adversary: "adversary-extreme", extreme_kaling: "kaling-extreme",
  extreme_kalos: "kalos-extreme", extreme_seren: "seren-extreme-2", extreme_blackMage: "blackmage-extreme",
};

function stepLabel(s) {
  if (s.path === "스타포스") return `${s.name} ${s.from_star}→${s.to_star}성`;
  if (s.path === "큐브") return `${s.slot} ${s.kind} ${s.grade} ${s.lines_good}줄`;
  if (s.path === "심볼") return `${s.name} ${s.from_level}→${s.to_level}레벨${s.remaining_symbols > 0 ? ` (심볼 ${s.remaining_symbols.toLocaleString("ko-KR")}개 더)` : ""}`;
  return s.name;
}

export default function TargetRoadmapPanel({ name, defense }) {
  const [boss, setBoss] = useState(BOSSES[0][0]);
  const [current, setCurrent] = useState("");
  const [target, setTarget] = useState("50");
  const [fragMan, setFragMan] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(clipboardText(data.scouter)); setCopied(true); } catch { setCopied(false); }
  };

  const load = async () => {
    setBusy(true); setError(null); setCopied(false);  // 새 로드맵은 아직 복사 안 함
    try {
      setData(await getTargetRoadmap(name, ENGINE_BOSS[boss] || defense, { current: Number(current), target: Number(target), fragmentMan: fragMan }));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel">
      <PanelHead title="목표 배율 로드맵" icon="trend"
                 subtitle="보스 배율을 목표까지 올리려면 무엇을 어떤 순서로 하면 되는지, 억당 효율 순으로 쌓아 보여 줘요." />
      <HowTo steps={[
        <>MapleScouter <strong>효율·보스컷</strong>에서 그 보스의 지금 배율(예: 34.52%)을 보고 아래에 넣어요.</>,
        <>목표 배율(기본 50%)과, HEXA까지 보려면 조각 1개 값을 넣고 <strong>로드맵 만들기</strong>.</>,
      ]} />
      <div className="inline wrap">
        <label className="inline">보스 <select aria-label="보스" value={boss} onChange={(e) => setBoss(e.target.value)}>
          {BOSSES.map(([k, n]) => <option key={k} value={k}>{n}</option>)}
        </select></label>
        <label className="inline">지금 배율(%) <input aria-label="지금 배율(%)" inputMode="decimal" value={current} placeholder="34.52"
          onChange={(e) => setCurrent(e.target.value)} style={{ width: "6em" }} /></label>
        <label className="inline">목표 배율(%) <input aria-label="목표 배율(%)" inputMode="decimal" value={target}
          onChange={(e) => setTarget(e.target.value)} style={{ width: "5em" }} /></label>
        <label className="inline">조각 1개 값(만 메소) <input aria-label="로드맵 조각 값(만 메소)" inputMode="decimal" value={fragMan}
          placeholder="넣으면 HEXA 포함" onChange={(e) => setFragMan(e.target.value)} style={{ width: "8em" }} /></label>
        <button type="button" onClick={load} disabled={!name || busy || !(Number(current) > 0)}>{busy ? "계산 중…" : "로드맵 만들기"}</button>
      </div>
      {!ENGINE_BOSS[boss] && <p className="muted small">이 보스는 계산용 보스 목록에 없어서, 위쪽에서 고른 보스 기준으로 계산해요.</p>}
      {error && <p role="alert" className="error">{error.message}</p>}
      {data && (
        <>
          <p>
            필요한 딜 <strong>×{data.needed_multiplier.toFixed(3)}</strong> · 로드맵 끝 <strong>{data.final_ratio.toFixed(2)}%</strong>
            {data.reached ? " (목표 도달)" : data.stopped_at_max_steps ? " (단계 수 상한에서 멈췄어요 — 더 쌓으면 갈 수 있어요)" : " (이 계산으로는 목표에 못 미쳐요)"} · 누적 <strong>{data.total_cost_text}</strong>
          </p>
          <table aria-label="목표 배율 로드맵">
            <thead><tr><th>#</th><th>단계</th><th className="num">실딜</th><th className="num">비용</th><th className="num">누적 배율</th><th className="num">누적 비용</th></tr></thead>
            <tbody>
              {data.steps.map((s, i) => (
                <tr key={i}>
                  <td>{i + 1}</td><td>{s.path} · {stepLabel(s)}</td><td className="num">+{s.delta_pct.toFixed(2)}%</td>
                  <td className="num">{s.cost_text}</td><td className="num">{s.ratio_after.toFixed(2)}%</td><td className="num">{s.total_cost_text}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.scouter && (
            <p>
              <button type="button" className="ghost small" onClick={copy}>변화량 복사</button>{" "}
              <span className="muted small">{copied ? "복사했어요" : "장비 변화(큐브·스타포스·HEXA 스탯·심볼)를 글로 — 다른 계산기와 손으로 비교할 때"}</span>
            </p>
          )}
          {data.basis_warning && <p role="note" className="error small">{data.basis_warning}</p>}
          <details className="note"><summary>계산 기준 보기</summary><p className="muted small">{data.note}</p></details>
        </>
      )}
    </section>
  );
}
