import { useState } from "react";
import { getTargetRoadmap } from "./api.js";
import { clipboardText } from "./scouter.js";
import { HowTo, PanelHead } from "./ui/Guide.jsx";

// 목표 보스 배율 로드맵(2026-10-09): MapleScouter 효율·보스컷의 배율(예: 익스트림 스우 34.52%)에서 목표(50%)까지.
// 지금 배율은 사용자가 직접 보고 넣는다. MapleScouter에 자동으로 넣어 읽던 확장 연동은 뺐다(2026-10-13, 운영자 연동 불가).

function stepLabel(s) {
  if (s.path === "스타포스") return `${s.name} ${s.from_star}→${s.to_star}성`;
  if (s.path === "큐브") return `${s.slot} ${s.kind} ${s.grade} ${s.lines_good}줄`;
  if (s.path === "심볼") return `${s.name} ${s.from_level}→${s.to_level}레벨${s.remaining_symbols > 0 ? ` (심볼 ${s.remaining_symbols.toLocaleString("ko-KR")}개 더)` : ""}`;
  return s.name;
}

export default function TargetRoadmapPanel({ name, defense }) {
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
    setBusy(true); setError(null);
    try {
      setData(await getTargetRoadmap(name, defense, { current: Number(current), target: Number(target), fragmentMan: fragMan }));
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
        <label className="inline">지금 배율(%) <input aria-label="지금 배율(%)" inputMode="decimal" value={current} placeholder="34.52"
          onChange={(e) => setCurrent(e.target.value)} style={{ width: "6em" }} /></label>
        <label className="inline">목표 배율(%) <input aria-label="목표 배율(%)" inputMode="decimal" value={target}
          onChange={(e) => setTarget(e.target.value)} style={{ width: "5em" }} /></label>
        <label className="inline">조각 1개 값(만 메소) <input aria-label="로드맵 조각 값(만 메소)" inputMode="decimal" value={fragMan}
          placeholder="넣으면 HEXA 포함" onChange={(e) => setFragMan(e.target.value)} style={{ width: "8em" }} /></label>
        <button type="button" onClick={load} disabled={!name || busy || !(Number(current) > 0)}>{busy ? "계산 중…" : "로드맵 만들기"}</button>
      </div>
      {error && <p role="alert" className="error">{error.message}</p>}
      {data && (
        <>
          <p>
            필요한 딜 <strong>×{data.needed_multiplier.toFixed(3)}</strong> · 로드맵 끝 <strong>{data.final_ratio.toFixed(2)}%</strong>
            {data.reached ? " (목표 도달)" : " (이 계산으로는 목표에 못 미쳐요)"} · 누적 <strong>{data.total_cost_text}</strong>
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
          <details className="note"><summary>계산 기준 보기</summary><p className="muted small">{data.note}</p></details>
        </>
      )}
    </section>
  );
}
