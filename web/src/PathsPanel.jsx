import { useEffect, useState } from "react";
import { getPaths, postMarketRefresh } from "./api.js";
import { formatPct, settingLabel } from "./format.js";
import { EmptyState, HowTo, PanelHead, RowsSkeleton } from "./ui/Guide.jsx";

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
      <PanelHead title="업그레이드 경로 비교" icon="layers"
                 subtitle="같은 부위를 구매(관측 매물)·직작(매물+큐브)·지금 템 큐브 중 어떤 방법으로 올리는 게 억당 실딜이 높은지 비교해요.">
        <button type="button" className={autoLoad ? "ghost small" : undefined} onClick={load} disabled={!name || busy}>
          {autoLoad ? (busy ? "계산 중…" : "다시 계산") : "업그레이드 경로 비교"}
        </button>
        {showRefresh && <button type="button" onClick={update} disabled={!name || busy}>경매장 시세 갱신</button>}
      </PanelHead>
      <HowTo steps={[
        <><strong>억당</strong> 열이 높을수록 같은 메소로 실딜이 많이 올라요.</>,
        <>구매 경로는 경매장 화면 평가로 쌓인 <strong>관측 매물</strong>로만 계산해요. 관측이 없으면 큐브 경로만 나와요.</>,
        <>세트 효과가 바뀌는 경우 실딜에 이미 들어가 있고, <strong>세트 변화</strong> 열에 따로 적어요.</>,
      ]} />
      {busy && !data && <RowsSkeleton rows={4} />}
      {refresh && (
        <p className="muted">
          검색 {refresh.searched}회 · 매물 {refresh.recorded}건 저장 · 오늘 남은 검색 {refresh.search_remaining ?? "?"}회
          {refresh.errors?.length ? ` · 실패 ${refresh.errors.length}건` : ""}
        </p>
      )}
      {error && <p role="alert" className="error">{error.message}</p>}
      {data && (
        <>
          <p className="muted small">{settingLabel(data.evaluation_setting)} 기준(보스 세팅) · 관측 매물 {data.observed_count}건</p>
          {data.note && <details className="note"><summary>계산 기준 보기</summary><p className="muted small">{data.note}</p></details>}
          {data.all.length === 0 && (
            <EmptyState icon="layers" title="비교할 경로가 아직 없어요">관측 매물이 쌓이거나 큐브로 오를 단계가 있으면 여기에 나와요.</EmptyState>
          )}
          <table aria-label="업그레이드 경로" hidden={data.all.length === 0}>
            <thead><tr><th>부위</th><th>경로</th><th className="num">실딜</th><th className="num">비용</th><th className="num">억당</th><th>세트 변화</th></tr></thead>
            <tbody>
              {data.all.map((p, i) => (
                <tr key={i}>
                  <td>{p.slot}</td>
                  <td>{pathLabel(p)}{p.target ? <><br /><span className="muted">{p.target.join(" / ")}</span></> : null}</td>
                  <td className="num">{formatPct(p.delta_pct)}</td><td className="num">{p.cost_text}</td><td className="num">{formatPct(p.per_100m)}</td>
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
