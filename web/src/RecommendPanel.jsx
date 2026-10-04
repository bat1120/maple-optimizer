import { useState } from "react";
import { getRecommend } from "./api.js";
import { formatPct, settingLabel } from "./format.js";

// 게임 경매장 검색 조건 추천. 부위마다 윗잠을 목표 잠재로 바꿨을 때의 보스 실딜 상승을 엔진이 계산한다.
// 사용자는 카드의 조건으로 게임에서 검색하고, 그 화면을 '경매장 화면 분석'에 연결해 실제 매물을 평가한다.
export default function RecommendPanel({ name, defense }) {
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

  return (
    <section className="panel">
      <h3>경매장 검색 추천</h3>
      <label>쿨감 1초 = 주스탯 %
        <input inputMode="decimal" value={cooldown} placeholder="비우면 쿨감 미반영" onChange={(e) => setCooldown(e.target.value)} />
      </label>
      <button type="button" onClick={load} disabled={!name || busy}>검색 추천 받기</button>
      {error && <p role="alert" className="error">{error.message}</p>}
      {data && (
        <>
          <p className="muted">{settingLabel(data.evaluation_setting)} 기준(보스 세팅) · {data.note}</p>
          {data.recommendations.length === 0 ? (
            <p>잠재만 바꿔서 오르는 부위가 없어요.</p>
          ) : (
            <ol className="plain">
              {data.recommendations.map((r) => (
                <li key={r.slot}>
                  <strong>{r.slot}</strong> · 실딜 {formatPct(r.delta_pct)}
                  <span className="muted"> · {r.kind} {r.grade} {r.lines_good}줄</span>
                  <br />
                  검색: {r.category} · {r.kind} {r.target_potentials.join(" / ")} · {r.min_starforce}성 이상
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
          <p className="muted">게임 경매장에서 이 조건으로 검색한 뒤, 아래 '경매장 화면 분석'에 게임 창을 연결하면 실제 매물을 평가해요.</p>
        </>
      )}
    </section>
  );
}
