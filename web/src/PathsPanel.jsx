import { useEffect, useState } from "react";
import { getPaths, postMarketRefresh } from "./api.js";
import { formatPct, settingLabel } from "./format.js";

// 업그레이드 경로 비교: 구매(관측 매물)·직작(매물+큐브)·지금 템 큐브를 억당 실딜로. 세트 효과 변화는 실딜에 들어가 있고 따로 표시한다.
// '경매장 시세 갱신'은 로컬에 연결된 maple-auction-mcp로 웹 경매장을 검색한다(일일 검색 한도 소진).
function pathLabel(p) {
  if (p.path === "구매") return `구매 · ${p.name}${p.sold ? " (체결가)" : " (호가)"}`;
  const step = `${p.kind} ${p.grade} ${p.lines_good}줄`;
  return p.path === "직작" ? `직작 · ${p.name} + 큐브 ${step}` : `큐브 ${step}`;
}

export default function PathsPanel({ name, defense, autoLoad = false, showRefresh = true }) {
  const [data, setData] = useState(null);
  const [refresh, setRefresh] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const run = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const load = () => run(async () => setData(await getPaths(name, defense)));
  const update = () => run(async () => {
    setRefresh(await postMarketRefresh({ name, boss_defense: defense, max_searches: 15 }));
    setData(await getPaths(name, defense));
  });

  useEffect(() => { if (autoLoad && name) load(); }, [autoLoad, name, defense]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="panel">
      <h3>업그레이드 경로 비교 (구매·직작·큐브)</h3>
      <button type="button" className={autoLoad ? "ghost small" : undefined} onClick={load} disabled={!name || busy}>
        {autoLoad ? (busy ? "계산 중…" : "다시 계산") : "업그레이드 경로 비교"}
      </button>{" "}
      {showRefresh && <button type="button" onClick={update} disabled={!name || busy}>경매장 시세 갱신</button>}
      {refresh && (
        <p className="muted">
          검색 {refresh.searched}회 · 매물 {refresh.recorded}건 저장 · 오늘 남은 검색 {refresh.search_remaining ?? "?"}회
          {refresh.errors?.length ? ` · 실패 ${refresh.errors.length}건` : ""}
        </p>
      )}
      {error && <p role="alert" className="error">{error.message}</p>}
      {data && (
        <>
          <p className="muted">{settingLabel(data.evaluation_setting)} 기준(보스 세팅) · 관측 매물 {data.observed_count}건 · {data.note}</p>
          <table aria-label="업그레이드 경로">
            <thead><tr><th>부위</th><th>경로</th><th>실딜</th><th>비용</th><th>억당</th><th>세트 변화</th></tr></thead>
            <tbody>
              {data.all.map((p, i) => (
                <tr key={i}>
                  <td>{p.slot}</td>
                  <td>{pathLabel(p)}{p.target ? <><br /><span className="muted">{p.target.join(" / ")}</span></> : null}</td>
                  <td>{formatPct(p.delta_pct)}</td><td>{p.cost_text}</td><td>{formatPct(p.per_100m)}</td>
                  <td className="muted">{p.set_change?.map((c) => `${c.set} ${c.before}→${c.after}`).join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
