import { useRoute } from "./router.js";
import TopBar from "./layout/TopBar.jsx";
import Home from "./pages/Home.jsx";
import Character from "./pages/Character.jsx";
import Calc from "./pages/Calc.jsx";
import Admin from "./pages/Admin.jsx";

// 주소(#/, #/c/<닉네임>?tab=, #/calc, #/admin) → 화면. 관리자 화면은 메뉴에 두지 않는다.
export default function App() {
  const route = useRoute();
  return (
    <>
      <TopBar route={route} />
      <main className={`page page-${route.page}`}>
        {route.page === "home" && <Home />}
        {route.page === "character" && <Character key={route.name} route={route} />}
        {route.page === "calc" && <Calc />}
        {route.page === "admin" && <Admin />}
      </main>
      <footer className="footer muted small">
        데이터: 넥슨 Open API(약 15분 지연) · 이 사이트는 넥슨과 관계없는 개인 프로젝트예요
      </footer>
    </>
  );
}
