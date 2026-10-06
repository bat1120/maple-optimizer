import { useCallback, useState } from "react";
import { getCharacter, getSettings, postListings } from "../api.js";
import { formatMeso, formatPct, formatRelative, formatStat, parsePotentials, parsePrice, settingLabel } from "../format.js";
import { loadListings, saveListings } from "../storage.js";
import { CraftPanel, CubePanel, OptimizePanel, StarforcePanel } from "../Panels.jsx";
import AgentPanel from "../AgentPanel.jsx";
import ScreenWatch from "../ScreenWatch.jsx";
import RecommendPanel from "../RecommendPanel.jsx";
import RoadmapPanel from "../RoadmapPanel.jsx";
import PathsPanel from "../PathsPanel.jsx";

const TOTAL_KEYS = ["STR", "DEX", "INT", "LUK", "ATK", "MATK", "ALL%", "BOSS", "IED", "DMG"];
const TOTAL_LABEL = { ATK: "공격력", MATK: "마력", "ALL%": "올스탯%", BOSS: "보공%", IED: "방무%", DMG: "데미지%" };
const EMPTY_FORM = { slot: "", part: "", name: "", total: {}, potentials: "", price: "", resale: "" };

function ErrorBox({ error }) {
  if (!error) return null;
  return <p role="alert" className="error">{error.message}</p>;
}

function Summary({ data }) {
  return (
    <section>
      <h2>{data.character_class} Lv.{data.level}</h2>
      <p>
        기준: {data.date ?? "현재"} · 적용 중인 세팅 {settingLabel(data.active_setting)} · 스탯공격력{" "}
        {Math.round(data.stat_attack.engine).toLocaleString()} (API {data.stat_attack.api.toLocaleString()})
      </p>
      <p className="muted">전투력(참고, 인게임 기록값) {data.combat_power_reference.toLocaleString()}</p>
      {data.excluded.length > 0 && <p className="muted">계산 제외 옵션: {data.excluded.join(", ")}</p>}
    </section>
  );
}

function SettingsTable({ ranking }) {
  return (
    <section>
      <h3>보스 세팅 순위 (프리셋 조합)</h3>
      <table>
        <thead><tr><th>#</th><th>조합</th><th>현재 대비</th><th>환산 주스탯</th></tr></thead>
        <tbody>
          {ranking.slice(0, 5).map((r, i) => (
            <tr key={settingLabel(r.setting)}>
              <td>{i + 1}</td><td>{settingLabel(r.setting)}</td>
              <td>{r.relative_to_active == null ? "—" : formatRelative(r.relative_to_active)}</td>
              <td>{r.main_stat_vs_active == null ? "—" : formatStat(r.main_stat_vs_active)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function ListingForm({ slots, onAdd }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState(null);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const submit = (e) => {
    e.preventDefault();
    const price = parsePrice(form.price);
    const resale = form.resale ? parsePrice(form.resale) : 0;
    if (!form.slot || !form.name || price == null || resale == null) {
      setError({ message: "부위, 아이템명, 가격(예: 45억 3000만)을 입력해 주세요." });
      return;
    }
    const total = Object.fromEntries(Object.entries(form.total).filter(([, v]) => v !== "" && !Number.isNaN(Number(v)))
      .map(([k, v]) => [k, Number(v)]));
    onAdd({ slot: form.slot, part: form.part || form.slot, name: form.name, total,
            potentials: parsePotentials(form.potentials), price, resale });
    setForm(EMPTY_FORM);
    setError(null);
  };
  return (
    <form onSubmit={submit} className="listing-form">
      <h3>매물 추가</h3>
      <label>부위
        <select value={form.slot} onChange={(e) => set("slot", e.target.value)}>
          <option value="">선택</option>
          {slots.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>
      <label>아이템명<input value={form.name} onChange={(e) => set("name", e.target.value)} /></label>
      <label>종류(무기 종류 등)<input value={form.part} onChange={(e) => set("part", e.target.value)} /></label>
      <fieldset>
        <legend>총 옵션 (툴팁 그대로)</legend>
        {TOTAL_KEYS.map((k) => (
          <label key={k}>{TOTAL_LABEL[k] ?? k}
            <input inputMode="decimal" value={form.total[k] ?? ""}
                   onChange={(e) => set("total", { ...form.total, [k]: e.target.value })} />
          </label>
        ))}
      </fieldset>
      <label>잠재·에디 (한 줄에 하나)
        <textarea rows={6} value={form.potentials} onChange={(e) => set("potentials", e.target.value)} />
      </label>
      <label>가격<input value={form.price} placeholder="45억 3000만" onChange={(e) => set("price", e.target.value)} /></label>
      <label>지금 템 판매 예상가(등록가 — 수수료는 자동으로 빼요)<input value={form.resale} placeholder="0" onChange={(e) => set("resale", e.target.value)} /></label>
      <ErrorBox error={error} />
      <button type="submit">매물 추가</button>
    </form>
  );
}

function ListingResults({ result }) {
  if (!result) return null;
  return (
    <section>
      <h3>억당 효율 ({settingLabel(result.setting)} 기준, {result.boss.name})</h3>
      <p className="muted">환산 주스탯: 같은 실딜 상승을 내는 최종 주스탯 증가량 = (상승률) × (주스탯×4 + 부스탯) / 4</p>
      <table>
        <thead><tr><th>부위</th><th>아이템</th><th>가격</th><th>실딜 상승</th><th>환산</th><th>억당</th><th>억당 환산</th><th>계산 제외</th></tr></thead>
        <tbody>
          {result.ranking.map((r, i) => (
            <tr key={i}>
              <td>{r.slot}</td><td>{r.name}</td><td>{formatMeso(r.price)}</td>
              <td>{formatPct(r.delta_pct)}</td><td>{formatStat(r.main_stat_gain)}</td>
              <td>{formatPct(r.per_100m)}</td><td>{formatStat(r.main_stat_gain_per_100m)}</td><td>{r.excluded.join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export default function Admin() {
  const [name, setName] = useState("");
  const [defense, setDefense] = useState(300);
  const [feeRate, setFeeRate] = useState(0.05); // 경매장 판매 수수료: 지금 템 판매 대금에서만 빠진다
  const [feeFromScreen, setFeeFromScreen] = useState(false);
  const onFeeRate = useCallback((f) => { setFeeRate(f); setFeeFromScreen(true); }, []);
  const [summary, setSummary] = useState(null);
  const [settings, setSettings] = useState(null);
  const [listings, setListings] = useState(loadListings);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [cube, setCube] = useState(null);
  const [screenItems, setScreenItems] = useState([]);

  const lookup = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const s = await getCharacter(name.trim());
      setSummary(s);
      setSettings(await getSettings(name.trim(), defense));
    } catch (err) {
      setSummary(null);
      setSettings(null);
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const updateListings = (next) => {
    setListings(next);
    saveListings(next);
  };

  const evaluate = async () => {
    setError(null);
    try {
      setResult(await postListings(name.trim(), { boss_defense: defense, fee_rate: feeRate, listings }));
    } catch (err) {
      setError(err);
    }
  };

  const slots = summary ? [...new Set(Object.values(summary.equipment_presets).flat().map((i) => i.slot))] : [];

  return (
    <div className="admin">
      <h1>관리자 도구</h1>
      <p className="muted">매물 직접 입력·효율 계산, 경매장 화면 분석·장비창 채점, AI 상담. 화면 분석·AI는 관리자 로그인이 필요해요.</p>
      <form onSubmit={lookup} className="search">
        <label>닉네임<input value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label>보스 방어율(%)
          <input type="number" value={defense} onChange={(e) => setDefense(Number(e.target.value) || 0)} />
        </label>
        <label>경매장 판매 수수료
          <select value={String(feeRate)} onChange={(e) => { setFeeRate(Number(e.target.value)); setFeeFromScreen(false); }}>
            <option value="0.05">5% (기본)</option>
            <option value="0.03">3% (MVP 실버 이상·PC방)</option>
            {![0.05, 0.03].includes(feeRate) && <option value={String(feeRate)}>{Math.round(feeRate * 1000) / 10}%</option>}
          </select>
          {feeFromScreen && <span className="muted"> 화면에서 읽음</span>}
        </label>
        <button type="submit" disabled={busy}>조회</button>
      </form>
      <ErrorBox error={error} />
      {summary && <Summary data={summary} />}
      {settings && <SettingsTable ranking={settings.ranking} />}
      {summary && (
        <>
          <ListingForm slots={slots} onAdd={(l) => updateListings([...listings, l])} />
          {listings.length > 0 && (
            <section>
              <h3>매물 {listings.length}개</h3>
              <ul>
                {listings.map((l, i) => (
                  <li key={i}>
                    {l.slot} · {l.name} · {formatMeso(l.price)}{" "}
                    <button type="button" onClick={() => updateListings(listings.filter((_, j) => j !== i))}>삭제</button>
                  </li>
                ))}
              </ul>
              <button type="button" onClick={evaluate}>효율 계산</button>
            </section>
          )}
          <ListingResults result={result} />
          <OptimizePanel name={name.trim()} listings={listings} defense={defense} feeRate={feeRate} />
        </>
      )}
      <section>
        <h2>강화 계산</h2>
        <div className="panels">
          <StarforcePanel />
          <CubePanel onResult={setCube} />
          <CraftPanel key={cube ? `${cube.probability}-${cube.cost}` : "none"} initialCube={cube} />
        </div>
      </section>
      <RecommendPanel name={summary ? name.trim() : ""} defense={defense} />
      <RoadmapPanel name={summary ? name.trim() : ""} defense={defense} />
      <PathsPanel name={summary ? name.trim() : ""} defense={defense} />
      <AgentPanel name={summary ? name.trim() : ""} screenItems={screenItems} feeRate={feeRate} />
      <ScreenWatch name={summary ? name.trim() : ""} defense={defense} onItems={setScreenItems} onFeeRate={onFeeRate} />
    </div>
  );
}
