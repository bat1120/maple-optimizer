import { useRoute } from "./router.js";
import TopBar from "./layout/TopBar.jsx";
import Home from "./pages/Home.jsx";
import Character from "./pages/Character.jsx";
import Calc from "./pages/Calc.jsx";
import Admin from "./pages/Admin.jsx";
import Scouter from "./pages/Scouter.jsx";

// 주소(#/, #/c/<닉네임>?tab=, #/calc, #/admin) → 화면. 관리자 화면은 메뉴에 두지 않는다.
export default function App() {
  const route = useRoute();
  return (
    <>
      <a className="skip-link" href="#main">본문으로 건너뛰기</a>
      <TopBar route={route} />
      <main id="main" tabIndex={-1} className={`page page-${route.page}`}>
        {route.page === "home" && <Home />}
        {route.page === "character" && <Character key={route.name} route={route} />}
        {route.page === "calc" && <Calc />}
        {route.page === "admin" && <Admin />}
        {route.page === "scouter" && <Scouter />}
      </main>
      <footer className="footer muted small">
        <p>데이터: 넥슨 Open API(약 15분 지연) · 이 사이트는 넥슨과 관계없는 개인 프로젝트예요</p>
        <p>최근 검색·테마 설정은 이 브라우저에만 저장돼요</p>
      </footer>
    </>
  );
}
