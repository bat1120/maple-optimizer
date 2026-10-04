import { useState } from "react";
import { getRoadmap } from "./api.js";
import { formatMeso, formatPct, settingLabel } from "./format.js";

// 전체 부위 로드맵: 부위마다 잠재·에디의 '다음 단계'(실딜이 처음 0.1% 이상 오르는 등급·줄 수)와 모든 단계를 보여 준다.
const KINDS = ["잠재", "에디"];
const label = (t) => `${t.grade} ${t.lines_good}줄`;
// 관측 시세: 화면 분석으로 쌓인 매물 중 이 단계 조건을 갖춘 것
const marketText = (m) => (m ? `시세 ${formatMeso(m.median)} (${m.count}건, 최저 ${formatMeso(m.min)}) · 억당 ${formatPct(m.per_100m)}` : "시세 없음");

function Next({ row, kind }) {
  const i = row.next?.[kind];
  if (i == null) return <span className="muted">—</span>;
  const t = row[kind][i];
  return <span>{label(t)} {formatPct(t.delta_pct)}<br /><span className="muted">{t.target.join(" / ")}</span></span>;
}

export default function RoadmapPanel({ name, defense }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

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

  return (
    <section className="panel">
      <h3>전체 부위 로드맵</h3>
      <button type="button" onClick={load} disabled={!name || busy}>전체 부위 로드맵</button>
      {error && <p role="alert" className="error">{error.message}</p>}
      {data && (
        <>
          <p className="muted">{settingLabel(data.evaluation_setting)} 기준(보스 세팅) · {data.note}</p>
          {data.value_ranking?.length > 0 && (
            <>
              <h4>가격 대비 순위 (큐브 메소 재설정 기준)</h4>
              <p className="muted">{data.value_note} {data.market_note}</p>
              <table aria-label="가격 대비 순위">
                <thead><tr><th>#</th><th>부위</th><th>단계</th><th>실딜</th><th>큐브 평균 비용</th><th>억당</th><th>관측 시세</th></tr></thead>
                <tbody>
                  {data.value_ranking.map((v, i) => (
                    <tr key={`${v.slot}-${v.kind}`}>
                      <td>{i + 1}</td><td>{v.slot} {v.kind}</td>
                      <td>{label(v)}<br /><span className="muted">{v.target.join(" / ")}</span></td>
                      <td>{formatPct(v.delta_pct)}</td><td>{v.cube_cost_text}</td><td>{formatPct(v.per_100m)}</td>
                      <td className="muted">{marketText(v.market)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          <table aria-label="부위별 다음 단계">
            <thead><tr><th>부위</th><th>지금</th><th>잠재 다음 단계</th><th>에디 다음 단계</th></tr></thead>
            <tbody>
              {data.slots.map((row) => (
                <tr key={row.slot}>
                  <td>
                    <strong>{row.slot}</strong>{row.route === "큐브" ? <span className="muted"> · 큐브(경매장 구매 불가)</span> : null}
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
        </>
      )}
    </section>
  );
}
