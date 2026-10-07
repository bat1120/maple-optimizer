import { useEffect, useRef, useState } from "react";
import { SCOUTER_INPUT_URL, bookmarkletHref, clipboardText, sampleScouter } from "../scouter.js";

const SAMPLE = sampleScouter();

// 환산 계산기(MapleScouter) 연동 안내 + '환산 채우기' 북마클릿. 주소는 렌더 뒤에 넣는다(React의 javascript: 주소 경고를 피하려고).
export default function Scouter() {
  const link = useRef(null);
  useEffect(() => { link.current?.setAttribute("href", bookmarkletHref()); }, []);
  const [copied, setCopied] = useState(false);
  const copySample = async () => {
    try { await navigator.clipboard.writeText(clipboardText(SAMPLE)); setCopied(true); } catch { setCopied(false); }
  };
  return (
    <div className="scouter-page">
      <h1>환산 주스탯 계산기에 템 넣기</h1>
      <p className="muted">
        경매장 화면 평가에서 읽은 매물을, MapleScouter 입력 화면에 클릭 두 번으로 옮겨요. 템을 바꿨을 때 달라지는 스탯(세트 효과 포함)만 지금 칸 값에 더해요.
      </p>
      <p>
        <a className="button-link" href={SCOUTER_INPUT_URL} target="_blank" rel="noopener noreferrer">MapleScouter 입력 화면 열기 ↗</a>
      </p>
      <section className="card">
        <h3>1. 한 번만: 북마크 버튼 설치</h3>
        <p>아래 버튼을 브라우저 <strong>즐겨찾기(북마크) 막대로 끌어다 놓으세요.</strong> 즐겨찾기 막대가 안 보이면 Ctrl+Shift+B.</p>
        <p><a ref={link} className="bookmarklet" href="#/scouter" onClick={(e) => e.preventDefault()}>환산 채우기</a></p>
      </section>
      <section className="card">
        <h3>먼저 시험해 보기</h3>
        <p>경매장 데이터 없이 견본(보스 데미지 +10%, 크리 데미지 +5%)으로 북마크가 되는지 볼 수 있어요.</p>
        <p>
          <button type="button" onClick={copySample}>테스트용 복사</button>{" "}
          {copied && <span className="muted small">견본을 복사했어요 — MapleScouter 입력 화면에서 '환산 채우기'를 누르면 보스·크뎀 칸이 그만큼 올라가요(확인 뒤 같은 값을 빼거나 새로고침 전 검색 캐릭터 다시 불러오기)</span>}
        </p>
      </section>
      <section className="card">
        <h3>2. 쓸 때마다</h3>
        <ol>
          <li>캐릭터 화면 → 업그레이드 탭 → 경매장 화면 평가에서 매물 옆 <strong>[환산용 복사]</strong></li>
          <li>복사 옆 <strong>MapleScouter 열기 ↗</strong> — 내 캐릭터 정보 화면이 열려요</li>
          <li>즐겨찾기 막대의 <strong>환산 채우기</strong>를 누르기 — 입력 화면으로 넘어가 내 캐릭터 스탯으로 교체한 뒤 칸에 더해요. 처음엔 클립보드 읽기 허용을 물어요(허용 또는 붙여넣기 창에 Ctrl+V)</li>
          <li>위쪽에 "N칸 변경"이 뜨면 MapleScouter의 결과 보기를 누르세요. 되돌리려면 MapleScouter의 [되돌리기]</li>
        </ol>
        <p className="muted small">
          바뀌는 칸: 주스탯·부스탯(기본/%), 마력(공격력), 데미지, 보스 데미지, 최종 데미지, 방어율 무시(곱연산), 크리티컬 확률·데미지, 재사용 감소(초).
          '기본 스공' 칸은 건드리지 않아요. 칸 이름으로 찾기 때문에 MapleScouter 화면이 바뀌면 일부 칸을 못 찾을 수 있고, 그때는 못 찾은 칸 이름을 알려 줘요.
        </p>
      </section>
    </div>
  );
}
