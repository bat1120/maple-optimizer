# maple-optimizer — Claude 작업 규칙

메이플스토리(KMS) 장비 최적화 웹 서비스. 넥슨 Open API로 스펙을 불러와 실딜·억당 효율을 계산하고,
경매장 화면 공유를 읽어 매물을 평가한다. 관리자 AI 상담은 OpenAI(gpt-6-luna)를 쓴다.
스펙: `docs/superpowers/specs/2026-10-03-maple-optimizer-design.md` · 목표: `GOALS.md` · 기록: `goal-log.md`
**새 세션은 먼저 `docs/HANDOFF.md`(최근 작업·다음 할 일·클라우드에서 못 하는 것)를 읽는다.**

## 언어
- 사용자에게 보이는 모든 텍스트(답변·진행 메시지·이슈 댓글·커밋 메시지)는 한국어로 쓴다. 코드·식별자·명령어·경로만 원문.

## 명령 (리눅스·클라우드 세션 기준)
- 설치: `uv sync` · `npm --prefix web ci`
- 테스트: `uv run pytest -q --ignore=tests/goals` · `npm --prefix web test`
- 목표 판정: `uv run pytest tests/goals/test_<id>.py -q -rs` — skip은 통과가 아니다
- 웹 빌드: `npm --prefix web run build` (서버가 `web/dist`를 서빙)
- 로컬 서버: `uv run uvicorn server.app:default_app --factory --port 8000` (`.env` 필요 — 클라우드에는 없다)
- Windows 게이트(`scripts/validate.ps1`, `scripts/verify.ps1 -Goal <ID>`)는 `pwsh`가 있으면 그대로 써도 된다

## 작업 방식
- 기능·버그 수정은 실패하는 테스트를 먼저 쓰고 실패를 확인한 뒤 구현한다.
- 커밋 전에 위 두 테스트가 모두 통과해야 한다. 실패하면 커밋하지 않고 원인을 남긴다.
- 목표(GOALS.md)는 7단계: LOAD → BASELINE → BUILD → VALIDATE(차단) → DEPLOY(없음) → VERIFY(차단) → RECORD.
  성공 기준은 숫자여야 하고, 진행 중에 낮추지 않는다. 같은 게이트 3번 연속 실패면 BLOCKED로 적고 이유를 goal-log.md에 남긴다.
- 목표를 끝내면 GOALS.md 상태와 goal-log.md를 갱신한다. 판단이 필요한 결정은 `Ruling: 결정 — 이유 — 틀렸을 때 비용`으로 남긴다.
- 커밋 메시지는 한국어, 끝에 빈 줄 다음 `Co-Authored-By: Claude <noreply@anthropic.com>`. main에 커밋·푸시한다.

## 금지
- `.env`·키·토큰 출력이나 커밋 (`NEXON_API_KEY`, `OPENAI_API_KEY`, `ADMIN_PASSWORD_HASH`, `SESSION_SECRET` 등)
- 사람 몫 목표(H*) 수행 — 서버 생성·키 신청·Secrets 등록·게임 화면 조작은 사람이 한다
- 넥슨·경매장 자동 수집, 내부 API 호출, 자동화 차단 우회 (2026-10-05: 경매장 API는 자동화 차단 신호로 막힘 → 화면 스캔만 쓴다)
- 숫자 추정: 측정·관측값만 쓴다. 없으면 "측정값 없음". 가격은 `price_text`를 글자 그대로
- 남의 이미지를 저장소나 학습에 올리기 (`.data/`는 git 제외, 로컬 평가용)
- 다른 저장소 수정

## 알아 둘 것
- 화면 분석: `server/tooltip.py`(툴팁 찾기·별 세기), `server/vision.py`(AI 판독·검산·FrameCache), `web/src/watch.js`(브라우저 쪽 변화 감지).
  툴팁 찾기·건너뛰기는 AI 비용이 0이고, 같은 툴팁 재사용은 '같은 자리·글자·3초 안'일 때만(숫자 하나 다른 매물은 그림으로 못 가른다).
- 계산 엔진: `engine/` — 실딜은 언제나 보스 세팅 기준. 큐브 확률표는 `engine/data/`(공식표).
- 배포: `main` 푸시 → `.github/workflows/deploy.yml`(테스트 → ghcr 이미지 → `DEPLOY_ENABLED`일 때 VM). Dockerfile은 서버가 import하는 패키지를 전부 COPY해야 한다(`tests/test_dockerfile.py`).
