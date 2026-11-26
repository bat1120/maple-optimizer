import { useCallback, useEffect, useRef, useState } from "react";
import { getBosses, getCharacter, getSettings } from "../api.js";
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
import PlanPanel from "../PlanPanel.jsx";
import { FLOW, WATCH_TITLE } from "../flow.js";
import PathsPanel from "../PathsPanel.jsx";
import SwapsPanel from "../SwapsPanel.jsx";
import ArmorSetsPanel from "../ArmorSetsPanel.jsx";
import TargetRoadmapPanel from "../TargetRoadmapPanel.jsx";
import RecommendPanel from "../RecommendPanel.jsx";
import CalcPanels, { CALC_STEPS } from "../calc/CalcPanels.jsx";
import ScreenWatch from "../ScreenWatch.jsx";
import Icon from "../ui/icons.jsx";
import { ErrorState, RowsSkeleton } from "../ui/Guide.jsx";

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

// 이 서비스의 흐름을 순서로 보여 준다(2026-11-23 심사 3명 공통: 추천 → 경매장 검색 → 화면 공유 → 딜 계산이 화면에 순서로 안 보였다)
// current: 지금 단계(1 = 추천을 보는 중, 3 = 화면 공유 칸을 연 상태). 지난 단계는 흐리게, 지금 단계는 주황 테두리
// go: 요약 탭에서는 단계 줄 끝에 '업그레이드 탭에서 시작하기' 버튼을 단다
export function FlowSteps({ current = 1, go = null }) {
  return (
    <ol className={`flow-steps${go ? " with-go" : ""}`} aria-label="이렇게 진행해요">
      {FLOW.map((s, i) => (
        <li key={s.title} className={i + 1 === current ? "is-now" : i + 1 < current ? "is-done" : undefined}
            aria-current={i + 1 === current ? "step" : undefined}><span className="flow-no">{i + 1}</span><span className="flow-text"><strong>{s.title}</strong><span className="muted">{s.text}</span></span></li>
      ))}
      {go && <li className="flow-go"><a className="button-link" href={go}>업그레이드 순서 보기</a></li>}
    </ol>
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
// 처음 펼칠 때 그린다(그 전엔 계산 요청도 안 나간다) — 2026-10-17 점검: 탭을 열자마자 요청이 몰려 분당 한도에 걸렸다.
// 한 번 펼친 뒤엔 접어도 그대로 둔다(화면 평가의 공유 세션·읽은 매물이 사라지지 않게).
function Fold({ title, children, open, onToggle, foldRef }) {
  const [seen, setSeen] = useState(!!open);
  useEffect(() => { if (open) setSeen(true); }, [open]);
  const toggle = (e) => {
    const o = e.currentTarget.open;
    if (o) setSeen(true);
    onToggle?.(o);
  };
  return (
    <details className="fold" ref={foldRef} open={open} onToggle={toggle}>
      <summary>{title}</summary>
      {seen ? children : null}
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

// 약한 캐릭터: 방어율 무시가 낮으면 기본값(방어율 300%) 보스에는 피해가 0이라 추천을 만들 수 없다. 사용자가 방어율을 직접
// 고르기 전이라면 피해가 들어가는 값까지 차례로 낮춰서 보여 준다(2026-11-25 — 전에는 오류 문구만 나와 직접 낮춰야 했다)
export const AUTO_DEFENSES = [100, 50, 10];

export const BASELINE_POLL_MS = 8000; // 과거 날짜 3개를 불러오는 데 10초 안팎 — 그동안 이 간격으로 다시 묻는다

export default function Character({ route }) {
  const { name, tab } = route;
  const [defense, setDefense] = useState(300); // 입력칸에 보이는 값(보스 id 또는 방어율)
  // 계산에 쓰는 값은 입력이 0.5초 멈춘 뒤에 바꾼다(2026-10-17 점검: 한 글자마다 요청이 최대 5건 나가 분당 한도에 걸렸다)
  const [calcDefense, setCalcDefense] = useState(300);
  useEffect(() => {
    const t = setTimeout(() => setCalcDefense(defense), 500);
    return () => clearTimeout(t);
  }, [defense]);
  // 순위 카드 [이 조건으로 찾은 매물 평가하기] → 화면 공유 평가 칸을 열고 찾는 조건을 보여 준다(2026-10-17)
  const [watchOpen, setWatchOpen] = useState(false);
  const [stage, setStage] = useState(1); // 계획 패널이 알려 주는 지금 단계(1 추천 · 2 검색 조건 · 3 화면 공유)
  const [watchTarget, setWatchTarget] = useState(null);
  const watchRef = useRef(null);
  const evaluate = (v) => {
    setWatchTarget(v);
    setWatchOpen(true);
    setTimeout(() => watchRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" }), 0);
  };
  const [summary, setSummary] = useState(null);
  const [settings, setSettings] = useState(null);
  // 세팅 순위(보스 세팅)를 못 받았을 때만 지금 착용 기준으로 보여 준다. 받는 동안에는 지금 착용(사냥용일 수 있다)을 먼저
  // 보여 주지 않는다 — 2026-11-26 사용자: 템 세팅을 보러 오는 곳이니 처음에 적용되는 것은 보스 세팅이어야 한다
  const [settingsFailed, setSettingsFailed] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [bosses, setBosses] = useState(null);

  // 캐릭터 정보는 이름이 바뀔 때만, 세팅 순위는 보스가 바뀔 때도 다시 부른다
  const touched = useRef(false);                 // 사용자가 보스·방어율을 직접 골랐는지
  const [lowered, setLowered] = useState(null);  // 자동으로 낮췄다면 낮춘 값
  const pickDefense = (v) => { touched.current = true; setLowered(null); setDefense(v); };
  const loadSettings = useCallback(async () => {
    // 피해가 0인지: 세팅 순위는 오류 없이 1위 실딜 지수 0으로 온다(운영에서 확인 — 처음엔 NO_DAMAGE 오류만 봐서 안 낮춰졌다). 오류로 와도 같게 다룬다
    const lower = () => {
      const next = !touched.current && typeof calcDefense === "number" ? AUTO_DEFENSES.find((d) => d < calcDefense) : null;
      if (next != null) { setLowered(next); setDefense(next); setCalcDefense(next); }
      return next != null;
    };
    try {
      const got = await getSettings(name, calcDefense);
      if (got?.ranking?.length && got.ranking[0].index === 0 && lower()) return;
      setSettings(got);
    } catch (e) {
      if (!(e.code === "NO_DAMAGE" && lower())) { setError(e); setSettingsFailed(true); }
    }
  }, [name, calcDefense]);
  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const s = await getCharacter(name);
      setSummary(s);
      addRecent(name);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }, [name]);

  useEffect(() => {
    setSummary(null); setSettings(null); setSettingsFailed(false);
    if (!touched.current) { setLowered(null); setDefense(300); setCalcDefense(300); }   // 자동으로 낮춘 값은 다음 캐릭터로 가져가지 않는다
  }, [name]);
  // 버프 없는 기준(2026-11-23): 서버가 과거 날짜를 뒤에서 불러오는 동안은 baseline.pending. 다 되면 한 번 더 받아,
  // 버프가 섞여 있었던 경우에만 계산을 다시 한다(숫자가 달라지는 건 그 경우뿐이다)
  const [calcKey, setCalcKey] = useState(0);
  useEffect(() => {
    if (!summary?.baseline?.pending) return undefined;
    const t = setTimeout(async () => {
      try {
        const s = await getCharacter(name);
        setSummary(s);
        if (!s.baseline?.pending && s.baseline?.buffed) setCalcKey((k) => k + 1);
      } catch { /* 다음 조회 때 다시 본다 */ }
    }, BASELINE_POLL_MS);
    return () => clearTimeout(t);
  }, [summary, name]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (summary) loadSettings(); }, [summary, loadSettings]);
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
          <ProfileCard name={name} summary={summary} best={settings?.best} pending={!settings && !settingsFailed} defense={defense} onDefense={pickDefense} onRefresh={load} busy={busy}
                       bosses={bosses || []} force={settings?.force} />
          {lowered != null && (
            <p className="baseline-note small" role="note"><Icon name="info" size={14} />
              방어율 무시가 낮아 방어율 300% 보스에는 피해가 들어가지 않아요. 그래서 방어율 {lowered}% 보스 기준으로 계산했어요 — 잡는 보스에 맞게 위에서 바꿀 수 있어요.</p>
          )}
          {summary.baseline?.buffed && (
            <p className="baseline-note small" role="note"><Icon name="info" size={14} />{summary.baseline.note}</p>
          )}
          {/* 추천 상자 하나에 두 줄(2026-10-11 심사 5회차: 띠 두 개가 모양이 달라 별개 부품처럼 보였다) */}
          {tab === "summary" && (
            <div className="picks">
              <FreeSwitch ranking={settings?.ranking} breakdown={settings?.free_breakdown} />
              <TopPick key={calcKey} name={name} defense={calcDefense} />
            </div>
          )}
          {/* AI 상담은 모두에게(2026-10-17). 일반 사용자는 하루 질문 수 제한 — 남은 횟수를 보여 준다.
              2026-11-23: 추천 결과 아래로 내리고 한 줄 입력으로 줄였다(결과가 질문 폼에 밀리지 않게) */}
          <details className="agent-fold">
            <summary><Icon name="info" size={16} /><strong>AI에게 물어보기</strong>
              <span className="muted">예: 50억으로 뭐부터 할까? · 경매장에서 뭘 검색할까?</span></summary>
            <AgentPanel key={name} name={name} initialAuthed title="AI에게 물어보기" showQuota
                        watchProps={{ job: summary.character_class, level: summary.level, defense: calcDefense }} />
          </details>
          <nav className="tabs" role="tablist" aria-label="캐릭터 화면 탭">
            {Object.entries(TAB_LABEL).map(([t, label]) => (
              <a key={t} role="tab" aria-selected={tab === t} href={hashFor({ page: "character", name, tab: t })}>
                <Icon name={TAB_ICON[t]} size={16} />{label}
              </a>
            ))}
          </nav>
          {tab === "summary" && <FlowSteps current={0} go={hashFor({ page: "character", name, tab: "upgrade" })} />}
          {tab !== "upgrade" && <TabIntro tab={tab} />}
          {tab === "summary" && (
            <div className="summary-grid">
              <div className="stack summary-side">
                <SettingsRanking ranking={settings?.ranking} loading={busy && !settings} />
                {!settings && !settingsFailed ? (
                  <section className="card" aria-busy="true"><h3 className="panel-title">주요 스탯</h3>
                    <p className="panel-sub">보스 세팅 기준으로 계산하는 중이에요…</p><RowsSkeleton rows={5} /></section>
                ) : (
                  <StatSummary final={settings?.best?.final || summary.final} setting={settings?.best ? settings.best.setting : null}
                               hpMain={summary.character_class === "데몬어벤져"} />
                )}
                {summary.excluded?.length > 0 && (
                  <section className="card">
                    <h3 className="panel-title">계산에서 뺀 옵션</h3>
                    <p className="panel-sub">실딜 계산에 넣지 않은 옵션이에요.</p>
                    <p className="muted small">{summary.excluded.join(", ")}</p>
                  </section>
                )}
              </div>
              {/* 처음엔 보스 세팅의 장비 프리셋(2026-10-17 사용자). 세팅 순위가 오면 다시 그린다 */}
              {!settings && !settingsFailed ? (
                <section className="card" aria-busy="true"><h3 className="panel-title">장비</h3>
                  <p className="panel-sub">보스 세팅의 장비 프리셋을 고르는 중이에요…</p><RowsSkeleton rows={6} /></section>
              ) : (
                <EquipmentGrid key={settings?.best?.setting.equipment ?? "worn"} presets={summary.equipment_presets}
                               active={settings?.best?.setting.equipment ?? summary.active_setting?.equipment}
                               boss={settings?.best?.setting.equipment} worn={summary.active_setting?.equipment}
                               image={summary.profile?.image} name={name} />
              )}
            </div>
          )}
          {tab === "upgrade" && (
            <div className="stack">
              {/* 2026-11-23 사용자: 계획 하나로 합친다 — 흐름 4단계 → 내 업그레이드 계획(추천 1 · 검색 조건 2 · 화면 공유와 결과 3·4)
                  → 다른 기준(잠재·에디만 본 순위 포함). 화면 공유 칸은 계획에서 고른 줄 바로 아래에 온다 */}
              <FlowSteps current={watchOpen ? 3 : stage} />
              <PlanPanel key={calcKey} name={name} defense={calcDefense} onEvaluate={evaluate}
                         onStage={(n) => { setStage(n); if (n < 3) setWatchOpen(false); }}
                         watch={(
                           <div className="pc-only">
                             <Fold title={WATCH_TITLE} open={watchOpen} onToggle={setWatchOpen} foldRef={watchRef}>
                               <ScreenWatch name={name} job={summary?.character_class} level={summary?.level} defense={calcDefense} admin={false} target={watchTarget} />
                             </Fold>
                           </div>
                         )} />
              <p className="card mobile-only muted note-box">
                <Icon name="monitor" size={16} />
                검색 화면을 읽어 매물을 평가하는 3·4단계는 PC에서 돼요. PC에서 이 주소를 열면 이어서 할 수 있어요.
              </p>
              {/* 2026-10-11 심사 3회차: 경매장 경로가 세 군데로 갈렸다 → 순위 카드의 [경매장 검색 조건 복사]가 기본,
                  나머지는 '다른 기준으로 보기' 아래 접힘으로, 화면 평가는 '고급 도구' 하나로 */}
              <h3 className="section-label">다른 기준으로 보기</h3>
              <Fold title="잠재·에디만 가격 대비 순위로 보기"><RoadmapPanel name={name} defense={calcDefense} autoLoad active={summary.active_setting} onEvaluate={evaluate} /></Fold>
              <Fold title="실딜만 보고 고르기 — 가격은 안 봐요"><RecommendPanel name={name} defense={calcDefense} autoLoad /></Fold>
              <Fold title="방법별 비교 — 구매·직작·큐브·강화"><PathsPanel name={name} defense={calcDefense} autoLoad showRefresh={false} /></Fold>
              <Fold title="방어구 세트 조합 — 카루타·앱솔·아케인·에테르넬"><ArmorSetsPanel name={name} defense={calcDefense} autoLoad /></Fold>
              <Fold title="다른 템으로 갈아타기 — 세트 효과까지"><SwapsPanel name={name} defense={calcDefense} autoLoad /></Fold>
              <Fold title="목표 보스 배율까지의 순서"><TargetRoadmapPanel name={name} defense={calcDefense} /></Fold>
            </div>
          )}
          {tab === "calc" && <CalcPanels />}
        </div>
      )}
      {(summary || !error) && <BottomTabs route={{ page: "character", name, tab }} />}
    </div>
  );
}
