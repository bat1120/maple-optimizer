// 해시 주소 ↔ 화면. Render 같은 정적 호스팅에서도 서버 설정 없이 새로고침·공유가 된다.
import { useEffect, useState } from "react";

export const TABS = ["summary", "upgrade", "calc"];

export function parseHash(hash) {
  const raw = (hash || "").replace(/^#/, "");
  const [path, query = ""] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "c" && parts[1]) {
    const tab = new URLSearchParams(query).get("tab");
    return { page: "character", name: decodeURIComponent(parts[1]), tab: TABS.includes(tab) ? tab : "summary" };
  }
  if (parts[0] === "calc") return { page: "calc" };
  if (parts[0] === "admin") return { page: "admin" };
  if (parts[0] === "scouter") return { page: "scouter" };
  return { page: "home" };
}

export function hashFor(route) {
  if (route.page === "character") {
    const tab = route.tab && route.tab !== "summary" ? `?tab=${route.tab}` : "";
    return `#/c/${encodeURIComponent(route.name)}${tab}`;
  }
  if (route.page === "calc") return "#/calc";
  if (route.page === "admin") return "#/admin";
  if (route.page === "scouter") return "#/scouter";
  return "#/";
}

export function navigate(route) {
  window.location.hash = hashFor(route);
}

export function useRoute() {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}
