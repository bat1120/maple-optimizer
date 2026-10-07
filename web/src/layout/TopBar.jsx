import { useEffect, useState } from "react";
import { navigate } from "../router.js";
import { THEME_LABEL, applyTheme, loadTheme, nextTheme, saveTheme } from "../theme.js";
import Icon, { LogoMark } from "../ui/icons.jsx";

export function useTheme() {
  const [theme, setTheme] = useState(loadTheme);
  useEffect(() => { applyTheme(theme); }, [theme]);
  const cycle = () => setTheme((t) => { const n = nextTheme(t); saveTheme(n); applyTheme(n); return n; });
  return [theme, cycle];
}

const THEME_ICON = { light: "sun", dark: "moon", system: "monitor" };

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
        <a className="logo" href="#/"><LogoMark /><span className="logo-text">메이플 장비 최적화</span></a>
        {route.page !== "home" && (
          <form role="search" className="topbar-search" onSubmit={submit}>
            <Icon name="search" size={16} className="field-icon" />
            <input type="search" aria-label="캐릭터 검색" placeholder="캐릭터 닉네임 검색" value={q}
                   onChange={(e) => setQ(e.target.value)} />
          </form>
        )}
        <nav className="topbar-nav" aria-label="주요 메뉴">
          <a className="nav-link" href="#/calc" aria-current={route.page === "calc" ? "page" : undefined}>
            <Icon name="calc" size={16} />계산기
          </a>
          <a className="nav-link" href="#/scouter" aria-current={route.page === "scouter" ? "page" : undefined}>
            <Icon name="link" size={16} />환산 도우미
          </a>
          <button type="button" className="ghost theme-toggle" onClick={cycle} aria-label={`테마: ${THEME_LABEL[theme]}`}
                  title="테마 바꾸기(시스템 → 라이트 → 다크)">
            <Icon name={THEME_ICON[theme]} size={16} /><span className="theme-label">{THEME_LABEL[theme]}</span>
          </button>
        </nav>
      </div>
    </header>
  );
}
