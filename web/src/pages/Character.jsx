import { useCallback, useEffect, useState } from "react";
import { getCharacter, getSettings } from "../api.js";
import { hashFor } from "../router.js";
import { addRecent } from "../recent.js";
import BottomTabs, { TAB_ICON, TAB_LABEL } from "../layout/BottomTabs.jsx";
import ProfileCard from "../character/ProfileCard.jsx";
import EquipmentGrid from "../character/EquipmentGrid.jsx";
import SettingsRanking from "../character/SettingsRanking.jsx";
import RoadmapPanel from "../RoadmapPanel.jsx";
import PathsPanel from "../PathsPanel.jsx";
import TargetRoadmapPanel from "../TargetRoadmapPanel.jsx";
import RecommendPanel from "../RecommendPanel.jsx";
import CalcPanels, { CALC_STEPS } from "../calc/CalcPanels.jsx";
import ScreenWatch from "../ScreenWatch.jsx";
import Icon from "../ui/icons.jsx";
import { ErrorState, HowTo } from "../ui/Guide.jsx";

// 탭마다 '이 화면에서 할 수 있는 것' 한 줄 + 사용 방법. 실제로 있는 기능만 적는다.
export const TAB_GUIDE = {
  summary: {
    lead: "지금 장비와, 프리셋 조합별 보스 실딜 순위를 한눈에 봐요.",
    steps: [
      <>장비창 위 <strong>[프리셋 1·2·3]</strong>으로 장비 프리셋을 바꿔 볼 수 있어요. 처음엔 지금 적용 중인 프리셋이 열려요.</>,
      <>장비 칸을 누르면 <strong>잠재·에디 옵션</strong>이 열려요. 칸 테두리 색은 잠재 등급, ★ 숫자는 스타포스예요.</>,
      <><strong>보스 세팅 순위</strong>는 장비·하이퍼·어빌 프리셋 조합을 보스 실딜로 줄 세운 거예요. '현재 대비'가 +면 지금보다 세요.</>,
      <>위쪽 <strong>보스 방어율(%)</strong>을 바꾸면 순위와 업그레이드 계산이 그 값으로 다시 계산돼요.</>,
    ],
  },
  upgrade: {
    lead: "무엇을 바꾸면 보스 실딜이 오르는지, 가격 대비로 순서를 알려 드려요.",
    steps: [
      <><strong>가격 대비 순위</strong>에서 억당 효율 막대가 긴 것부터 보세요(큐브 메소 재설정 평균 비용 기준).</>,
      <><strong>경로 비교</strong>로 구매·직작·큐브 중 어느 쪽이 억당 실딜이 높은지 비교해요.</>,
      <><strong>경매장 검색 추천</strong>의 조건을 [복사]해서 게임 경매장에서 그대로 검색해요.</>,
      <>PC라면 <strong>경매장 화면 평가</strong>에 게임 창을 연결해 실제 매물을 내 캐릭터 기준으로 평가할 수 있어요.</>,
    ],
  },
  calc: {
    lead: "스타포스·큐브 비용과 매물 vs 직작을 계산해요. 결과는 서버가 계산한 값이에요.",
    steps: CALC_STEPS,
  },
};

export function TabIntro({ tab }) {
  const g = TAB_GUIDE[tab];
  return (
    <div className="tab-intro">
      <p className="tab-lead"><Icon name={TAB_ICON[tab]} size={16} />{g.lead}</p>
      <HowTo steps={g.steps} />
    </div>
  );
}

function Skeleton() {
  return (
    <div data-testid="skeleton" aria-busy="true" aria-label="불러오는 중" className="char-skel">
      <div className="card skeleton profile-skel">
        <span className="skel-avatar" />
        <div><span className="w40 h22" /><span className="w60" /><div className="skel-kpis"><span /><span /><span /></div></div>
      </div>
      <div className="skeleton tabs-skel"><span /><span /><span /></div>
      <div className="summary-grid">
        <div className="card skeleton grid-skel">{Array.from({ length: 15 }, (_, i) => <span key={i} />)}</div>
        <div className="card skeleton rows-skel"><span className="w40 h22" /><span /><span /><span /><span /></div>
      </div>
      <p className="muted small skel-note">넥슨 Open API에서 캐릭터 정보를 불러오는 중이에요…</p>
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
        <ErrorState message={error.message} onRetry={load}>
          닉네임을 다시 확인하거나 잠시 뒤에 다시 시도해 주세요. <a href="#/">첫 화면으로</a>
        </ErrorState>
      )}
      {summary && (
        <div className="fade-in">
          <ProfileCard name={name} summary={summary} defense={defense} onDefense={setDefense} onRefresh={load} busy={busy} />
          <nav className="tabs" role="tablist" aria-label="캐릭터 화면 탭">
            {Object.entries(TAB_LABEL).map(([t, label]) => (
              <a key={t} role="tab" aria-selected={tab === t} href={hashFor({ page: "character", name, tab: t })}>
                <Icon name={TAB_ICON[t]} size={16} />{label}
              </a>
            ))}
          </nav>
          <TabIntro tab={tab} />
          {tab === "summary" && (
            <div className="summary-grid">
              <EquipmentGrid presets={summary.equipment_presets} active={summary.active_setting?.equipment}
                             image={summary.profile?.image} name={name} />
              <div className="stack">
                <SettingsRanking ranking={settings?.ranking} loading={busy && !settings} />
                {summary.excluded?.length > 0 && (
                  <section className="card">
                    <h3 className="panel-title">계산에서 뺀 옵션</h3>
                    <p className="panel-sub">실딜 계산에 넣지 않은 옵션이에요.</p>
                    <p className="muted small">{summary.excluded.join(", ")}</p>
                  </section>
                )}
              </div>
            </div>
          )}
          {tab === "upgrade" && (
            <div className="stack">
              <RoadmapPanel name={name} defense={defense} autoLoad />
              <PathsPanel name={name} defense={defense} autoLoad showRefresh={false} />
              <TargetRoadmapPanel name={name} defense={defense} />
              <RecommendPanel name={name} defense={defense} autoLoad />
              <div className="pc-only"><ScreenWatch name={name} job={summary?.character_class} level={summary?.level} defense={defense} admin={false} /></div>
              <p className="card mobile-only muted note-box">
                <Icon name="monitor" size={16} />
                PC에서 열면 경매장 화면을 바로 평가할 수 있어요 — 게임 창을 공유하면 툴팁을 읽어 내 캐릭터 기준으로 계산해요(휴대폰 브라우저는 화면 공유를 지원하지 않아요).
              </p>
            </div>
          )}
          {tab === "calc" && <CalcPanels />}
        </div>
      )}
      <BottomTabs route={{ page: "character", name, tab }} />
    </div>
  );
}
