import { useCallback, useEffect, useState } from "react";
import { getCharacter, getSettings } from "../api.js";
import { hashFor } from "../router.js";
import { addRecent } from "../recent.js";
import BottomTabs, { TAB_LABEL } from "../layout/BottomTabs.jsx";
import ProfileCard from "../character/ProfileCard.jsx";
import EquipmentGrid from "../character/EquipmentGrid.jsx";
import SettingsRanking from "../character/SettingsRanking.jsx";
import RoadmapPanel from "../RoadmapPanel.jsx";
import PathsPanel from "../PathsPanel.jsx";
import RecommendPanel from "../RecommendPanel.jsx";
import CalcPanels from "../calc/CalcPanels.jsx";
import ScreenWatch from "../ScreenWatch.jsx";

function Skeleton() {
  return (
    <div data-testid="skeleton" aria-busy="true" aria-label="불러오는 중">
      <div className="card skeleton profile-skel"><span /><span /><span /></div>
      <div className="card skeleton grid-skel">{Array.from({ length: 10 }, (_, i) => <span key={i} />)}</div>
    </div>
  );
}

export default function Character({ route }) {
  const { name, tab } = route;
  const [defense, setDefense] = useState(300);
  const [summary, setSummary] = useState(null);
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const s = await getCharacter(name);
      setSummary(s);
      addRecent(name);
      setSettings(await getSettings(name, defense));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }, [name, defense]);

  useEffect(() => { setSummary(null); setSettings(null); }, [name]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="character">
      {busy && !summary && <Skeleton />}
      {error && (
        <div className="card error-card" role="alert">
          <p>{error.message}</p>
          <button type="button" onClick={load}>다시 시도</button>
        </div>
      )}
      {summary && (
        <>
          <ProfileCard name={name} summary={summary} defense={defense} onDefense={setDefense} onRefresh={load} busy={busy} />
          <nav className="tabs" role="tablist" aria-label="캐릭터 화면 탭">
            {Object.entries(TAB_LABEL).map(([t, label]) => (
              <a key={t} role="tab" aria-selected={tab === t} href={hashFor({ page: "character", name, tab: t })}>{label}</a>
            ))}
          </nav>
          {tab === "summary" && (
            <div className="summary-grid">
              <EquipmentGrid presets={summary.equipment_presets} active={summary.active_setting?.equipment}
                             image={summary.profile?.image} name={name} />
              <div className="stack">
                <SettingsRanking ranking={settings?.ranking} />
                {summary.excluded?.length > 0 && (
                  <section className="card"><h3>계산에서 뺀 옵션</h3><p className="muted small">{summary.excluded.join(", ")}</p></section>
                )}
              </div>
            </div>
          )}
          {tab === "upgrade" && (
            <div className="stack">
              <RoadmapPanel name={name} defense={defense} autoLoad />
              <PathsPanel name={name} defense={defense} autoLoad showRefresh={false} />
              <RecommendPanel name={name} defense={defense} autoLoad />
              <div className="pc-only"><ScreenWatch name={name} defense={defense} admin={false} /></div>
              <p className="card mobile-only muted">
                PC에서 열면 경매장 화면을 바로 평가할 수 있어요 — 게임 창을 공유하면 툴팁을 읽어 내 캐릭터 기준으로 계산해요(휴대폰 브라우저는 화면 공유를 지원하지 않아요).
              </p>
            </div>
          )}
          {tab === "calc" && <CalcPanels />}
        </>
      )}
      <BottomTabs route={{ page: "character", name, tab }} />
    </div>
  );
}
