import { useCallback, useEffect, useState } from "react";
import { getAdminSession, getBosses, getCharacter, getSettings } from "../api.js";
import AgentPanel from "../AgentPanel.jsx";
import { hashFor, navigate } from "../router.js";
import { addRecent } from "../recent.js";
import BottomTabs, { TAB_ICON, TAB_LABEL } from "../layout/BottomTabs.jsx";
import ProfileCard from "../character/ProfileCard.jsx";
import EquipmentGrid from "../character/EquipmentGrid.jsx";
import TopPick from "../character/TopPick.jsx";
import FreeSwitch from "../character/FreeSwitch.jsx";
import StatSummary from "../character/StatSummary.jsx";
import SettingsRanking from "../character/SettingsRanking.jsx";
import RoadmapPanel from "../RoadmapPanel.jsx";
import PathsPanel from "../PathsPanel.jsx";
import TargetRoadmapPanel from "../TargetRoadmapPanel.jsx";
import RecommendPanel from "../RecommendPanel.jsx";
import CalcPanels, { CALC_STEPS } from "../calc/CalcPanels.jsx";
import ScreenWatch from "../ScreenWatch.jsx";
import Icon from "../ui/icons.jsx";
import { ErrorState } from "../ui/Guide.jsx";

// 탭마다 '이 화면에서 할 수 있는 것' 한 줄 + 사용 방법. 실제로 있는 기능만 적는다.
export const TAB_GUIDE = {
  summary: {
    lead: "보스 세팅(실딜 1위 조합) 기준 장비·스탯과, 프리셋 조합별 보스 실딜 순위를 한눈에 봐요.",
    steps: [
      <>장비창 위 <strong>[프리셋 1·2·3]</strong>으로 장비 프리셋을 바꿔 볼 수 있어요. 처음엔 보스 세팅(실딜 1위 조합)의 프리셋이 열려요 — [보스]·[착용] 표시로 구분해요.</>,
      <>장비 칸을 누르면 <strong>잠재·에디 옵션</strong>이 열려요. 칸 테두리 색은 잠재 등급, ★ 숫자는 스타포스예요.</>,
      <><strong>보스 세팅 순위</strong>는 장비·하이퍼·어빌 프리셋 조합을 보스 실딜로 줄 세운 거예요. '현재 대비'가 +면 지금보다 세요.</>,
      <>위쪽 <strong>보스</strong>(목록에서 보스·난이도, 또는 방어율 직접 입력)를 바꾸면 순위와 업그레이드 계산이 그 보스로 다시 계산돼요. 요구 포스가 있는 보스는 포스 보정도 들어가요.</>,
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

// 2026-10-11 심사 3회차: 안내 한 줄과 '사용 방법' 막대가 같은 말을 두 번 했다 → 한 줄(누르면 사용 방법)로 합치고,
// 계산 설정(보스 방어율)은 프로필이 아니라 이 줄 오른쪽에 작게 둔다(자주 안 바꾸는 값이 핵심 숫자 자리를 차지했다).
export function TabIntro({ tab, defense, onDefense }) {
  const g = TAB_GUIDE[tab];
  return (
    <div className="tab-intro">
      <details className="howto guide tab-howto">
        <summary><Icon name={TAB_ICON[tab]} size={16} /><span className="tab-lead">{g.lead}</span><span className="howto-more">사용 방법</span></summary>
        <ol className="steps">{g.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
      </details>
      {onDefense && (
        <label className="defense-field">보스 방어율
          <input type="number" inputMode="numeric" value={defense} onChange={(e) => onDefense(Number(e.target.value) || 0)} />%
        </label>
      )}
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

// 접어 두는 구역(2026-10-11 심사 2회차: 1위가 셋으로 갈려 '무엇부터'가 흐려졌다 → 가격 대비 순위만 펼친다)
function Fold({ title, children }) {
  return (
    <details className="fold">
      <summary>{title}</summary>
      {children}
    </details>
  );
}

// 닉네임을 못 찾았을 때(404): 같은 이름 '다시 시도'는 막다른 길이라, 그 닉네임을 채운 검색창으로 고쳐 찾게 한다(2026-10-11 디자인 심사)
function NotFound({ name }) {
  const [q, setQ] = useState(name);
  const submit = (e) => { e.preventDefault(); if (q.trim()) navigate({ page: "character", name: q.trim() }); };
  return (
    <div className="card error-card not-found" role="alert">
      <span className="error-icon"><Icon name="alert" size={20} /></span>
      <div className="error-body">
        <p className="error-title">「{name}」 캐릭터를 찾지 못했어요</p>
        <p className="muted small">띄어쓰기·대소문자를 확인해 주세요. 막 만든 캐릭터는 넥슨 Open API에 나오기까지 시간이 걸려요.</p>
        <form role="search" className="hero-search retry-search" onSubmit={submit}>
          <div className="search-field">
            <Icon name="search" size={18} className="field-icon" />
            <input type="search" name="nickname" autoComplete="off" spellCheck={false} aria-label="캐릭터 닉네임 다시 검색"
                   value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <button type="submit">다시 검색</button>
        </form>
      </div>
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
  const [bosses, setBosses] = useState(null);
  const [isAdmin, setIsAdmin] = useState(null); // 관리자 로그인(쿠키)이면 맨 위에 AI 상담(2026-10-12). 캐릭터를 불러온 뒤 한 번 확인

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
  useEffect(() => {
    if (!summary || isAdmin !== null) return;
    getAdminSession().then((r) => setIsAdmin(r?.admin === true)).catch(() => setIsAdmin(false));
  }, [summary, isAdmin]);
  // 보스 목록은 캐릭터를 불러온 뒤 한 번(목록이 없으면 직접 입력만)
  useEffect(() => {
    if (!summary || bosses) return;
    getBosses().then((r) => setBosses(r?.bosses || [])).catch(() => setBosses([]));
  }, [summary, bosses]);

  return (
    <div className={`character tab-${tab}`}>
      {busy && !summary && <Skeleton />}
      {error && (error.status === 404 ? <NotFound name={name} /> : (
        <ErrorState message={error.message} onRetry={load}>
          잠시 뒤에 다시 시도해 주세요. <a href="#/">첫 화면으로</a>
        </ErrorState>
      ))}
      {summary && (
        <div className="fade-in">
          <ProfileCard name={name} summary={summary} best={settings?.best} defense={defense} onDefense={setDefense} onRefresh={load} busy={busy}
                       bosses={bosses || []} force={settings?.force} />
          {isAdmin && (
            <AgentPanel key={name} name={name} initialAuthed title="AI 상담"
                        watchProps={{ job: summary.character_class, level: summary.level, defense }} />
          )}
          {/* 추천 상자 하나에 두 줄(2026-10-11 심사 5회차: 띠 두 개가 모양이 달라 별개 부품처럼 보였다) */}
          {tab === "summary" && (
            <div className="picks">
              <FreeSwitch ranking={settings?.ranking} />
              <TopPick name={name} defense={defense} after={settings?.ranking?.[0]?.relative_to_active > 1} />
            </div>
          )}
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
              <div className="stack summary-side">
                <SettingsRanking ranking={settings?.ranking} loading={busy && !settings} active={summary.active_setting} />
                <StatSummary final={settings?.best?.final || summary.final} setting={settings?.best ? settings.best.setting : null} />
                {summary.excluded?.length > 0 && (
                  <section className="card">
                    <h3 className="panel-title">계산에서 뺀 옵션</h3>
                    <p className="panel-sub">실딜 계산에 넣지 않은 옵션이에요.</p>
                    <p className="muted small">{summary.excluded.join(", ")}</p>
                  </section>
                )}
              </div>
              {/* 처음엔 보스 세팅의 장비 프리셋(2026-10-17 사용자). 세팅 순위가 오면 다시 그린다 */}
              <EquipmentGrid key={settings?.best?.setting.equipment ?? "worn"} presets={summary.equipment_presets}
                             active={settings?.best?.setting.equipment ?? summary.active_setting?.equipment}
                             boss={settings?.best?.setting.equipment} worn={summary.active_setting?.equipment}
                             image={summary.profile?.image} name={name} />
            </div>
          )}
          {tab === "upgrade" && (
            <div className="stack">
              {/* 순서(2026-10-11 심사): 1순위 → 그 조건으로 경매장 검색 → 방법 비교 → 목표 배율 */}
              <RoadmapPanel name={name} defense={defense} autoLoad active={summary.active_setting} />
              {/* 2026-10-11 심사 3회차: 경매장 경로가 세 군데로 갈렸다 → 순위 카드의 [경매장 검색 조건 복사]가 기본,
                  나머지는 '다른 기준으로 보기' 아래 접힘으로, 화면 평가는 '고급 도구' 하나로 */}
              <h3 className="section-label">다른 기준으로 보기</h3>
              <Fold title="실딜만 보고 고르기 — 가격은 안 봐요"><RecommendPanel name={name} defense={defense} autoLoad /></Fold>
              <Fold title="방법별 비교 — 구매·직작·큐브·강화"><PathsPanel name={name} defense={defense} autoLoad showRefresh={false} /></Fold>
              <Fold title="목표 보스 배율까지의 순서"><TargetRoadmapPanel name={name} defense={defense} /></Fold>
              <h3 className="section-label">고급 도구</h3>
              <div className="pc-only">
                <Fold title="게임 경매장 화면을 읽어 매물 평가 (PC 전용)">
                  <ScreenWatch name={name} job={summary?.character_class} level={summary?.level} defense={defense} admin={false} />
                </Fold>
              </div>
              <p className="card mobile-only muted note-box">
                <Icon name="monitor" size={16} />
                게임 경매장 화면을 읽어 매물을 평가하는 기능은 PC에서만 돼요.
              </p>
            </div>
          )}
          {tab === "calc" && <CalcPanels />}
        </div>
      )}
      {(summary || !error) && <BottomTabs route={{ page: "character", name, tab }} />}
    </div>
  );
}
