# maple-optimizer — Claude 작업 규칙

메이플스토리(KMS) 장비 최적화 웹 서비스. 넥슨 Open API로 스펙을 불러와 실딜·억당 효율을 계산하고,
경매장 화면 공유를 읽어 매물을 평가한다. AI 상담은 OpenAI(gpt-6-luna)를 쓴다.

**이 프로젝트가 하려는 일(2026-11-23 사용자):** 모든 메이플 유저가 자기 템을 객관적으로 진단하고, 지금 가진 재화로
스펙을 어디까지 올리는 게 적당한지 계산해 준다. 흐름은 ① AI가 내 캐릭터에 맞는 템 세팅을 추천 → ② 그 조건을 게임 경매장에서 검색
→ ③ 넥슨 API로는 경매장 매물을 볼 수 없어서, 화면 공유로 받은 검색 화면의 매물을 OCR·YOLO 등으로 읽음 → ④ 읽은 매물을
끼웠을 때의 실제 딜량을 계산. 새 기능·프롬프트·도구는 이 흐름의 어느 단계를 돕는지로 판단한다.
스펙·계획(`docs/superpowers/`)·목표(`GOALS.md`)·기록(`goal-log.md`)·목표 판정(`tests/goals/`)·디자인 규칙(`design.md`)은
사용자 PC에만 있고 GitHub에는 없다(2026-10-10). 클라우드 세션에서는 없으니 필요하면 사용자에게 묻는다.
**새 세션은 먼저 `docs/HANDOFF.md`(최근 작업·다음 할 일·클라우드에서 못 하는 것)를 읽는다.**

## 언어
- 사용자에게 보이는 모든 텍스트(답변·진행 메시지·이슈 댓글·커밋 메시지)는 한국어로 쓴다. 코드·식별자·명령어·경로만 원문.

## 명령 (리눅스·클라우드 세션 기준)
- 설치: `uv sync` · `npm --prefix web ci`
- 린트: `uv run ruff check .` (버그 규칙만 — 설정은 `pyproject.toml`. 일부러 어긴 곳은 `# noqa: <코드> — 이유`)
- 테스트: `uv run pytest -q --ignore=tests/goals` · `npm --prefix web test`
- 목표 판정: `uv run pytest tests/goals/test_<id>.py -q -rs` — skip은 통과가 아니다
- 화면 검증: `node tools/verify_ui/run.mjs` — 픽스처 서버(키 없음, 닉네임 = 직업 이름 예: 레테)로 실제 앱을 띄워
  기능 지도(`tools/verify_ui/features.json`)대로 확인하고 찍는다. 결과 `tools/verify_ui/out/<커밋>-<시각>/index.html`. 클라우드에서도 된다
- AI 상담 평가(이 PC 전용, 실제 모델·비용 발생 — 한 번에 20만 토큰 안팎): `uv run python tools/agent_eval/run.py [--only <id>] [--label <이름>]`.
  프롬프트(`agent/loop.py` SYSTEM)·도구 설명·도구 결과 모양을 바꾸면 앞뒤로 돌려 비교한다. 결과 `tools/agent_eval/out/…/report.html`
- 웹 빌드: `npm --prefix web run build` (서버가 `web/dist`를 서빙)
- 로컬 서버: `uv run uvicorn server.app:default_app --factory --port 8000` (`.env` 필요 — 클라우드에는 없다)
- Windows 게이트(`scripts/validate.ps1`, `scripts/verify.ps1 -Goal <ID>`)는 `pwsh`가 있으면 그대로 써도 된다

## 작업 방식
- 기능·버그 수정은 실패하는 테스트를 먼저 쓰고 실패를 확인한 뒤 구현한다.
- 커밋 전에 린트와 위 두 테스트가 모두 통과해야 한다. 실패하면 커밋하지 않고 원인을 남긴다.
- 화면에 보이는 것을 바꿨으면 화면 검증을 돌려 통과시키고, 끝낼 때 결과 페이지 경로를 알린다(사람은 코드 대신 그 페이지를 본다).
  기능을 더했으면 기능 지도에 한 줄을 더한다. 통과시키려고 기대값을 지우거나 낮추지 않는다.
- AI 상담이 규칙을 어기면 프롬프트에 줄을 보태기 전에 순서대로 본다: ① 도구가 막을 수 있나(입력 검사 + 고칠 방법이 적힌 오류)
  ② 도구 결과에 그대로 옮길 글자를 실을 수 있나(`*_text`) ③ 도구 결과가 너무 크지 않나 ④ 그래도 안 되면 프롬프트.
  고친 뒤 평가 세트(`tools/agent_eval/cases.json`)에 그 경우를 더한다(`tests/test_agent_guards.py` 참고).
- 같은 실수를 두 번 고쳤으면 이 파일에 한 줄을 보태기 전에 린트 규칙·테스트로 만들 수 있는지 먼저 본다
  (예: 패키지 경계 `tests/test_import_boundaries.py`, 불변 조건 `tests/test_properties.py`, Dockerfile `tests/test_dockerfile.py`).
- 목표(GOALS.md)는 7단계: LOAD → BASELINE → BUILD → VALIDATE(차단) → DEPLOY(없음) → VERIFY(차단) → RECORD.
  성공 기준은 숫자여야 하고, 진행 중에 낮추지 않는다. 같은 게이트 3번 연속 실패면 BLOCKED로 적고 이유를 goal-log.md에 남긴다.
- 목표를 끝내면 GOALS.md 상태와 goal-log.md를 갱신한다. 판단이 필요한 결정은 `Ruling: 결정 — 이유 — 틀렸을 때 비용`으로 남긴다.
- 커밋 메시지는 한국어, 끝에 빈 줄 다음 `Co-Authored-By: Claude <noreply@anthropic.com>`. main에 커밋·푸시한다.

## 금지
- `.env`·키·토큰 출력이나 커밋 (`NEXON_API_KEY`, `OPENAI_API_KEY`, `ADMIN_PASSWORD_HASH`, `SESSION_SECRET` 등)
- 사람 몫 목표(H*) 수행 — 서버 생성·키 신청·Secrets 등록·게임 화면 조작은 사람이 한다
- 넥슨·경매장 자동 수집, 내부 API 호출, 자동화 차단 우회 (2026-10-05: 경매장 API는 자동화 차단 신호로 막힘 → 화면 스캔만 쓴다)
- 환산주스탯(MapleScouter) 자동 접근·계산 결과 사용·계산 로직 역추적 (약관 제15조·권리 조항, 2026-10-10 확인). 2026-10-13 운영자가 연동은 어렵다고 답함 → 북마크·확장 삭제, 사람이 손으로 비교하는 검증 기준으로만
- 숫자 추정: 측정·관측값만 쓴다. 없으면 "측정값 없음". 가격은 `price_text`를 글자 그대로
  - 확률·비용·스탯 표처럼 확인이 필요한 데이터는 에이전트 판단(패턴 추정·기억)으로 고치지 않는다. 웹 검색으로 공식 출처
    (넥슨 공지·가이드·확률 공개 페이지)를 직접 열어 값을 확인한 뒤 고치고, 출처 주소·날짜를 데이터 파일(`_source`·`_verified`)과
    검산 테스트에 남긴다. 출처를 못 찾으면 고치지 않고 무엇이 의심되는지만 보고한다(2026-11-22 사용자 지시).
    공지 한두 쪽을 읽는 것은 되지만 주기·대량 수집 금지는 그대로다
- 남의 이미지를 저장소나 학습에 올리기 (`.data/`는 git 제외, 로컬 평가용)
- 다른 저장소 수정

## 알아 둘 것
- 화면 분석: `server/tooltip.py`(툴팁 찾기·별 세기), `server/ocr.py`(경매장 매물 툴팁 로컬 OCR — 코드로 확인되면 AI를 안 부른다,
  `VISION_OCR=0`이면 끔), `server/vision.py`(AI 판독·검산·FrameCache), `web/src/watch.js`(브라우저 쪽 변화 감지).
  툴팁 찾기·건너뛰기는 AI 비용이 0이고, 같은 툴팁 재사용은 '같은 자리·글자·3초 안'일 때만(숫자 하나 다른 매물은 그림으로 못 가른다).
- 계산 엔진: `engine/` — 실딜은 언제나 보스 세팅 기준. 큐브 확률표는 `engine/data/`(공식표).
- 배포: `main` 푸시 → `.github/workflows/deploy.yml`(테스트 → ghcr 이미지 → `DEPLOY_ENABLED`일 때 VM). Dockerfile은 서버가 import하는 패키지를 전부 COPY해야 한다(`tests/test_dockerfile.py`).
