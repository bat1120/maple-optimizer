import { useEffect, useRef, useState } from "react";
import { hashFor, navigate } from "../router.js";
import { addRecent, clearRecent, closeHint, hintClosed, loadRecent } from "../recent.js";
import { getMarketStats } from "../api.js";
import Icon from "../ui/icons.jsx";

// 처음 온 사람용 안내 — 실제 있는 화면만 설명한다.
const FIRST_STEPS = [
  { icon: "search", title: "닉네임 검색", text: "캐릭터 닉네임을 넣으면 넥슨 Open API로 지금 스펙을 불러와요." },
  { icon: "user", title: "요약 탭", text: "프리셋별 장비창과, 장비·하이퍼·어빌 프리셋 조합의 보스 세팅 순위를 봐요." },
  { icon: "trend", title: "업그레이드 탭", text: "부위별 잠재·에디 다음 단계와 가격 대비 순위, 경매장 검색 조건을 알려 드려요." },
  { icon: "calc", title: "계산기 탭", text: "스타포스 기대 비용, 큐브 목표 확률, 매물 vs 직작을 계산해요." },
];

export default function Home() {
  const [q, setQ] = useState("");
  const [recent, setRecent] = useState(loadRecent);
  const [showHint, setShowHint] = useState(() => !hintClosed());
  const box = useRef(null);
  const [stats, setStats] = useState(null); // 모인 경매장 관측 수(공개 통계) — 못 불러와도 화면은 그대로
  useEffect(() => { getMarketStats().then(setStats).catch(() => {}); }, []);
  useEffect(() => {
    const on = (e) => {
      if (e.key === "/" && document.activeElement !== box.current) { e.preventDefault(); box.current?.focus(); }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);
  const submit = (e) => {
    e.preventDefault();
    const name = q.trim();
    if (!name) { box.current?.focus(); return; }
    addRecent(name);
    navigate({ page: "character", name });
  };
  const hideHint = () => { closeHint(); setShowHint(false); };
  return (
    <div className="home">
      <section className="hero">
        <span className="eyebrow"><Icon name="spark" size={14} />KMS · 보스 실딜 기준</span>
        <h1>내 장비, 어디부터 바꿀까?</h1>
        <p className="hero-sub">닉네임으로 스펙을 불러와 보스 실딜과 억당 효율로 업그레이드 순서를 알려 드려요.</p>
        <form role="search" className="hero-search" onSubmit={submit}>
          <div className="search-field">
            <Icon name="search" size={20} className="field-icon" />
            <input ref={box} type="search" aria-label="캐릭터 닉네임" placeholder="캐릭터 닉네임"
                   value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
            <kbd className="kbd" title="/ 키를 누르면 검색창으로 바로 가요">/</kbd>
          </div>
          <button type="submit" className="btn-lg">검색</button>
        </form>
        {recent.length > 0 && (
          <div className="recent" aria-label="최근 검색">
            <span className="recent-label"><Icon name="clock" size={14} />최근 검색</span>
            {recent.map((n) => <a key={n} className="chip chip-link" href={hashFor({ page: "character", name: n })}>{n}</a>)}
            <button type="button" className="link-button" onClick={() => setRecent(clearRecent())}>지우기</button>
          </div>
        )}
        <p className="hero-foot muted small">
          {recent.length > 0 ? "최근 검색은 이 브라우저에만 저장돼요." : "닉네임만 정확히 넣으면 돼요 — 월드는 고르지 않아도 돼요."}
        </p>
      </section>

      {showHint && (
        <section className="card first-visit" aria-labelledby="first-visit-title">
          <div className="first-visit-head">
            <h2 id="first-visit-title">처음이신가요? 이렇게 써 보세요</h2>
            <button type="button" className="icon-button" onClick={hideHint} aria-label="안내 닫기"><Icon name="close" size={16} /></button>
          </div>
          <ol className="step-cards">
            {FIRST_STEPS.map((s, i) => (
              <li key={s.title}>
                <span className="step-num">{i + 1}</span>
                <span className="step-icon"><Icon name={s.icon} size={18} /></span>
                <strong>{s.title}</strong>
                <span className="muted small">{s.text}</span>
              </li>
            ))}
          </ol>
          <p className="muted small">탭은 주소에 남아서 새로고침하거나 링크를 공유해도 같은 화면이 열려요.</p>
        </section>
      )}

      <section className="home-cards" aria-label="바로가기">
        <a className="card link-card" href="#/calc">
          <span className="card-icon"><Icon name="calc" /></span>
          <strong>스타포스·큐브 계산기</strong>
          <span className="muted small">기대 비용·파괴 횟수, 잠재 재설정 기대비용, 매물 vs 직작 — 캐릭터 없이도 돼요</span>
          <span className="card-cta">열기 <Icon name="chevron" size={14} /></span>
        </a>
        <a className="card link-card" href="#/scouter">
          <span className="card-icon"><Icon name="link" /></span>
          <strong>환산 주스탯 도우미</strong>
          <span className="muted small">경매장 화면 평가에서 읽은 매물을 MapleScouter 입력 화면에 옮기는 방법</span>
          <span className="card-cta">안내 보기 <Icon name="chevron" size={14} /></span>
        </a>
        <div className="card info-card">
          <span className="card-icon"><Icon name="layers" /></span>
          <strong>계산 기준</strong>
          <ul className="bullets muted small">
            <li>넥슨 Open API(약 15분 지연)</li>
            <li>실딜은 언제나 보스 세팅 기준</li>
            <li>큐브는 공식 확률표</li>
          </ul>
          {stats?.total > 0 && (
            <span className="stat-inline">지금까지 모인 경매장 관측 {stats.total.toLocaleString("ko-KR")}건{stats.first_day ? ` (${stats.first_day}부터)` : ""}</span>
          )}
        </div>
      </section>
    </div>
  );
}
