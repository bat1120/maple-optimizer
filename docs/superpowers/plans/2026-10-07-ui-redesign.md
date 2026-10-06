# UI 개편 구현 계획

> 실행: 인라인(같은 세션), 작업마다 실패하는 테스트 먼저 → 구현 → 통과. 사용자 지시 "완료할 때까지 쭉 진행".

**Goal:** 설계(`docs/superpowers/specs/2026-10-07-ui-redesign-design.md`)대로 일반 유저 중심 화면(검색→요약→업그레이드)을 만든다.
**Architecture:** 해시 라우터 + 페이지 컴포넌트. 기존 패널·API·계산은 재사용. 서버는 캐릭터 응답에 프로필·장비 상세만 더한다.
**Tech:** React 18, Vite, Vitest + Testing Library, CSS 변수 토큰. FastAPI(파이썬) 서버.

## Global Constraints
- 새 UI 의존성 추가 금지(React·Vite만). 넥슨 새 호출 금지(이미 받는 응답만)
- 모든 화면 문구 한국어. 숫자는 억·만 표기(`format.js`), 숫자 열은 tabular-nums
- 기존 기능 테스트는 지우지 않고 위치만 옮긴다. 웹·파이썬 테스트 모두 통과 후 커밋

## Review Focus
1. 넥슨 응답에 `character_image`·`item_icon`이 없을 때(픽스처처럼) 화면이 깨지지 않는다(빈 아바타·이름 글자 칸)
2. 프리셋에 없는 슬롯·장비가 없는 프리셋 → 빈 칸, 오류 없음
3. 주소에 한글 닉네임·공백·잘못된 탭 → 인코딩 유지, 탭은 summary로
4. 휴대폰 폭(≤720px)에서 장비창이 목록으로 바뀌고 표가 넘치지 않는다
5. 관리자 화면 밖에서는 화면 분석·AI 상담이 렌더링되지 않는다(공개 화면에서 관리자 API를 부르지 않음)

## Task 1: 서버 — 프로필·장비 상세
- Files: `engine/stats/snapshot.py`(Item.icon, CharacterSnapshot.profile), `nexon/convert.py`, `server/service.py`, Test `tests/test_ui_payload.py`
- 테스트: 픽스처 레테 → `profile.world`가 basic의 world_name, 이미지 필드 없으면 `image is None`;
  장비 항목에 `potential_grade`·`potentials`·`additional`·`level`·`icon`(없으면 None) 키
- 완료: 새 테스트 + 기존 파이썬 테스트 통과

## Task 2: 라우터·테마
- Files: `web/src/router.js`, `web/src/theme.js`, Tests `router.test.js`, `theme.test.js`
- `parseHash("#/c/%EB%A0%88%ED%85%8C?tab=upgrade") → {page:"character", name:"레테", tab:"upgrade"}`, 잘못된 탭 → summary,
  모르는 주소 → home, `hashFor({...})` 왕복. 테마 `cycleTheme` light→dark→system, 저장·`data-theme` 적용

## Task 3: 레이아웃·스타일 토큰
- Files: `layout/TopBar.jsx`, `layout/BottomTabs.jsx`, `styles.css`(토큰·반응형), Test `layout.test.jsx`
- TopBar: 로고 링크 `#/`, 검색 제출 → navigate, 테마 버튼 라벨 순환. BottomTabs: 탭 3개, 현재 탭 표시

## Task 4: 첫 화면
- Files: `pages/Home.jsx`, `recent.js`, Test `Home.test.jsx`
- 검색 → `#/c/<닉네임>`, 최근 검색 최대 8개 저장·표시·클릭 이동, `/` 키로 검색창 포커스

## Task 5: 캐릭터 화면
- Files: `pages/Character.jsx`, `character/ProfileCard.jsx`, `character/EquipmentGrid.jsx`, `character/SettingsRanking.jsx`, Test `Character.test.jsx`
- 조회 중 뼈대, 오류 카드 + [다시 시도], 프로필 카드 숫자, 장비창: 등급 클래스(`grade-legendary` 등)·성 배지·빈 칸·프리셋 전환·상세 열기,
  탭 전환 → 주소 변경, 업그레이드 탭에 로드맵·경로·검색 추천, 계산기 탭에 3종 계산기
- 가격 대비 순위 막대 폭 = 억당 / 최대 억당(RoadmapPanel 표에 막대 추가)

## Task 6: 계산기·관리자 페이지
- Files: `pages/Calc.jsx`, `pages/Admin.jsx`, `admin/ListingTools.jsx`(기존 App의 매물 입력·결과·OptimizePanel 이동), Test `Admin.test.jsx`
- 관리자: 닉네임·방어율·수수료 입력, 매물 입력·효율 계산, AI 상담, 화면 연결(기존 컴포넌트 그대로)

## Task 7: App 셸 교체
- Files: `App.jsx`(라우터 셸), `App.test.jsx` 갱신
- 주소별 페이지 렌더, 테마 적용

## Task 8: 확인·배포
- `npm --prefix web test`, `npm --prefix web run build`, `uv run pytest`, validate 게이트
- 로컬 서버에서 PC·휴대폰 폭 화면을 직접 열어 확인(라이트·다크)
- 커밋·푸시 → Render 자동 배포 → 데모 주소에서 확인
