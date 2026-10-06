import CalcPanels from "../calc/CalcPanels.jsx";

export default function Calc() {
  return (
    <div className="calc-page">
      <h1>강화 계산기</h1>
      <p className="muted">캐릭터 없이도 쓸 수 있어요. 스타포스 기대 비용, 잠재 재설정 기대비용, 매물 vs 직작을 비교해요.</p>
      <CalcPanels />
    </div>
  );
}
