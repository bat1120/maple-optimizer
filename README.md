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
| (배포 후) 같은 키 | VM의 `.env` | `docker compose`가 읽는다 (H1) |
| (배포 후) SSH 키·레지스트리 토큰 | GitHub Actions Secrets | 쓰기 전용 — 한 번 넣으면 다시 읽을 수 없다 (H3) |

저장소에는 `.env.example`만 있다. 키 값을 채팅·이슈·로그에 붙이지 않는다.

## 테스트와 게이트

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate.ps1          # 회귀 스위트 (pytest + vitest)
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1 -Goal G5   # 목표별 판정
```

- `tests/fixtures/`는 익명화한 실제 넥슨 응답이다(2026-10-02~03). 넥슨 약관상 수집 데이터는 30일 안에 갱신해야 하므로 서비스 데이터로 쓰지 않는다. 다시 받으려면 `.raw/`에 넣고 `uv run python tools/build_fixtures.py`.
- 세트 매핑 데이터 재생성: `uv run --group analysis python tools/derive_set_data.py`

## 데이터 출처와 한계

- 스타포스 확률: 공식 패치노트(2025-03-20, 2026-03-19) 기준. 비용 공식은 비공식(나무위키). 잠재 재설정 가격은 레전드리 200제 4,500만만 인게임 확인, 나머지는 나무위키 — `engine/data/*.json`의 `_verified` 참고.
- 넥슨 API에 경매장이 없어 매물은 직접 입력한다.
- 데몬어벤져는 아직 "계산 제외"(API가 HP를 표시 상한으로만 준다).
- 추옵(환불) 확률표가 없어 직작 비용에 추옵은 포함하지 않는다.
