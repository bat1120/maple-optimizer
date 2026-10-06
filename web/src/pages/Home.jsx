import { useEffect, useRef, useState } from "react";
import { hashFor, navigate } from "../router.js";
import { addRecent, loadRecent } from "../recent.js";
import { getMarketStats } from "../api.js";

export default function Home() {
  const [q, setQ] = useState("");
  const [recent] = useState(loadRecent);
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
    if (!name) return;
    addRecent(name);
    navigate({ page: "character", name });
  };
  return (
    <div className="home">
      <section className="hero">
        <h1>내 장비, 어디부터 바꿀까?</h1>
        <p className="muted">닉네임으로 스펙을 불러와 보스 실딜과 억당 효율로 업그레이드 순서를 알려 드려요.</p>
        <form role="search" className="hero-search" onSubmit={submit}>
          <input ref={box} type="search" aria-label="캐릭터 닉네임" placeholder="캐릭터 닉네임  ( / 키로 바로 입력)"
                 value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
          <button type="submit">검색</button>
        </form>
        {recent.length > 0 && (
          <div className="recent">
            <span className="muted">최근 검색</span>
            {recent.map((n) => <a key={n} className="chip" href={hashFor({ page: "character", name: n })}>{n}</a>)}
          </div>
        )}
      </section>
      <section className="home-cards">
        <a className="card link-card" href="#/calc">
          <strong>스타포스·큐브 계산기</strong>
          <span className="muted">기대 비용·파괴 횟수, 잠재 재설정 기대비용, 매물 vs 직작</span>
        </a>
        <div className="card">
          <strong>계산 기준</strong>
          <span className="muted">넥슨 Open API(약 15분 지연) · 보스 세팅 기준 실딜 · 공식 큐브 확률표</span>
          {stats?.total > 0 && (
            <span className="muted">지금까지 모인 경매장 관측 {stats.total.toLocaleString("ko-KR")}건{stats.first_day ? ` (${stats.first_day}부터)` : ""}</span>
          )}
        </div>
      </section>
    </div>
  );
}
