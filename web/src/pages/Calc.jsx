import CalcPanels, { CALC_STEPS } from "../calc/CalcPanels.jsx";
import { HowTo } from "../ui/Guide.jsx";
import Icon from "../ui/icons.jsx";

export default function Calc() {
  return (
    <div className="calc-page">
      <header className="page-head">
        <span className="page-icon"><Icon name="calc" size={22} /></span>
        <div>
          <h1>강화 계산기</h1>
          <p className="page-sub">캐릭터 없이도 쓸 수 있어요. 스타포스 기대 비용, 잠재 재설정 기대비용, 매물 vs 직작을 비교해요.</p>
        </div>
      </header>
      <HowTo steps={CALC_STEPS} note="내 캐릭터 기준 실딜까지 보려면 첫 화면에서 닉네임을 검색한 뒤 업그레이드 탭을 여세요." />
      <CalcPanels />
    </div>
  );
}
