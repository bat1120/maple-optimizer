// 목표 세팅 컨설팅(2026-11-26 사용자: 메이플 템 세팅은 한 단계씩이 아니라, 메소를 모아 오래 쓸 템들로 한 번에 갈아타는 것).
// 서버가 성(17·18·21·22)마다 방어구·장신구 세팅을 통째로 계산해 준다(세트 효과가 같이 바뀌는 것까지). 화면은 그 결과를 그대로 보여 주고,
// 살 템의 시세만 사용자가 넣는다(넥슨이 주지 않는다) — 넣은 만큼 합계와 1억 메소당 효율을 계산한다(합·나눗셈뿐이라 화면에서 한다).
import { useEffect, useRef, useState } from "react";
import { getConsult, getConsultBest } from "./api.js";
import { formatMeso, formatPct, parsePrice } from "./format.js";
import { EmptyState, PanelHead, RowsSkeleton } from "./ui/Guide.jsx";

// 세팅 전체의 실딜은 수십 %라 소수 한 자리면 충분하다(1억 메소당 효율은 작은 수라 formatPct 그대로)
const pct1 = (x) => `${x >= 0 ? "+" : ""}${x.toFixed(1)}%`;
const SHORT = (s) => (s || "").replace("의 보스 세트", "").replace(" 세트", "");

export default function ConsultPanel({ name, defense }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [star, setStar] = useState(22);
  // 잠재 목표(2026-11-26 사용자: 오래 쓸 세팅인데 잠재는 어떻게 되는가): same = 지금 그대로, legend2·legend3 = 레전드리 좋은 줄 2·3개
  const [pot, setPot] = useState("same");
  const [addi, setAddi] = useState("same"); // 에디 목표: same | epic2 | unique2 | legend2
  const [off, setOff] = useState({});       // 잠재 목표에서 뺀 칸: "성/목표/칸" → true
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

  // 휴대폰에서는 고르는 줄이 옆으로 밀리는 한 줄이다 — 고른 알약이 화면 밖에 있으면 그 줄만 옆으로 밀어 보이게 한다(페이지는 안 움직인다)
  const panel = useRef(null);
  useEffect(() => {
    for (const row of panel.current?.querySelectorAll(".consult-stars") || []) {
      const on = row.querySelector('[aria-selected="true"]');
      if (on && (on.offsetLeft < row.scrollLeft || on.offsetLeft + on.offsetWidth > row.scrollLeft + row.clientWidth)) {
        row.scrollLeft = Math.max(0, on.offsetLeft - row.offsetLeft - 40);
      }
    }
  }, [data, star, pot, addi]);
  const all = data?.builds || [];
  const pots = [...new Set(all.map((b) => b.potential || "same"))];
  const mine = pots.includes(pot) ? pot : pots[0];
  const builds = all.filter((b) => (b.potential || "same") === mine);
  const build = builds.find((b) => b.starforce === star) || builds[builds.length - 1];
  // 에디 목표(에픽·유니크·레전드리 2줄): 서버가 세팅마다 '에디까지 얹은 실딜'과 칸별 목표를 준다(additional_options)
  const optOf = (b) => (b?.additional_options || []).find((a) => a.key === addi) || null;
  const opt = optOf(build);
  const deltaOf = (b) => (optOf(b) || b).delta_pct;
  const potGoal = !!build && mine !== "same";
  const goal = potGoal || !!opt;                       // 목표를 골랐다 — 실딜에 그 잠재·에디가 들어 있으니 큐브 비용도 합계에 넣는다
  const cubes = potGoal ? build.cube || [] : [];
  const addis = opt ? opt.slots : [];
  // 목표에서 뺀 칸(체크를 푼 칸): 효율이 나쁜 칸(예: 모자 쿨감 줄을 지키며 2줄 — 800억에 1%p)을 사용자가 가려 뺀다.
  // 합계는 그 칸의 큐브 비용을 정확히 빼고, 실딜은 서버가 준 칸별 몫을 뺀다(곱으로 겹치는 부분만큼 어긋나 '약'으로 적는다)
  const offKey = (slot, kind = "잠재") => `${build?.starforce}/${kind}/${kind === "에디" ? addi : mine}/${slot}`;
  const isOff = (slot, kind) => !!off[offKey(slot, kind)];
  const toggle = (slot, kind) => (e) => setOff((o) => ({ ...o, [offKey(slot, kind)]: !e.target.checked }));
  // 살 템의 에디 목표 비용은 '지금 수준으로 맞추는 에디 비용'(match_parts.에디) 자리에 들어간다 — 더해지는 건 그 차이
  const buyOf = Object.fromEntries((build?.buy || []).map((x) => [x.slot, x]));
  const addiCost = (a) => (a.cost || 0) - (a.kept ? 0 : buyOf[a.slot]?.match_parts?.["에디"]?.cost || 0);
  const dropped = !goal ? [] : [
    // 실딜에서 빼는 몫은 share_pct(서버가 칸별 몫의 합을 전체 상승과 같게 나눈 값 — 무기류 줄은 곱으로 겹친다). 없으면 gain_pct
    ...(potGoal ? build.buy.filter((x) => x.goal && isOff(x.slot)).map((x) => ({ group: x.group, kept: false, ...x.goal, gain_pct: x.goal.share_pct ?? x.goal.gain_pct })) : []),
    ...cubes.filter((x) => isOff(x.slot)).map((x) => ({ ...x, kept: true, gain_pct: x.share_pct ?? x.gain_pct })),
    ...addis.filter((a) => isOff(a.slot, "에디")).map((a) => ({ group: a.group, kept: a.kept, gain_pct: a.share_pct ?? a.gain_pct, cost: addiCost(a) })),
  ];
  const drop = (group, key, kept) => dropped.filter((x) => (!group || x.group === group) && (kept == null || x.kept === kept))
    .reduce((a, x) => a + (x[key] || 0), 0);
  const sum = (xs, f) => xs.reduce((a, x) => a + (f(x) || 0), 0);
  const inGroup = (group) => (x) => !group || x.group === group;
  // 큐브 비용: 살 템(잠재·에디) + 지금 템(잠재·에디) − 뺀 칸
  const buyCubeOf = (group) => (goal ? sum((build.buy || []).filter(inGroup(group)), (x) => x.match_cost)
    + sum(addis.filter((a) => !a.kept).filter(inGroup(group)), addiCost) - drop(group, "cost", false) : 0);
  const keptCubeOf = (group) => (goal ? sum(cubes.filter(inGroup(group)), (x) => x.cost)
    + sum(addis.filter((a) => a.kept).filter(inGroup(group)), addiCost) - drop(group, "cost", true) : 0);
  const buyCube = buyCubeOf(null), keptCube = keptCubeOf(null);
  const cubeAll = buyCube + keptCube;
  const shown = (delta, group) => (dropped.length ? `약 ${pct1(delta - drop(group, "gain_pct"))}` : pct1(delta));
  const eff = (g) => (g ? `${pct1(g.gain_pct)}${g.per_100m ? ` · 100억당 +${(g.per_100m * 100).toFixed(2)}%` : ""}` : "");
  const whole = build ? (opt || build).delta_pct : 0;
  const armorPct = build?.armor ? (opt ? opt.armor_delta_pct : build.armor.delta_pct) : 0;
  const accPct = build?.accessory ? (opt ? opt.accessory_delta_pct : build.accessory.delta_pct) : 0;
  const goalText = [potGoal && `잠재를 ${build.potential_label}로`, opt && `에디를 ${opt.label}로`].filter(Boolean).join(" · ");
  const unknown = build ? build.match_unknown + (potGoal ? build.cube_unknown || 0 : 0) + (opt ? opt.unknown || 0 : 0) : 0;
  const priced = (build?.buy || []).map((x) => parsePrice(prices[x.name] || ""));
  const missing = priced.filter((p) => !p).length;
  const buyTotal = priced.reduce((a, p) => a + (p || 0), 0);
  const total = buyTotal + (build?.raise_cost || 0) + cubeAll;
  // 나눠서 한다면: 장신구만 · 방어구만 · 둘 다. 강화 비용은 서버가 준 평균, 살 템은 넣은 시세만큼만 안다
  const budget = parsePrice(have);
  const part = (group) => {
    const buy = (build?.buy || []).filter((x) => !group || x.group === group);
    const known = buy.map((x) => parsePrice(prices[x.name] || ""));
    const raise = (build?.raise || []).filter((x) => !group || x.group === group).reduce((a, x) => a + x.cost, 0)
      + buyCubeOf(group) + keptCubeOf(group);
    return { buy: buy.length, missing: known.filter((p) => !p).length, cost: raise + known.reduce((a, p) => a + (p || 0), 0), raise };
  };
  const options = build ? [
    build.accessory && { label: "장신구만", text: shown(accPct, "장신구"), ...part("장신구") },
    build.armor && { label: "방어구만", text: shown(armorPct, "방어구"), ...part("방어구") },
    // 무기·보조무기·엠블렘의 잠재·에디는 방어구·장신구 어느 쪽도 아니라 '둘 다'에만 들어간다 — 그렇게 이름에 적는다
    { label: [...cubes, ...addis].some((x) => x.group === "무기") ? "둘 다 + 무기류" : "둘 다", text: shown(whole, null), ...part(null) },
  ].filter((o) => o && (o.buy > 0 || o.raise > 0)) : [];
  // 가진 메소로 어디까지(2026-11-26): 강화·살 템(넣은 시세)은 먼저 들어가고, 남는 메소로 목표 칸(잠재·에디)을 100억당 효율 높은 순으로 채운다.
  // 쓰는 값은 서버가 준 칸별 몫·큐브 평균뿐이다(새 숫자를 만들지 않는다). 칸 체크와 같은 근사라 실딜은 '약'
  const units = !goal ? [] : [
    ...(potGoal ? build.buy.filter((x) => x.goal).map((x) => ({ slot: x.slot, kind: "잠재", name: x.name, cost: x.goal.cost, gain: x.goal.gain_pct, share: x.goal.share_pct ?? x.goal.gain_pct })) : []),
    ...cubes.map((x) => ({ slot: x.slot, kind: "잠재", name: x.name, cost: x.cost, gain: x.gain_pct, share: x.share_pct ?? x.gain_pct })),
    ...addis.map((x) => ({ slot: x.slot, kind: "에디", name: x.name, cost: addiCost(x), gain: x.gain_pct, share: x.share_pct ?? x.gain_pct })),
  ].filter((u) => u.cost > 0 && u.gain > 0);
  const fit = (() => {
    if (!budget || !units.length) return null;
    const on = (u) => !isOff(u.slot, u.kind);
    const base = total - sum(units.filter(on), (u) => u.cost);          // 목표 칸을 다 뺀 합계(강화 + 넣은 시세 + 그 밖의 큐브)
    if (base > budget) return { short: base - budget, base };
    let left = budget - base;
    const keep = [];
    for (const u of [...units].sort((a, b) => b.gain / b.cost - a.gain / a.cost)) {
      if (u.cost <= left) { keep.push(u); left -= u.cost; }
    }
    const gain = whole - sum(units.filter((u) => !keep.includes(u)), (u) => u.share);
    return { keep, spent: sum(keep, (u) => u.cost), gain, left };
  })();
  const applyFit = () => setOff((o) => {
    const next = { ...o };
    for (const u of units) next[offKey(u.slot, u.kind)] = !fit.keep.includes(u);
    return next;
  });
  // 추천 조합(섞은 목표 + 성까지 같이): 가진 메소 전체를 서버에 보내면, 성마다 강화 평균과 넣은 시세를 빼고 남는 메소로
  // 칸마다 잠재·에디 목표를 따로 고른 조합을 정확히 재서 가장 많이 오르는 성을 돌려준다
  const [best, setBest] = useState(null);
  const bestSeq = useRef(0);
  useEffect(() => {
    if (!build || !budget) { setBest(null); return undefined; }
    const mine = ++bestSeq.current;
    const t = setTimeout(() => {
      getConsultBest(name, defense, budget, buyTotal)
        .then((d) => { if (mine === bestSeq.current) setBest(d); })
        .catch(() => { if (mine === bestSeq.current) setBest(null); });
    }, 400);                                                   // 메소를 치는 동안 매 글자마다 부르지 않는다
    return () => clearTimeout(t);
  }, [name, defense, !!build, budget, buyTotal]); // eslint-disable-line react-hooks/exhaustive-deps
  const mixed = best?.mix || null;
  const bestRow = best?.stars?.find((x) => x.starforce === best.best);
  const cheapest = best?.stars?.reduce((a, x) => (!a || x.short < a.short ? x : a), null);
  const [mixOpen, setMixOpen] = useState(false);
  const [starsOpen, setStarsOpen] = useState(false);
  const verdict = (o) => {
    if (!budget) return o.missing ? `${goal ? "강화·큐브" : "강화"} ${formatMeso(o.raise) || "0"} + 살 템 ${o.missing}개 시세` : formatMeso(o.cost);
    if (o.cost > budget) return `${formatMeso(o.cost - budget)} 모자라요${o.missing ? `(시세를 안 넣은 템 ${o.missing}개 빼고도)` : ""}`;
    if (o.missing) return `살 템 ${o.missing}개에 ${formatMeso(budget - o.cost)}까지 쓸 수 있어요`;
    return `돼요 · ${formatMeso(budget - o.cost)} 남아요`;
  };

  return (
    <section className="panel consult-panel" aria-label="목표 세팅 컨설팅" ref={panel}>
      <PanelHead title="목표 세팅 컨설팅" icon="trend"
                 subtitle="메소를 모아 한 번에 갈아탄다면 — 방어구·장신구를 통째로 바꾼 세팅의 보스 실딜이에요(세트 효과 포함)." />
      {error && <p role="alert" className="inline-error"><strong>{error.message}</strong></p>}
      {!data && !error && <RowsSkeleton rows={4} />}
      {data && builds.length === 0 && (
        <EmptyState icon="trend" title="계산할 세팅을 찾지 못했어요">바꿔 볼 방어구·장신구 칸이 없어요.</EmptyState>
      )}
      {build && (
        <>
          {/* 결론이 먼저(2026-11-26: 에디 줄이 늘어 휴대폰에서 결론이 첫 화면 밖으로 밀렸다 — 고르는 줄은 그 아래) */}
          <p className="consult-headline">
            <span>{build.starforce}성{potGoal ? ` · 잠재 ${build.potential_label}` : ""}{opt ? ` · 에디 ${opt.label}` : ""} 세팅으로 갈아타면 보스 실딜</span>
            <strong className="consult-gain num">{shown(whole, null)}</strong>
            <span className="muted small">
              {[build.armor && `방어구 ${build.armor.label} ${pct1(armorPct)}`,
                build.accessory && `장신구 ${build.accessory.label} ${pct1(accPct)}`].filter(Boolean).join(" · ")}
            </span>
          </p>
          <div className="consult-stars" role="tablist" aria-label="목표 스타포스">
            {builds.map((b) => (
              <button key={b.starforce} type="button" role="tab" aria-selected={b.starforce === build.starforce}
                      className={b.starforce === build.starforce ? "pill is-on" : "pill"} onClick={() => setStar(b.starforce)}>
                {b.starforce}성 <strong className="num">{pct1(deltaOf(b))}</strong>
              </button>
            ))}
          </div>
          {pots.length > 1 && (
            <div className="consult-stars consult-pots" role="tablist" aria-label="잠재 목표">
              <span className="muted small">잠재</span>
              {pots.map((k) => {
                const b = all.find((x) => (x.potential || "same") === k && x.starforce === build.starforce);
                return (
                  <button key={k} type="button" role="tab" aria-selected={k === mine} className={k === mine ? "pill is-on" : "pill"}
                          onClick={() => setPot(k)}>
                    {b?.potential_label || k}{b ? <> <strong className="num">{pct1(deltaOf(b))}</strong></> : null}
                  </button>
                );
              })}
            </div>
          )}
          {(build.additional_options || []).length > 0 && (
            <div className="consult-stars consult-pots" role="tablist" aria-label="에디 목표">
              <span className="muted small">에디</span>
              <button type="button" role="tab" aria-selected={!opt} className={!opt ? "pill is-on" : "pill"} onClick={() => setAddi("same")}>
                지금 그대로 <strong className="num">{pct1(build.delta_pct)}</strong>
              </button>
              {build.additional_options.map((a) => (
                <button key={a.key} type="button" role="tab" aria-selected={opt?.key === a.key} className={opt?.key === a.key ? "pill is-on" : "pill"}
                        onClick={() => setAddi(a.key)}>
                  {a.label} <strong className="num">{pct1(a.delta_pct)}</strong>
                </button>
              ))}
            </div>
          )}

          <button type="button" className="ghost more-ranks" aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? "접기" : `살 템 ${build.buy.length}개 · 강화할 템 ${build.raise.length}개${cubes.length ? ` · 잠재 올릴 템 ${cubes.length}개` : ""}${addis.length ? ` · 에디 올릴 템 ${addis.length}개` : ""} 보기`}
          </button>
          {open && options.length > 0 && (
            <>
              <div className="consult-budget">
                <label htmlFor="consult-have">가진 메소</label>
                <input id="consult-have" aria-label="컨설팅에 쓸 메소" inputMode="text" autoComplete="off" placeholder="예: 3000억" value={have}
                       onChange={(e) => setHave(e.target.value)} />
                <span className="muted small">넣으면 어디까지 되는지 알려 드려요</span>
              </div>
              {best && !mixed && cheapest && (
                <p className="consult-fit"><strong>강화{buyTotal ? "·살 템" : ""}만으로 {cheapest.short_text} 모자라요</strong>
                  <span className="muted small"> — 가장 싼 {cheapest.starforce}성 강화(평균 {cheapest.raise_cost_text})도 아직 어려워요.</span></p>
              )}
              {mixed && bestRow && (
                <div className="consult-fit consult-mix" aria-label="추천 조합">
                  <p>
                    <span className="muted small">추천 조합 · </span>
                    {formatMeso(budget)}이면 <strong>{best.best}성</strong>이 가장 많이 올라요 — {bestRow.raise_cost ? `강화 ${bestRow.raise_cost_text}` : "강화 없이"}{buyTotal ? ` + 살 템 ${formatMeso(buyTotal)}` : ""} + 큐브 <strong>{mixed.cost_text || "0"}</strong>,
                    보스 실딜 <strong className="num consult-mix-gain">{pct1(mixed.delta_pct)}</strong>
                    {best.best !== build.starforce && <> <button type="button" className="ghost small" onClick={() => setStar(best.best)}>{best.best}성 세팅 보기</button></>}
                  </p>
                  <p className="consult-mix-buttons">
                    <button type="button" className="ghost small" aria-expanded={starsOpen} onClick={() => setStarsOpen(!starsOpen)}>
                      {starsOpen ? "성별 비교 접기" : "성별 비교"}</button>
                    {mixed.picks.length > 0 && <button type="button" className="ghost small" aria-expanded={mixOpen} onClick={() => setMixOpen(!mixOpen)}>
                      {mixOpen ? "접기" : `칸별 목표 ${mixed.picks.length}개 보기`}</button>}
                  </p>
                  {starsOpen && (
                    <table className="consult-options" aria-label="성별 비교">
                      <thead><tr><th>성</th><th className="num">강화 평균 · 큐브</th><th className="num">보스 실딜</th></tr></thead>
                      <tbody>
                        {best.stars.map((x) => (
                          <tr key={x.starforce} className={x.starforce === best.best ? "is-ok" : ""}>
                            <td>{x.starforce}성</td>
                            <td className="num">{x.raise_cost ? x.raise_cost_text : "강화 없음"}<span className="muted small">{x.delta_pct == null ? "—" : `+ 큐브 ${x.cost_text}`}</span></td>
                            <td className="num">{x.delta_pct == null ? <span className="muted">{x.short_text} 모자라요</span> : <strong>{pct1(x.delta_pct)}</strong>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  <p className="muted small">성마다 강화 평균{buyTotal ? "과 넣은 시세(성마다 같게)" : ""}를 먼저 빼고, 남는 메소로 칸마다 잠재·에디 목표를 따로 골라 가장 많이 오르는 조합이에요(위 탭과 따로).
                    실딜은 고른 줄을 실제로 낀 세팅으로 잰 값이에요.{missing > 0 ? ` 시세를 안 넣은 살 템 ${missing}개는 계산에 없어요.` : ""}</p>
                  {mixOpen && (
                    <table className="consult-options" aria-label="추천 조합 칸별 목표">
                      <thead><tr><th>칸</th><th>목표</th><th className="num">몫 · 큐브 평균</th></tr></thead>
                      <tbody>
                        {mixed.picks.map((x) => (
                          <tr key={`${x.slot}/${x.kind}`}>
                            <td>{x.slot} <span className="muted small">{x.name}</span></td>
                            <td>{x.kind} {x.label} <span className="muted small">{x.target.join(" · ")}</span></td>
                            <td className="num"><strong>{pct1(x.gain_pct)}</strong><span className="muted small">{x.cost_text}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
              {fit && (
                <div className="consult-fit" aria-label="가진 메소로 고른 칸">
                  {fit.short ? (
                    <p><strong>강화{buyTotal ? "·살 템" : ""}만으로 {formatMeso(fit.short)} 모자라요</strong> <span className="muted small">— 목표 칸을 넣을 메소가 남지 않아요.</span></p>
                  ) : (
                    <>
                      <p>
                        <span className="muted small">고른 목표 안에서 · </span>{formatMeso(budget)}이면 목표 칸 <strong>{fit.keep.length}/{units.length}개</strong>까지(큐브 평균 {formatMeso(fit.spent) || "0"}) —
                        보스 실딜 <strong className="num">{fit.keep.length < units.length ? `약 ${pct1(fit.gain)}` : pct1(whole)}</strong>
                        {fit.keep.length < units.length && (units.every((u) => isOff(u.slot, u.kind) === !fit.keep.includes(u))
                          ? <span className="muted small"> · 아래 체크가 이대로예요</span>
                          : <> <button type="button" className="ghost small" onClick={applyFit}>이대로 체크하기</button></>)}
                      </p>
                      <p className="muted small">강화{buyTotal ? "와 넣은 시세" : ""}를 먼저 빼고, 남는 메소로 100억당 효율 높은 칸부터 넣었어요.
                        {missing > 0 ? ` 시세를 안 넣은 살 템 ${missing}개는 계산에 없어요.` : ""}{fit.keep.length < units.length ? " 실딜은 칸별 몫으로 계산해 '약'이에요." : ""}</p>
                    </>
                  )}
                </div>
              )}
              <table className="consult-options" aria-label="나눠서 한다면">
                <thead><tr><th>나눠서 한다면</th><th className="num">보스 실딜</th><th>{budget ? `${formatMeso(budget)}으로` : "필요한 메소"}</th></tr></thead>
                <tbody>
                  {options.map((o) => (
                    <tr key={o.label} className={budget && o.cost <= budget && !o.missing ? "is-ok" : ""}>
                      <td>{o.label}</td><td className="num"><strong>{o.text}</strong></td><td>{verdict(o)}</td>
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
                    <span className="consult-name"><strong>{x.name}</strong> <span className="muted small">{x.starforce}성{x.set ? ` · ${SHORT(x.set)}` : ""}</span>
                      {/* 잠재·에디를 지금 그 자리 템 수준으로 큐브로 처음부터 맞추는 평균(위쪽 한계) — 잠재 붙은 매물을 사면 덜 든다 */}
                      <span className="consult-match muted small">
                        {x.goal ? (
                          <label className="consult-pick">
                            <input type="checkbox" aria-label={`${x.name} 잠재 목표 넣기`} checked={!isOff(x.slot)} onChange={toggle(x.slot)} />
                            <span className={isOff(x.slot) ? "is-off" : ""}>잠재를 목표로 <strong className="num">{eff(x.goal)}</strong>{x.goal.cost_text ? ` · 큐브 평균 ${x.goal.cost_text}` : ""}</span>
                          </label>
                        ) : null}
                        {x.target ? `목표 잠재 ${x.target.join(" · ")}` : ""}
                        {addis.some((a) => a.slot === x.slot && !isOff(a.slot, "에디"))
                          ? (x.target ? "" : x.match_parts?.["잠재"]?.cost ? `잠재를 지금 수준으로 맞추면 평균 +${x.match_parts["잠재"].text}` : "")
                          : `${x.target ? " — " : ""}${x.match_cost == null ? "잠재 맞추는 비용은 계산하지 못했어요" : x.match_cost === 0 ? "맞출 잠재 없음"
                            : x.target ? `에디(지금 수준)까지 합치면 평균 ${x.match_text}` : `잠재·에디까지 맞추면 평균 +${x.match_text}`}`}
                      </span>
                    </span>
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

          {open && cubes.length > 0 && (
            <>
              <h4 className="consult-sub">지금 템 잠재 올리기 {cubes.length}개 <span className="muted small">— 큐브 평균 {build.cube_cost_text || "계산 못 함"}</span></h4>
              <ul className="consult-list" aria-label="잠재 올릴 템">
                {cubes.map((x) => (
                  <li key={x.slot}>
                    <span className="consult-slot muted small">{x.slot}</span>
                    <span className="consult-name"><strong>{x.name}</strong> <span className="muted small">{x.from_grade === "레전드리" ? "레전드리 · 줄만 바꿈" : `${x.from_grade} → 레전드리`}</span>
                      <span className="consult-match muted small">
                        <label className="consult-pick">
                          <input type="checkbox" aria-label={`${x.name} 잠재 목표 넣기`} checked={!isOff(x.slot)} onChange={toggle(x.slot)} />
                          <span className={isOff(x.slot) ? "is-off" : ""}>보스 실딜 <strong className="num">{eff(x)}</strong></span>
                        </label>
                        목표 잠재 {x.target.join(" · ")}
                      </span>
                    </span>
                    <span className="num">{x.cost_text || "계산 못 함"}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {open && addis.length > 0 && (
            <>
              <h4 className="consult-sub">에디 올리기 {addis.length}개 <span className="muted small">— {opt.label}, 큐브 평균 {opt.cost_text || "계산 못 함"}</span></h4>
              <ul className="consult-list" aria-label="에디 올릴 템">
                {addis.map((x) => (
                  <li key={x.slot}>
                    <span className="consult-slot muted small">{x.slot}</span>
                    <span className="consult-name"><strong>{x.name}</strong> <span className="muted small">
                      {!x.kept ? "살 템 · 레어에서" : x.from_grade === opt.label.split(" ")[0] ? `${x.from_grade} · 줄만 바꿈` : `${x.from_grade} → ${opt.label.split(" ")[0]}`}</span>
                      <span className="consult-match muted small">
                        <label className="consult-pick">
                          <input type="checkbox" aria-label={`${x.name} 에디 목표 넣기`} checked={!isOff(x.slot, "에디")} onChange={toggle(x.slot, "에디")} />
                          <span className={isOff(x.slot, "에디") ? "is-off" : ""}>보스 실딜 <strong className="num">{eff(x)}</strong></span>
                        </label>
                        목표 에디 {x.target.join(" · ")}
                      </span>
                    </span>
                    <span className="num">{x.cost_text || "계산 못 함"}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {open && <p className="consult-total" aria-live="polite">
            {total > 0 ? (
              <>
                <span>필요한 메소</span> <strong className="num">{formatMeso(total)}</strong>
                {missing > 0
                  ? <span className="muted small"> + 시세를 안 넣은 템 {missing}개</span>
                  : <span className="muted small"> · 1억 메소당 <strong className="num">{formatPct((whole - drop(null, "gain_pct")) / (total / 1e8))}</strong></span>}
              </>
            ) : <span className="muted small">살 템의 시세를 넣으면 필요한 메소와 1억 메소당 효율을 계산해요.</span>}
            {goal && cubeAll > 0 && (
              <span className="consult-match-total muted small">
                위 합계에는 {goalText} 맞추는 큐브 평균 <strong className="num">{formatMeso(cubeAll)}</strong>이 들어 있어요
                (살 템 {formatMeso(buyCube) || "0"} · 지금 템 {formatMeso(keptCube) || "0"}) — 잠재가 붙은 매물을 사면 그보다 덜 들어요.{" "}
                {opt ? (potGoal ? "추옵은" : "잠재는 지금 수준(살 템은 큐브로 맞추는 평균 포함), 추옵은") : "에디·추옵은"} 지금 그대로로 봤어요.
                {dropped.length > 0 ? ` ${opt ? "목표" : "잠재 목표"}에서 뺀 칸 ${dropped.length}개는 지금 ${opt ? "것" : "잠재"} 그대로예요 — 실딜은 칸별 몫을 뺀 값이라 '약'이에요.` : " 효율이 낮은 칸은 체크를 풀어 뺄 수 있어요."}
                {unknown > 0 ? ` 계산하지 못한 템 ${unknown}개는 빠져 있어요.` : ""}
              </span>
            )}
            {!goal && build.match_cost > 0 && (
              <span className="consult-match-total muted small">
                위는 잠재 없는 템만 살 때예요. 잠재·에디까지 지금 수준으로 큐브로 맞추면 평균 <strong className="num">{build.match_cost_text}</strong>이 더 들어요
                (합계 {formatMeso(total + build.match_cost)}{missing > 0 ? " + 안 넣은 시세" : ""}) — 잠재가 붙은 매물을 사면 그보다 덜 드니 위쪽 한계로 보세요.
                {build.match_unknown > 0 ? ` 계산하지 못한 템 ${build.match_unknown}개는 빠져 있어요.` : ""}
              </span>
            )}
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
