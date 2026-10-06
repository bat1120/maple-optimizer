// 라이트·다크·시스템 테마. 시스템이면 data-theme을 지워 CSS가 prefers-color-scheme을 따르게 한다.
const KEY = "maple-optimizer:theme";
const ORDER = ["light", "dark", "system"];
export const THEME_LABEL = { light: "라이트", dark: "다크", system: "시스템" };

export function nextTheme(t) {
  return ORDER[(ORDER.indexOf(t) + 1) % ORDER.length];
}

export function loadTheme() {
  try {
    const t = localStorage.getItem(KEY);
    return ORDER.includes(t) ? t : "system";
  } catch {
    return "system";
  }
}

export function saveTheme(t) {
  try { localStorage.setItem(KEY, t); } catch { /* 저장 못 해도 이번 화면에는 적용된다 */ }
}

export function applyTheme(t) {
  const el = document.documentElement;
  if (t === "system") el.removeAttribute("data-theme");
  else el.dataset.theme = t;
}
