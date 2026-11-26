// 목표 세팅 컨설팅(2026-11-26 사용자: 메이플 템 세팅은 한 단계씩이 아니라, 메소를 모아 오래 쓸 템들로 한 번에 갈아타는 것).
// 서버가 성(17·18·21·22)마다 방어구·장신구 세팅을 통째로 계산해 준다(세트 효과가 같이 바뀌는 것까지). 화면은 그 결과를 그대로 보여 주고,
// 살 템의 시세만 사용자가 넣는다(넥슨이 주지 않는다) — 넣은 만큼 합계와 1억 메소당 효율을 계산한다(합·나눗셈뿐이라 화면에서 한다).
import { useEffect, useRef, useState } from "react";
import { getConsult } from "./api.js";
import { formatMeso, formatPct, parsePrice } from "./format.js";
import { EmptyState, PanelHead, RowsSkeleton } from "./ui/Guide.jsx";

// 세팅 전체의 실딜은 수십 %라 소수 한 자리면 충분하다(1억 메소당 효율은 작은 수라 formatPct 그대로)
const pct1 = (x) => `${x >= 0 ? "+" : ""}${x.toFixed(1)}%`;
const SHORT = (s) => (s || "").replace("의 보스 세트", "").replace(" 세트", "");

export default function ConsultPanel({ name, defense }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [star, setStar] = useState(22);
  const [prices, setPrices] = useState({}); // 템 이름 → 사용자가 적은 가격 글자
  // 처음엔 결론(성별 실딜)만 보이고 살 템·강화 목록은 눌러서 편다 — 바로 아래 '내 업그레이드 계획' 첫 줄이 첫 화면에서 밀려나지 않게
  const [open, setOpen] = useState(false);
  const [have, setHave] = useState(""); // 가진 메소(글자)
  const seq = useRef(0);

  useEffect(() => {
    if (!name) return;
    const mine = ++seq.current;
    setData(null); setError(null);
    getConsult(name, defense)
      .then((d) => { if (mine === seq.current) setData(d); })
      .catch((e) => { if (mine === seq.current) setError(e); });
  }, [name, defense]);

  const builds = data?.builds || [];
  const build = builds.find((b) => b.starforce === star) || builds[builds.length - 1];
  const priced = (build?.buy || []).map((x) => parsePrice(prices[x.name] || ""));
  const missing = priced.filter((p) => !p).length;
  const buyTotal = priced.reduce((a, p) => a + (p || 0), 0);
  const total = buyTotal + (build?.raise_cost || 0);
  // 나눠서 한다면: 장신구만 · 방어구만 · 둘 다. 강화 비용은 서버가 준 평균, 살 템은 넣은 시세만큼만 안다
  const budget = parsePrice(have);
  const part = (group) => {
    const buy = (build?.buy || []).filter((x) => !group || x.group === group);
    const known = buy.map((x) => parsePrice(prices[x.name] || ""));
    const raise = (build?.raise || []).filter((x) => !group || x.group === group).reduce((a, x) => a + x.cost, 0);
    return { buy: buy.length, missing: known.filter((p) => !p).length, cost: raise + known.reduce((a, p) => a + (p || 0), 0), raise };
  };
  const options = build ? [
    build.accessory && { label: "장신구만", delta: build.accessory.delta_pct, ...part("장신구") },
    build.armor && { label: "방어구만", delta: build.armor.delta_pct, ...part("방어구") },
    { label: "둘 다", delta: build.delta_pct, ...part(null) },
  ].filter((o) => o && (o.buy > 0 || o.raise > 0)) : [];
  const verdict = (o) => {
    if (!budget) return o.missing ? `강화 ${formatMeso(o.raise) || "0"} + 살 템 ${o.missing}개 시세` : formatMeso(o.cost);
    if (o.cost > budget) return `${formatMeso(o.cost - budget)} 모자라요${o.missing ? `(시세를 안 넣은 템 ${o.missing}개 빼고도)` : ""}`;
    if (o.missing) return `살 템 ${o.missing}개에 ${formatMeso(budget - o.cost)}까지 쓸 수 있어요`;
    return `돼요 · ${formatMeso(budget - o.cost)} 남아요`;
  };

  return (
    <section className="panel consult-panel" aria-label="목표 세팅 컨설팅">
      <PanelHead title="목표 세팅 컨설팅" icon="trend"
                 subtitle="메소를 모아 한 번에 갈아탄다면 — 방어구·장신구를 통째로 바꾼 세팅의 보스 실딜이에요(세트 효과 포함)." />
      {error && <p role="alert" className="inline-error"><strong>{error.message}</strong></p>}
      {!data && !error && <RowsSkeleton rows={4} />}
      {data && builds.length === 0 && (
        <EmptyState icon="trend" title="계산할 세팅을 찾지 못했어요">바꿔 볼 방어구·장신구 칸이 없어요.</EmptyState>
      )}
      {build && (
        <>
          <div className="consult-stars" role="tablist" aria-label="목표 스타포스">
            {builds.map((b) => (
              <button key={b.starforce} type="button" role="tab" aria-selected={b.starforce === build.starforce}
                      className={b.starforce === build.starforce ? "pill is-on" : "pill"} onClick={() => setStar(b.starforce)}>
                {b.starforce}성 <strong className="num">{pct1(b.delta_pct)}</strong>
              </button>
            ))}
          </div>
          <p className="consult-headline">
            <span>{build.starforce}성 세팅으로 갈아타면 보스 실딜</span>
            <strong className="consult-gain num">{pct1(build.delta_pct)}</strong>
            <span className="muted small">
              {[build.armor && `방어구 ${build.armor.label} ${pct1(build.armor.delta_pct)}`,
                build.accessory && `장신구 ${build.accessory.label} ${pct1(build.accessory.delta_pct)}`].filter(Boolean).join(" · ")}
            </span>
          </p>

          <button type="button" className="ghost more-ranks" aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? "접기" : `살 템 ${build.buy.length}개 · 강화할 템 ${build.raise.length}개 보기`}
          </button>
          {open && options.length > 0 && (
            <>
              <div className="consult-budget">
                <label htmlFor="consult-have">가진 메소</label>
                <input id="consult-have" aria-label="컨설팅에 쓸 메소" inputMode="text" autoComplete="off" placeholder="예: 3000억" value={have}
                       onChange={(e) => setHave(e.target.value)} />
                <span className="muted small">넣으면 어디까지 되는지 알려 드려요</span>
              </div>
              <table className="consult-options" aria-label="나눠서 한다면">
                <thead><tr><th>나눠서 한다면</th><th className="num">보스 실딜</th><th>{budget ? `${formatMeso(budget)}으로` : "필요한 메소"}</th></tr></thead>
                <tbody>
                  {options.map((o) => (
                    <tr key={o.label} className={budget && o.cost <= budget && !o.missing ? "is-ok" : ""}>
                      <td>{o.label}</td><td className="num"><strong>{pct1(o.delta)}</strong></td><td>{verdict(o)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {open && build.buy.length > 0 && (
            <>
              <h4 className="consult-sub">살 템 {build.buy.length}개 <span className="muted small">— 시세를 넣으면 합계가 나와요(예: 30억)</span></h4>
              <ul className="consult-list" aria-label="살 템">
                {build.buy.map((x) => (
                  <li key={x.slot}>
                    <span className="consult-slot muted small">{x.slot}</span>
                    <span className="consult-name"><strong>{x.name}</strong> <span className="muted small">{x.starforce}성{x.set ? ` · ${SHORT(x.set)}` : ""}</span></span>
                    <input aria-label={`${x.name} 시세`} inputMode="text" autoComplete="off" placeholder="시세" value={prices[x.name] || ""}
                           onChange={(e) => setPrices((p) => ({ ...p, [x.name]: e.target.value }))} />
                  </li>
                ))}
              </ul>
            </>
          )}

          {open && build.raise.length > 0 && (
            <>
              <h4 className="consult-sub">지금 템을 강화 {build.raise.length}개 <span className="muted small">— 평균 {build.raise_cost_text}</span></h4>
              <ul className="consult-list" aria-label="강화할 템">
                {build.raise.map((x) => (
                  <li key={x.slot}>
                    <span className="consult-slot muted small">{x.slot}</span>
                    <span className="consult-name"><strong>{x.name}</strong> <span className="muted small">{x.from_star}→{x.starforce}성</span></span>
                    <span className="num">{x.cost_text}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {open && <p className="consult-total" aria-live="polite">
            {buyTotal > 0 || build.raise_cost > 0 ? (
              <>
                <span>필요한 메소</span> <strong className="num">{formatMeso(total)}</strong>
                {missing > 0
                  ? <span className="muted small"> + 시세를 안 넣은 템 {missing}개</span>
                  : <span className="muted small"> · 1억 메소당 <strong className="num">{formatPct(build.delta_pct / (total / 1e8))}</strong></span>}
              </>
            ) : <span className="muted small">살 템의 시세를 넣으면 필요한 메소와 1억 메소당 효율을 계산해요.</span>}
          </p>}

          {open && build.set_change.some((c) => c.lost.length || c.gained.length) && (
            <ul className="small watch-sets" aria-label="세트 효과 변화">
              {build.set_change.filter((c) => c.lost.length || c.gained.length).map((c) => (
                <li key={c.set}>
                  <strong>{c.set} {c.before}→{c.after}개</strong>
                  {c.gained.length ? <span className="pos"> · 새로 켜지는 효과: {c.gained.join(" / ")}</span> : null}
                  {c.lost.length ? <span className="neg"> · 사라지는 효과: {c.lost.join(" / ")}</span> : null}
                </li>
              ))}
            </ul>
          )}
          {open && <details className="plan-note"><summary>계산 방법 · 들어 있지 않은 비용</summary><p className="muted small">{data.note}</p></details>}
        </>
      )}
    </section>
  );
}
