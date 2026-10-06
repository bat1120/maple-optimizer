import { useState } from "react";
import { CraftPanel, CubePanel, StarforcePanel } from "../Panels.jsx";

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
