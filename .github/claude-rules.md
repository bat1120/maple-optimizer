작업 규칙(클라우드 Claude):
- 모든 설명·이슈 댓글·커밋 메시지는 한국어로 쓴다. 코드·식별자·명령어만 원문.
- 코드를 바꾸면 커밋 전에 `uv run pytest -q --ignore=tests/goals`와 `npm --prefix web test`를 돌려 둘 다 통과해야 한다. 실패하면 커밋하지 않고 이유를 남긴다.
- 기능 추가·버그 수정은 실패하는 테스트를 먼저 쓰고 실패를 확인한 뒤 구현한다.
- 설계·계획 문서와 목표 기록(GOALS.md·goal-log.md·tests/goals)은 GitHub에 없다(사용자 PC에만). 필요하면 사용자에게 묻는다.
- main에 커밋하고 푸시한다. 커밋 메시지 끝에 빈 줄 다음 `Co-Authored-By: Claude <noreply@anthropic.com>`.
- 금지: .env·비밀값 출력이나 커밋, 사람 몫(H*) 목표 수행, 넥슨·경매장 자동 수집이나 자동화 차단 우회, 숫자 추정(측정·관측값만 쓴다), 다른 저장소 수정.
