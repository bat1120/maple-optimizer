import { hashFor } from "../router.js";
import Icon from "../ui/icons.jsx";

export const TAB_LABEL = { summary: "요약", upgrade: "업그레이드", calc: "계산기" };
export const TAB_ICON = { summary: "user", upgrade: "trend", calc: "calc" };

// 휴대폰(≤720px)에서만 보이는 아래 탭 막대. PC에서는 캐릭터 화면 위쪽 탭을 쓴다(CSS로 전환).
export default function BottomTabs({ route }) {
  return (
    <nav className="bottom-tabs" aria-label="캐릭터 화면 탭">
      {Object.entries(TAB_LABEL).map(([tab, label]) => (
        <a key={tab} href={hashFor({ ...route, tab })} aria-current={route.tab === tab ? "page" : undefined}>
          <Icon name={TAB_ICON[tab]} size={20} /><span>{label}</span>
        </a>
      ))}
    </nav>
  );
}
