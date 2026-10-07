import { useState } from "react";
import { CraftPanel, CubePanel, StarforcePanel } from "../Panels.jsx";

// 계산기 사용 방법(캐릭터 화면 '계산기' 탭과 #/calc 페이지 공통). 실제로 있는 입력·결과만 적는다.
export const CALC_STEPS = [
  <><strong>스타포스 비용</strong>: 장비 레벨·시작/목표 성·파괴 시 비용을 넣고 이벤트를 고르면 평균과 분포(중앙값·p75·p90)가 나와요.</>,
  <><strong>잠재 재설정</strong>: 원하는 옵션과 조건을 고르면 1회 성공 확률과 평균 재설정 횟수가 나와요.</>,
  <>잠재 재설정을 먼저 계산하면 <strong>매물 vs 직작</strong> 칸에 확률·1회 가격이 자동으로 들어가요. 매물 가격을 넣고 비교해 보세요.</>,
];

// 강화 계산기 3종. 캐릭터 화면 '계산기' 탭과 #/calc 페이지가 같이 쓴다.
export default function CalcPanels() {
  const [cube, setCube] = useState(null);
  return (
    <div className="calc-grid">
      <StarforcePanel />
      <CubePanel onResult={setCube} />
      <CraftPanel key={cube ? `${cube.probability}-${cube.cost}` : "none"} initialCube={cube} />
    </div>
  );
}
