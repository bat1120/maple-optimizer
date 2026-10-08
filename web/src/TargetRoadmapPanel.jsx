import { useState } from "react";
import { getTargetRoadmap } from "./api.js";
import { hasExtension, sendToExtension } from "./extension.js";
import { HowTo, PanelHead } from "./ui/Guide.jsx";

// 목표 보스 배율 로드맵(2026-10-09): MapleScouter 효율·보스컷의 배율(예: 익스트림 스우 34.52%)에서 목표(50%)까지.
// [MapleScouter에서 진짜 배율 보기] — 확장이 로드맵 변화량을 MapleScouter에 넣고 [결과]로 그 보스의 실제 배율(전 → 후)을 읽는다.
// 보스 이름 ↔ MapleScouter 보스컷 이미지 이름. 확인한 것만(2026-10-09 툴팁: 스우=extreme_lotus, 최초의 대적자=extreme_adversary)
export const BOSSES = [
  ["extreme_lotus", "익스트림 스우"], ["extreme_adversary", "익스트림 최초의 대적자"], ["extreme_kaling", "익스트림 카링"],
  ["extreme_kalos", "익스트림 칼로스"], ["extreme_seren", "익스트림 세렌"], ["extreme_blackMage", "익스트림 검은 마법사"],
  ["destiny_seren", "데스티니 세렌"], ["champion_kalos", "챔피언 칼로스"], ["champion_seren", "챔피언 세렌"],
  ["champion_blackMage", "챔피언 검은 마법사"],
];

function stepLabel(s) {
  if (s.path === "스타포스") return `${s.name} ${s.from_star}→${s.to_star}성`;
  if (s.path === "큐브") return `${s.slot} ${s.kind} ${s.grade} ${s.lines_good}줄`;
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
  const [sent, setSent] = useState(null);
  const label = BOSSES.find(([k]) => k === boss)?.[1];

  const load = async () => {
    setBusy(true); setError(null); setSent(null);
    try {
      setData(await getTargetRoadmap(name, defense, { current: Number(current), target: Number(target), fragmentMan: fragMan }));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  // 장비 쪽(큐브·스타포스·HEXA 스탯)만 MapleScouter에 들어간다 — 우리 추정도 그 몫만
  const expected = data ? data.final_ratio / (data.hexa_core_multiplier || 1) : null;
  const check = async () => setSent(await sendToExtension({ ...data.scouter, check: { boss, label, expected } }));

  return (
    <section className="panel">
      <PanelHead title="목표 배율 로드맵" icon="trend"
                 subtitle="보스 배율을 목표까지 올리려면 무엇을 어떤 순서로 하면 되는지, 억당 효율 순으로 쌓아 보여 줘요." />
      <HowTo steps={[
        <>MapleScouter <strong>효율·보스컷</strong>에서 그 보스의 지금 배율(예: 34.52%)을 보고 아래에 넣어요.</>,
        <>목표 배율(기본 50%)과, HEXA까지 보려면 조각 1개 값을 넣고 <strong>로드맵 만들기</strong>.</>,
        <>크롬 확장이 있으면 <strong>MapleScouter에서 진짜 배율 보기</strong> — 장비 변화를 MapleScouter에 넣고 실제 배율(전 → 후)을 읽어 줘요.</>,
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
          {data.scouter && hasExtension() && (
            <p>
              <button type="button" onClick={check}>MapleScouter에서 진짜 배율 보기</button>{" "}
              <span className="muted small">장비 변화(큐브·스타포스·HEXA 스탯)만 들어가요 — 우리 추정 {expected?.toFixed(2)}%</span>
            </p>
          )}
          {data.scouter && !hasExtension() && (
            <p className="muted small">크롬 확장을 설치하면 이 로드맵을 MapleScouter에 넣고 실제 배율을 바로 볼 수 있어요(환산 도우미 페이지).</p>
          )}
          {sent?.ok && <p className="muted small">MapleScouter 탭을 열었어요 — 지금 배율을 읽고, 변화량을 넣고, 다시 읽어요(30초~1분). 결과는 그 탭 위쪽 알림에 떠요.</p>}
          {sent && !sent.ok && <p className="error small">{sent.error}</p>}
          <details className="note"><summary>계산 기준 보기</summary><p className="muted small">{data.note}</p></details>
        </>
      )}
    </section>
  );
}
