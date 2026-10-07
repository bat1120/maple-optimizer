import { useEffect, useState } from "react";
import { getRecommend } from "./api.js";
import { formatPct, settingLabel } from "./format.js";
import { EmptyState, HowTo, PanelHead, RowsSkeleton } from "./ui/Guide.jsx";

// 게임 경매장 검색 조건 추천. 부위마다 윗잠을 목표 잠재로 바꿨을 때의 보스 실딜 상승을 엔진이 계산한다.
// 사용자는 카드의 조건으로 게임에서 검색하고, 그 화면을 '경매장 화면 분석'에 연결해 실제 매물을 평가한다.
export default function RecommendPanel({ name, defense, autoLoad = false }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(""); // 쿨감 1초 = 주스탯 N% (비우면 쿨감은 실딜에 넣지 않는다)

  const load = async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await getRecommend(name, defense, 5, Number(cooldown) > 0 ? Number(cooldown) : null));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { if (autoLoad && name) load(); }, [autoLoad, name, defense]); // eslint-disable-line react-hooks/exhaustive-deps
  const copy = (text) => { try { navigator.clipboard?.writeText(text); } catch { /* 복사 못 해도 화면에 조건이 보인다 */ } };

  return (
    <section className="panel">
      <PanelHead title="경매장 검색 추천" icon="search"
                 subtitle="부위마다 어떤 잠재로 바꾸면 실딜이 오르는지 계산해, 게임 경매장에서 쓸 검색 조건으로 알려 드려요." />
      <HowTo steps={[
        <>카드의 칩(분류·등급·옵션·성)이 게임 경매장 <strong>검색 조건</strong>이에요. [복사]로 한 줄로 복사할 수 있어요.</>,
        <>쿨감이 중요한 직업이라면 <strong>쿨감 1초 = 주스탯 %</strong>를 넣고 [다시 계산]을 누르세요. 비우면 직업 자료값이 있을 때만 반영해요.</>,
        <>PC에서는 아래 <strong>경매장 화면 평가</strong>에 게임 창을 연결하면, 검색한 매물을 내 캐릭터 기준으로 평가해요.</>,
      ]} />
      <div className="inline-form">
        <label className="field">쿨감 1초 = 주스탯 %
          <input inputMode="decimal" value={cooldown} placeholder="비우면 직업 자료값(있을 때만)" onChange={(e) => setCooldown(e.target.value)} />
        </label>
        <button type="button" className={autoLoad ? "ghost" : undefined} onClick={load} disabled={!name || busy}>
          {autoLoad ? (busy ? "계산 중…" : "다시 계산") : "검색 추천 받기"}
        </button>
      </div>
      {busy && !data && <RowsSkeleton rows={3} />}
      {error && <p role="alert" className="error">{error.message}</p>}
      {data && (
        <>
          <p className="muted small">{settingLabel(data.evaluation_setting)} 기준(보스 세팅)</p>
          {data.note && <details className="note"><summary>계산 기준 보기</summary><p className="muted small">{data.note}</p></details>}
          {data.recommendations.length === 0 ? (
            <EmptyState icon="search" title="잠재만 바꿔서 오르는 부위가 없어요.">위의 업그레이드 경로 비교나 계산기 탭의 스타포스 비용을 살펴보세요.</EmptyState>
          ) : (
            <ol className="plain rec-list" aria-label="추천 검색 조건">
              {data.recommendations.map((r) => (
                <li key={r.slot} className="rec-item">
                  <strong>{r.slot}</strong> · 실딜 {formatPct(r.delta_pct)}
                  <span className="muted"> · {r.kind} {r.grade} {r.lines_good}줄</span>
                  <br />
                  <span className="chips">
                    <span className="chip">{r.category}</span><span className="chip">{r.kind} {r.grade}</span>
                    {r.target_potentials.map((t) => <span key={t} className="chip">{t}</span>)}
                    <span className="chip">{r.min_starforce}성 이상</span>
                    <button type="button" className="ghost small" onClick={() => copy(`${r.category} · ${r.kind} ${r.target_potentials.join(" / ")} · ${r.min_starforce}성 이상`)}>복사</button>
                  </span>
                  <span className="sr-only">검색: {r.category} · {r.kind} {r.target_potentials.join(" / ")} · {r.min_starforce}성 이상</span>
                  {r.kept?.length ? <><br /><span className="muted">유지: {r.kept.join(" / ")}</span></> : null}
                  <br />
                  <span className="muted">
                    지금: {r.current.name}{r.current.starforce ? ` ${r.current.starforce}성` : ""}
                    {r.current.potentials.length ? ` · ${r.current.potentials.join(" / ")}` : ""}
                  </span>
                </li>
              ))}
            </ol>
          )}
          <p className="muted small note-box">게임 경매장에서 이 조건으로 검색해 보세요. PC에서는 아래 '경매장 화면 평가'에 게임 창을 연결하면 실제 매물을 내 캐릭터 기준으로 평가해요.</p>
        </>
      )}
    </section>
  );
}
