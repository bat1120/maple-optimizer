# maple-optimizer

메이플스토리(KMS) 캐릭터 닉네임으로 현재 스펙을 불러와 **보스 실딜 기준**으로 장비 교체·경매장 매물·강화 비용·예산 최적화를 계산하는 웹 서비스.

- 설계: `docs/superpowers/specs/2026-10-03-maple-optimizer-design.md`
- 진행 상황: `GOALS.md`, 기록: `goal-log.md`

## 무엇을 계산하나

| 기능 | API | 비고 |
|---|---|---|
| 캐릭터 요약 | `GET /api/character/{닉네임}` | 엔진 스탯공격력이 API 값과 맞는지 함께 표시. 전투력은 참고값(계산하지 않음) |
| 보스 세팅 순위 | `GET /api/character/{닉네임}/settings?boss_defense=300` | 장비·하이퍼·어빌리티 프리셋 조합(최대 27개)을 보스 실딜 지수로 정렬 |
| 매물 억당 효율 | `POST /api/character/{닉네임}/listings` | 경매장 툴팁의 총 옵션 + 잠재 문자열 입력 |
| 스타포스 비용 | `POST /api/enhance/starforce` | 정확 기대값 + 분포(중앙값·p75·p90) |
| 큐브 목표 확률 | `POST /api/enhance/cube` | 공식 확률표(레전드리·무기·200) 정확 열거 |
| 직작 vs 매물 | `POST /api/craft/compare` | 직작 비용 분포에서 매물 가격의 위치(추옵 미포함) |
| 예산 최적화 | `POST /api/character/{닉네임}/optimize` | 부위당 1개, 예산 이내 |
| 경매장 화면 분석 (관리자) | `POST /api/vision/listings` | 사용자가 공유한 웹 경매장 탭 화면을 바뀔 때마다 GPT 비전으로 읽어 평가. 넥슨 서버에는 요청하지 않는다(화면 픽셀만) |
| AI 에이전트 (관리자) | `POST /api/admin/login`, `POST /api/agent/chat` (SSE) | OpenAI Responses API 함수 호출(기본 `gpt-6-luna`). 숫자는 도구 결과에서만 인용, 대조 안 된 숫자는 경고 |

## 로컬 실행

필요: Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 20+.

```powershell
uv sync                      # Python 의존성
npm --prefix web install     # 웹 의존성
powershell -ExecutionPolicy Bypass -File scripts/run-local.ps1   # 웹 빌드 후 http://127.0.0.1:8000
```

웹 개발 모드: 서버를 띄운 상태에서 `npm --prefix web run dev` (Vite가 `/api`를 8000번으로 프록시).

## 시크릿 — 어디에 두나

| 값 | 위치 | 비고 |
|---|---|---|
| `NEXON_API_KEY` | 저장소 루트 `.env` (git 제외) 또는 환경변수 | 넥슨 Open API 개발 단계 키(5건/초, 1,000건/일). 공개 전에는 서비스 단계 키로 교체 |
| (배포 후) 같은 키 | VM의 `~/maple-optimizer/.env` | `docker compose`가 `env_file`로 읽는다 (H1) |
| `OPENAI_API_KEY` | `.env` (로컬·VM) | 관리자 에이전트용 OpenAI API 키 (H5). 없으면 에이전트만 꺼진다 |
| `OPENAI_MODEL` | `.env` | 기본 `gpt-6-luna`(저가). `gpt-6.1-sol`(중간)·`gpt-6-astra`(상위)로 바꿀 수 있다 |
| `ADMIN_PASSWORD_HASH` | `.env` | `uv run python -c "from server.admin import make_password_hash as h; print(h('비밀번호'))"` 결과. 비밀번호 원문은 저장하지 않는다 |
| `SESSION_SECRET` | `.env` | 32자 이상 임의 문자열 (관리자 쿠키 서명) |
| `AGENT_DAILY_TOKEN_BUDGET` | `.env` | 하루 토큰 상한(기본 200,000). 넘으면 Claude를 호출하지 않는다 |
| `VM_HOST`, `VM_USER`, `VM_SSH_KEY` | GitHub Actions Secrets | 배포용 SSH. 쓰기 전용 — 한 번 넣으면 다시 읽을 수 없다 (H3) |
| `GHCR_READ_TOKEN` | GitHub Actions Secrets | VM이 ghcr.io 이미지를 받을 때 쓰는 `read:packages` 토큰 (H3) |
| `DEPLOY_ENABLED` | GitHub Actions Variables (`true`) | 서버 준비 전에는 배포 단계를 건너뛴다 |

저장소에는 `.env.example`만 있다. 키 값을 채팅·이슈·로그에 붙이지 않는다.

## 배포 (Oracle Always Free ARM VM)

```bash
# VM에서 (Docker·compose 설치 후)
git clone <저장소> ~/maple-optimizer && cd ~/maple-optimizer
printf 'NEXON_API_KEY=...
' > .env
DOMAIN=<도메인> docker compose up -d --build     # 또는 CI 이미지: IMAGE=ghcr.io/<owner>/maple-optimizer:latest
```

- `Dockerfile`: 웹 빌드 → Python 런타임(uv). amd64·arm64 둘 다. 키는 이미지에 넣지 않고 실행 시 `.env`로 넣는다.
- `docker-compose.yml`: `api`(FastAPI) + `caddy`(자동 HTTPS, `deploy/Caddyfile`).
- `.github/workflows/deploy.yml`: 테스트 → arm64/amd64 이미지를 ghcr.io에 푸시 → (`DEPLOY_ENABLED=true`일 때) SSH로 VM 갱신.

## 테스트와 게이트

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate.ps1          # 회귀 스위트 (pytest + vitest)
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1 -Goal G5   # 목표별 판정
```

- `tests/fixtures/`는 익명화한 실제 넥슨 응답이다(2026-10-02~03). 넥슨 약관상 수집 데이터는 30일 안에 갱신해야 하므로 서비스 데이터로 쓰지 않는다. 다시 받으려면 `.raw/`에 넣고 `uv run python tools/build_fixtures.py`.
- 세트 매핑 데이터 재생성: `uv run --group analysis python tools/derive_set_data.py`

## 데이터 출처와 한계

- 스타포스 확률: 공식 패치노트(2025-03-20, 2026-03-19) 기준. 비용 공식은 비공식(나무위키). 잠재 재설정 가격은 레전드리 200제 4,500만만 인게임 확인, 나머지는 나무위키 — `engine/data/*.json`의 `_verified` 참고.
- 넥슨 API에 경매장이 없다. 매물은 직접 입력하거나, 경매장 화면을 공유해 화면 분석으로 읽는다.
- 선택: [maple-auction-mcp](https://github.com/oyc0401/maple-auction-mcp)를 로컬에서 연결하면(`AUCTION_MCP_CMD`, 크롬 확장 + 웹 경매장 로그인)
  로드맵 다음 단계 조건으로 웹 경매장을 검색해(판매 중 호가·판매 완료 체결가) 관측 시세에 넣는다. 공식 API가 아니라 로그인한 브라우저로
  검색을 대신 하는 방식이라 계정 위험은 사용자 몫 — 읽기 도구만 쓰고, 갱신 한 번에 검색 15회 이하, 주기·대량 수집은 하지 않는다.
- 업그레이드 경로 비교(`/paths`): 구매(관측 매물 그대로, 세트 효과 변화 반영)·직작(매물가 + 메소 재설정 평균)·지금 템 큐브를 억당 실딜로 정렬.
- 데몬어벤져는 아직 "계산 제외"(API가 HP를 표시 상한으로만 준다).
- 추옵(환불) 확률표가 없어 직작 비용에 추옵은 포함하지 않는다.
