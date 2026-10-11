import { useEffect, useState } from "react";
import { SF_EVENTS, getPaths, postMarketRefresh } from "./api.js";
import { formatPct, settingLabel } from "./format.js";
import { EmptyState, HowTo, PanelHead, RowsSkeleton } from "./ui/Guide.jsx";

// 업그레이드 경로 비교: 구매(관측 매물)·직작(매물+큐브)·지금 템 큐브를 억당 실딜로. 세트 효과 변화는 실딜에 들어가 있고 따로 표시한다.
// '경매장 시세 갱신'은 로컬에 연결된 maple-auction-mcp로 웹 경매장을 검색한다(일일 검색 한도 소진).
// 환생의 불꽃 가격 칸(줄임 이름 = 서버 flame_prices 이름). 메소 추가옵션 재설정은 공식 300만 메소라 칸이 없다
const FLAMES = [["강력", "강력한 환생의 불꽃"], ["타오르는", "타오르는 환생의 불꽃"], ["영원", "영원한 환생의 불꽃"],
                ["검은", "검은 환생의 불꽃"], ["심연", "심연의 환생의 불꽃"]];

function flameDetail(p) {
  const n = (x) => Math.round(x).toLocaleString("ko-KR");
  const main = p.target_main != null ? ` · 주스탯 환산 ${n(p.current_main)} → ${Math.ceil(p.target_main).toLocaleString("ko-KR")} 이상` : "";
  return `평균 ${n(p.expected_tries)}회 · 1회 ${(p.reach_probability * 100).toFixed(3)}%${main}`;
}

function pathLabel(p) {
  if (p.path === "구매") return `구매 · ${p.name}${p.sold ? " (체결가)" : " (호가)"}`;
  if (p.path === "스타포스") return `스타포스 · ${p.name} ${p.from_star}→${p.to_star}성`;
  if (p.path === "HEXA 코어") return `다음 1레벨 · ${p.name}`;  // 부위 칸에 'HEXA 코어'가 이미 있다
  if (p.path === "HEXA 스탯") return p.name;
  if (p.path === "추옵") return `추옵 · ${p.name} · ${p.flame}`;
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
  const [events, setEvents] = useState({ discount30: false, destroy_down30: false, guarantee_5_10_15: false, restore_discount20: false,
                                         protect: false, miracle: false, spareEok: "", fragmentMan: "", hexaSunday: false, spareBySlot: {},
                                         flameMan: {} });
  const shining = SF_EVENTS.every((k) => events[k]);
  const sfSlots = [...new Set((data?.all || []).filter((p) => p.path === "스타포스").map((p) => p.slot))];
  const toggleShining = () => setEvents((e) => ({ ...e, ...Object.fromEntries(SF_EVENTS.map((k) => [k, !shining])) }));
  const toggle = (k) => setEvents((e) => ({ ...e, [k]: !e[k] }));
  const load = () => run(async () => setData(await getPaths(name, defense, events)));
  const update = () => run(async () => {
    setRefresh(await postMarketRefresh({ name, boss_defense: defense, max_searches: 15 }));
    setData(await getPaths(name, defense, events));
  });

  useEffect(() => { if (autoLoad && name) load(); }, [autoLoad, name, defense]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="panel">
      <PanelHead title="업그레이드 경로 비교" icon="layers"
                 subtitle="구매(관측 매물)·직작(매물+큐브)·큐브·스타포스·추옵·HEXA 중 어떤 방법이 억당 실딜이 높은지 비교해요.">
        <button type="button" className={autoLoad ? "ghost small" : undefined} onClick={load} disabled={!name || busy}>
          {autoLoad ? (busy ? "계산 중…" : "다시 계산") : "업그레이드 경로 비교"}
        </button>
        {showRefresh && <button type="button" onClick={update} disabled={!name || busy}>경매장 시세 갱신</button>}
      </PanelHead>
      <HowTo steps={[
        <><strong>억당</strong> 열이 높을수록 같은 메소로 실딜이 많이 올라요.</>,
        <>구매 경로는 경매장 화면 평가로 쌓인 <strong>관측 매물</strong>로만 계산해요. 관측이 없으면 큐브 경로만 나와요.</>,
        <>세트 효과가 바뀌는 경우 실딜에 이미 들어가 있고, <strong>세트 변화</strong> 열에 따로 적어요.</>,
        <><strong>조각 1개 값</strong>을 넣으면 HEXA 스탯(초기화 기대값)·HEXA 코어(다음 1레벨) 경로도 같은 억당으로 비교해요. 코어 딜 지분은 내 연무장 기록, 없으면 직업 상위 기록 중앙값이에요.</>,
        <><strong>추옵</strong>은 지금 템 추옵을 다시 굴려 목표 이상이 나올 때까지의 평균 비용이에요. 보스 장비로 확인되는 템만, 불꽃 값을 넣은 불꽃만 비교해요.</>,
        <><strong>스타포스</strong> 비용은 강화 + 흔적 복구 메소 기대값이에요. 위에서 이벤트를 고르고, <strong>스페어 1개 값</strong>을 넣으면 파괴 시 스페어 비용까지 더해요.</>,
      ]} />
      <fieldset className="events">
        <legend className="muted small">강화 이벤트·파괴 비용</legend>
        <label className="chip"><input type="checkbox" checked={events.discount30} onChange={() => toggle("discount30")} /> 30% 할인</label>
        <label className="chip"><input type="checkbox" checked={events.destroy_down30} onChange={() => toggle("destroy_down30")} /> 21성 이하 파괴 30% 감소</label>
        <label className="chip"><input type="checkbox" checked={events.guarantee_5_10_15} onChange={() => toggle("guarantee_5_10_15")} /> 5·10·15성 100%</label>
        <label className="chip"><input type="checkbox" checked={events.restore_discount20} onChange={() => toggle("restore_discount20")} /> 복구 메소 20% 할인</label>
        <button type="button" className="ghost small" aria-pressed={shining} aria-label="샤이닝 스타포스 한 번에" onClick={toggleShining}>
          샤이닝 스타포스{shining ? " ✓" : ""}</button>
        <label className="chip"><input type="checkbox" checked={events.protect} onChange={() => toggle("protect")} /> 파괴 방지<span className="muted small">(15~17성)</span></label>
        <label className="chip"><input type="checkbox" checked={events.miracle} onChange={() => toggle("miracle")} /> 미라클 타임<span className="muted small">(큐브 등급 상승 2배)</span></label>
        <label className="inline">스페어 1개 값(억) <input aria-label="스페어 1개 값(억)" inputMode="decimal" value={events.spareEok} placeholder="비우면 미포함"
          onChange={(e) => setEvents((v) => ({ ...v, spareEok: e.target.value }))} style={{ width: "7em" }} /></label>
        <label className="inline">조각 1개 값(만 메소) <input aria-label="조각 1개 값(만 메소)" inputMode="decimal" value={events.fragmentMan}
          placeholder="넣으면 HEXA 경로" onChange={(e) => setEvents((v) => ({ ...v, fragmentMan: e.target.value }))} style={{ width: "8em" }} /></label>
        <label className="chip"><input type="checkbox" checked={events.hexaSunday} onChange={() => toggle("hexaSunday")} /> HEXA 스탯 썬데이<span className="muted small">(메인 5레벨 이상 확률 ×1.2)</span></label>
        {sfSlots.length > 0 && (
          <details className="note">
            <summary>부위별 스페어 값(억) — 비우면 위 공통 값</summary>
            <div className="inline wrap">
              {sfSlots.map((slot) => (
                <label key={slot} className="inline">{slot} <input aria-label={`${slot} 스페어 값(억)`} inputMode="decimal"
                  value={events.spareBySlot[slot] ?? ""} style={{ width: "5em" }}
                  onChange={(e) => setEvents((v) => ({ ...v, spareBySlot: { ...v.spareBySlot, [slot]: e.target.value } }))} /></label>
              ))}
            </div>
          </details>
        )}
        <details className="note">
          <summary>환생의 불꽃 1개 값(만 메소) — 메소 추가옵션 재설정(1회 300만)은 항상 비교</summary>
          <div className="inline wrap">
            {FLAMES.map(([k, label]) => (
              <label key={k} className="inline">{label} <input aria-label={`${label} 1개 값(만 메소)`} inputMode="decimal"
                value={events.flameMan[k] ?? ""} style={{ width: "6em" }}
                onChange={(e) => setEvents((v) => ({ ...v, flameMan: { ...v.flameMan, [k]: e.target.value } }))} /></label>
            ))}
          </div>
        </details>
        <button type="button" className="ghost small" onClick={load} disabled={!name || busy}>이 조건으로 계산</button>
      </fieldset>
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
          <p className="muted small">{settingLabel(data.evaluation_setting)} 기준(보스 세팅) · 관측 매물 {data.observed_count}건{data.events ? ` · ${data.events.label}` : ""}</p>
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
                  <td>{pathLabel(p)}{p.target ? <><br /><span className="muted">{p.target.join(" / ")}</span></> : null}
                    {p.path === "스타포스" ? <><br /><span className="muted">평균 파괴 {p.expected_destroys.toFixed(2)}회 · 스페어 {(p.expected_spares ?? 0).toFixed(2)}개
                      {p.spare_price ? "(비용에 포함)" : "(스페어 값 미포함 — 흔적 복구 메소만)"}</span></> : null}
                    {p.path === "HEXA 코어" ? <><br /><span className="muted">조각 {p.fragments}개 · 솔 에르다 {p.erda}개 · 딜 지분: {p.share_source}</span></> : null}
                    {p.path === "추옵" ? <><br /><span className="muted">{flameDetail(p)}</span></> : null}
                    {p.path === "HEXA 스탯" ? <><br /><span className="muted">조각 평균 {Math.round(p.fragments).toLocaleString("ko-KR")}개(초기화 메소 포함)</span></> : null}</td>
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
