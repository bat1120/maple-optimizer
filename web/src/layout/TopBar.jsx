import { useEffect, useState } from "react";
import { navigate } from "../router.js";
import { THEME_LABEL, applyTheme, loadTheme, nextTheme, saveTheme } from "../theme.js";

export function useTheme() {
  const [theme, setTheme] = useState(loadTheme);
  useEffect(() => { applyTheme(theme); }, [theme]);
  const cycle = () => setTheme((t) => { const n = nextTheme(t); saveTheme(n); applyTheme(n); return n; });
  return [theme, cycle];
}

export default function TopBar({ route }) {
  const [theme, cycle] = useTheme();
  const [q, setQ] = useState("");
  const submit = (e) => {
    e.preventDefault();
    if (q.trim()) { navigate({ page: "character", name: q.trim() }); setQ(""); }
  };
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <a className="logo" href="#/"><span className="logo-mark" aria-hidden="true">◆</span> 메이플 장비 최적화</a>
        {route.page !== "home" && (
          <form role="search" className="topbar-search" onSubmit={submit}>
            <input type="search" aria-label="캐릭터 검색" placeholder="캐릭터 닉네임" value={q}
                   onChange={(e) => setQ(e.target.value)} />
          </form>
        )}
        <nav className="topbar-nav">
          <a href="#/calc" aria-current={route.page === "calc" ? "page" : undefined}>계산기</a>
          <button type="button" className="ghost" onClick={cycle} aria-label={`테마: ${THEME_LABEL[theme]}`}>
            {theme === "dark" ? "☾" : theme === "light" ? "☀" : "◐"} {THEME_LABEL[theme]}
          </button>
        </nav>
      </div>
    </header>
  );
}
