import { useState } from "react";
import { postCraft, postCube, postOptimize, postStarforce } from "./api.js";
import { formatMeso, formatPct, parsePrice, settingLabel } from "./format.js";
import { PanelHead } from "./ui/Guide.jsx";

// 강화·직작·최적화 패널. 계산은 전부 서버(engine)가 하고, 여기서는 입력 검증과 표시만 한다.

function Alert({ error }) {
  return error ? <p role="alert" className="error">{error.message}</p> : null;
}

function Num({ label, value, onChange, placeholder }) {
  return (
    <label className="field">{label}
      <input value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function Dist({ d, unit = "meso" }) {
  const f = unit === "meso" ? formatMeso : (x) => `${Math.round(x)}회`;
  return (
    <p className="dist">중앙값 {f(d.median)} · p75 {f(d.p75)} · p90 {f(d.p90)}</p>
  );
}

const CONDITIONS = [
  ["discount30", "30% 할인"],
  ["destroy_down30", "파괴 확률 30% 감소"],
  ["guarantee_5_10_15", "5·10·15성 100%"],
  ["protect", "파괴 방지(15~17성)"],
];

function useAsync() {
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const run = async (fn) => {
    setError(null);
    try {
      setResult(await fn());
    } catch (e) {
      setResult(null);
      setError(e);
    }
  };
  return { error, setError, result, run };
}

export function StarforcePanel() {
  const [f, setF] = useState({ level: "200", start: "0", target: "22", destroy: "30억", basic: false });
  const [cond, setCond] = useState({});
  const { error, setError, result, run } = useAsync();
  const set = (k) => (v) => setF((x) => ({ ...x, [k]: v }));
  const submit = (e) => {
    e.preventDefault();
    const start = Number(f.start), target = Number(f.target), level = Number(f.level);
    const destroy = parsePrice(f.destroy) ?? 0;
    if (!(target > start)) return setError({ message: "목표 성은 시작 성보다 커야 합니다." });
    run(() => postStarforce({ level, start, target, destroy_cost: destroy,
                              conditions: { ...cond, restore: f.basic ? "basic" : "full" } }));
  };
  return (
    <form onSubmit={submit} className="panel">
      <PanelHead title="스타포스 비용" icon="star" subtitle="목표 성까지 드는 평균 메소와 분포를 정확히 계산해요." />
      <div className="field-grid">
        <Num label="장비 레벨" value={f.level} onChange={set("level")} />
        <Num label="시작 성" value={f.start} onChange={set("start")} />
        <Num label="목표 성" value={f.target} onChange={set("target")} />
        <Num label="파괴 시 비용" value={f.destroy} onChange={set("destroy")} placeholder="스페어 시세 + 복구 메소" />
      </div>
      <p className="field-hint muted small">메소는 200억, 30억 5000만처럼 적어도 돼요.</p>
      <div className="check-grid" role="group" aria-label="이벤트·옵션">
      {CONDITIONS.map(([k, label]) => (
        <label key={k} className="check">
          <input type="checkbox" aria-label={label} checked={!!cond[k]} onChange={(e) => setCond((c) => ({ ...c, [k]: e.target.checked }))} />{label}
        </label>
      ))}
      <label className="check">
        <input type="checkbox" aria-label="기본 복구(12성)" checked={f.basic} onChange={(e) => set("basic")(e.target.checked)} />기본 복구(12성)
      </label>
      </div>
      <button type="submit" className="block">스타포스 계산</button>
      <Alert error={error} />
      {result && (
        <div className="result">
          <p className="result-kpi"><strong>평균 {formatMeso(result.exact_mean)}</strong></p>
          <Dist d={result.distribution} />
          <p className="muted">{result.note}</p>
        </div>
      )}
    </form>
  );
}

const OPTIONS = [["BOSS", "보공"], ["IED", "방무"], ["MATK", "마력%"], ["ATK", "공격력%"], ["INT", "INT%"], ["STR", "STR%"],
                 ["DEX", "DEX%"], ["LUK", "LUK%"], ["DMG", "데미지%"], ["CR", "크리티컬 확률%"]];

export function CubePanel({ onResult }) {
  const [f, setF] = useState({ key: "BOSS", kind: "lines", value: "2" });
  const { error, setError, result, run } = useAsync();
  const set = (k) => (v) => setF((x) => ({ ...x, [k]: v }));
  const submit = async (e) => {
    e.preventDefault();
    const value = Number(f.value);
    if (!(value > 0)) return setError({ message: "목표 값을 입력해 주세요." });
    const body = { table: "레전드리/무기/200", level: 200, grade: "레전드리",
                   ...(f.kind === "lines" ? { lines_at_least: { [f.key]: value } }
                                          : { sum_at_least: [{ key: f.key, percent: true, value }] }) };
    await run(async () => {
      const r = await postCube(body);
      onResult?.({ probability: r.probability, cost: r.cost_per_reset });
      return r;
    });
  };
  return (
    <form onSubmit={submit} className="panel">
      <PanelHead title="잠재 재설정" icon="spark" subtitle="레전드리 · 무기 · 200제 공식 확률표로 목표 옵션이 나올 확률과 평균 횟수를 계산해요." />
      <div className="field-grid">
      <label className="field">옵션
        <select value={f.key} onChange={(e) => set("key")(e.target.value)}>
          {OPTIONS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </label>
      <label className="field">조건
        <select value={f.kind} onChange={(e) => set("kind")(e.target.value)}>
          <option value="lines">줄 수 이상</option>
          <option value="sum">% 합 이상</option>
        </select>
      </label>
      <Num label="값" value={f.value} onChange={set("value")} />
      </div>
      <p className="field-hint muted small">줄 수 이상: 옵션이 몇 줄 이상 · % 합 이상: 같은 옵션 % 합계가 얼마 이상</p>
      <button type="submit" className="block">큐브 계산</button>
      <Alert error={error} />
      {result && (
        <div className="result">
          <p className="result-kpi"><strong>1회 성공 확률 {(result.probability * 100).toFixed(3)}%</strong> · 1회 {formatMeso(result.cost_per_reset)}</p>
          {result.cubes ? (
            <>
              <p>평균 {result.cubes.mean.toFixed(1)}회 ({formatMeso(result.meso.mean)})</p>
              <Dist d={result.cubes} unit="count" />
            </>
          ) : <p>이 조건은 나올 수 없습니다.</p>}
        </div>
      )}
    </form>
  );
}

export function CraftPanel({ initialCube }) {
  const [f, setF] = useState({ price: "", base: "", level: "200", start: "0", target: "22", destroy: "30억",
                               cubeP: initialCube ? String(initialCube.probability * 100) : "",
                               cubeCost: initialCube ? String(initialCube.cost) : "" });
  const { error, setError, result, run } = useAsync();
  const set = (k) => (v) => setF((x) => ({ ...x, [k]: v }));
  const submit = (e) => {
    e.preventDefault();
    const price = parsePrice(f.price), base = parsePrice(f.base) ?? 0;
    if (!price) return setError({ message: "매물 가격을 입력해 주세요 (예: 200억)." });
    run(() => postCraft({ price, base_price: base, level: Number(f.level), start_star: Number(f.start),
                          target_star: Number(f.target), destroy_cost: parsePrice(f.destroy) ?? 0,
                          cube_p: f.cubeP ? Number(f.cubeP) / 100 : 0, cube_cost: parsePrice(f.cubeCost) ?? 0 }));
  };
  return (
    <form onSubmit={submit} className="panel">
      <PanelHead title="매물 vs 직작" icon="layers" subtitle="경매장 매물 가격이 직접 만들 때(스타포스+큐브) 비용 분포의 어디쯤인지 알려 드려요." />
      <div className="field-grid">
        <Num label="매물 가격" value={f.price} onChange={set("price")} placeholder="200억" />
        <Num label="베이스 템 가격" value={f.base} onChange={set("base")} placeholder="노작 시세" />
        <Num label="장비 레벨" value={f.level} onChange={set("level")} />
        <Num label="시작 성" value={f.start} onChange={set("start")} />
        <Num label="목표 성" value={f.target} onChange={set("target")} />
        <Num label="파괴 시 비용" value={f.destroy} onChange={set("destroy")} />
        <Num label="목표 잠재 1회 확률(%)" value={f.cubeP} onChange={set("cubeP")} />
        <Num label="재설정 1회 가격" value={f.cubeCost} onChange={set("cubeCost")} />
      </div>
      {initialCube && <p className="field-hint muted small">잠재 재설정 결과에서 확률·1회 가격을 가져왔어요.</p>}
      <button type="submit" className="block">직작 비교</button>
      <Alert error={error} />
      {result && (
        <div className="result">
          <p className="result-kpi"><strong>매물은 직작 평균의 {(result.ratio_to_mean * 100).toFixed(1)}%</strong> (직작 평균 {formatMeso(result.craft_mean)})</p>
          <p>직작하면 {(result.prob_craft_costs_more * 100).toFixed(1)}% 확률로 이 가격보다 더 듭니다.</p>
          <Dist d={result.distribution} />
          <p className="muted">{result.note}</p>
        </div>
      )}
    </form>
  );
}

export function OptimizePanel({ name, listings, defense, feeRate = 0.05 }) {
  const [budget, setBudget] = useState("");
  const { error, setError, result, run } = useAsync();
  const submit = (e) => {
    e.preventDefault();
    if (!listings.length) return setError({ message: "먼저 매물을 추가해 주세요." });
    const b = parsePrice(budget);
    if (b == null) return setError({ message: "예산을 입력해 주세요 (예: 50억)." });
    run(() => postOptimize(name, { budget: b, boss_defense: defense, fee_rate: feeRate, candidates: listings }));
  };
  return (
    <form onSubmit={submit} className="panel">
      <PanelHead title="예산 최적화 (매물 목록 기준)" subtitle="예산 안에서 부위당 1개씩 골라 실딜이 가장 오르는 조합을 찾아요." />
      <Num label="예산" value={budget} onChange={setBudget} placeholder="50억" />
      <button type="submit">최적화</button>
      <Alert error={error} />
      {result && (
        <div className="result">
          <p className="result-kpi"><strong>실딜 {formatPct(result.gain_pct)}</strong> · {formatMeso(result.spent)} 사용 ({settingLabel(result.setting)} 기준)</p>
          {result.actions.length ? (
            <ol className="plain">
              {result.actions.map((a, i) => <li key={i}>{i + 1}. {a.slot} · {a.name} · {formatMeso(a.cost)}</li>)}
            </ol>
          ) : <p>예산 안에서 실딜을 올리는 조합이 없습니다.</p>}
        </div>
      )}
    </form>
  );
}
