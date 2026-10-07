# 메이플 장비 최적화 — 환산 채우기 (크롬 확장)

메이플 장비 최적화에서 고른 매물(또는 테스트 템)을 MapleScouter 환산 계산기에 **버튼 한 번**으로 넣는다.
확장이 MapleScouter 탭을 열고 → 내 캐릭터로 교체 → 템을 바꿨을 때 달라지는 스탯만 칸에 더한다. 결과 보기는 사용자가 누른다.

## 설치 (개발자 모드, 내 PC 시험용)

1. 크롬 주소창에 `chrome://extensions` 를 연다
2. 오른쪽 위 **개발자 모드**를 켠다
3. **압축해제된 확장 프로그램을 로드합니다** → 이 `extension` 폴더를 고른다
4. 메이플 장비 최적화 화면을 새로고침하면 매물 옆에 **[MapleScouter에 넣기]** 버튼이 생긴다

코드를 고친 뒤에는 `chrome://extensions` 에서 이 확장의 새로고침(↻)을 누른다.

## 구조

| 파일 | 하는 일 |
|---|---|
| `manifest.json` | MV3. 스크립트 권한은 `maplescouter.com`에만, 브리지는 우리 사이트(onrender·localhost)에만 |
| `bridge.js` | 우리 사이트 페이지 ↔ 확장. `window.postMessage({type:"MAPLEOPT_FILL", payload})`를 받아 백그라운드로 넘긴다 |
| `background.js`, `lib.js` | 그 캐릭터의 MapleScouter 정보 탭을 열고, 다 열리면 그 탭에 `generated/run.js`를 한 번 실행 |
| `generated/run.js` | **자동 생성** — `web/src/scouter.js`의 북마크와 같은 교체·채우기 코드. `web`에서 `npm run ext` |

- 서버로 아무것도 보내지 않는다. MapleScouter 화면의 입력칸만 바꾼다(되돌리기는 MapleScouter의 [되돌리기])
- 휴대폰 크롬은 확장을 지원하지 않는다(경매장 화면 평가도 PC 전용)
- 웹 스토어 등록(개발자 등록비 5달러, 심사 며칠)은 아직 하지 않았다
