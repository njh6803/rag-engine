# rag-engine 헌법 · 검증과 운영

커밋, 병합, 리뷰, 트래커, 가드레일을 만질 때 읽는다.

## 검증
- 손으로 치는 검증 명령(테스트, 린트, 타입체크)은 `CLAUDE.md`의 검증 명령 칸이 원천이다. 티켓의 "검사 N이 초록"은 손으로 치는 것을 말한다.
- 계약 시험은 첫날부터 CI에 둔다. 공식 MCP SDK의 클라이언트로 서버에 HTTP 접속해 도구 목록과 검색 도구의 형식을 본다. core가 검색 도구를 만들기 전에는 빈 서버의 `/health`와, MCP 도구 목록에 쓰기 도구가 없음을 본다(원칙 IV).
- 컨테이너 이미지는 첫날부터 CI에서 짓는다. 판 태그를 붙여 내는 것은 release-image다.
- 검색 품질은 search-eval이 서면 평가 세트의 적중률이 기준치 아래로 떨어질 때 CI가 실패한다. LLM을 부르는 시험은 두지 않는다(이 서버는 답을 만들지 않는다).
- 대상 사양에서 재야 하는 값(동시 요청의 검색 지연, 첫 대량 적재 시간)은 프로브로 남긴다. 자리와 근거 문장의 규칙은 `docs/agents/issue-tracker.md`의 프로브와 근거 절이다.

## 가드레일
- pre-commit이 커밋마다 린트, 포맷, 검사 러너(타입체크, 타입 우회 검사, 테스트, 지침 검사, 커밋 검사)를 돌고, CI가 같은 검사를 PR마다 돈다. 훅과 검사의 목록과 등록은 `.claude/settings.json`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`이 원천이다.
- 반드시 실행되어야 하는 것은 문서가 아니라 훅이나 검사로 둔다(`CLAUDE.md` 교정 루프).

## 브랜치와 병합
- main에 바로 커밋하지 않는다. main은 보호되고 필수 검사는 `verify`이며 최신 main 위에서 돌아야 병합된다(strict).
- PR마다 티켓 하나다. 티켓, 브랜치 이름, 면제 PR의 규약은 `docs/agents/issue-tracker.md`가 원천이고, 커밋 검사(`tools/check_ticket.py`)가 판정한다.
- 병합은 스쿼시 병합이고 `/git-pr-merge`로 한다. PR은 `/git-pr`이 `.github/PULL_REQUEST_TEMPLATE.md`를 채워 연다.

## 리뷰 파이프라인
- 커밋 전: `/code-review`로 셀프 리뷰하고 Critical과 Major를 고친다. 판단 기준은 `CODING_STANDARDS.md`다.
- PR 직전: CodeRabbit CLI로 한 번 더 본다(`.claude/agents/coderabbit-review.md`). CLI가 못 돌면 `.claude/agents/bug-perf-review.md`가 같은 축을 본다.
- PR: 공개 저장소이므로 CodeRabbit PR 리뷰와 Claude Code Review 워크플로가 함께 돈다.
- 초록 착시: 봇이 코멘트 없이 초록이면 리뷰가 돈 것으로 보지 않고 실행 로그를 읽는다.
- 실측(PR #1~#3, 2026-11-09~10). 첫 PR은 #1이다. CodeRabbit 좌석은 없다(CLI가 `Seat: not assigned`를 찍고도 `review_completed`로 끝났다). 별 10개 미만의 공개 저장소라 PR을 열면 CodeRabbit이 요약 코멘트만 바로 달고 리뷰는 자동으로 돌지 않으며(`This repository does not receive automatic reviews because it has fewer than 10 stars`), `@coderabbitai review` 코멘트로 불러야 돈다. 포함 한도는 시간당 리뷰 1회이고(`1 included review per hour`) 같은 시간 안의 둘째 호출은 `Review rate limited`다. 불러서 리뷰가 달리기까지 12~15분 걸렸다(#2, #3). Claude Code Review 워크플로는 푸시마다 코멘트 하나를 단다(#1, #2 각 둘).

## 이슈
- 이슈 트래커는 로컬 마크다운(`.scratch/`)이고 규약은 `docs/agents/issue-tracker.md`다. 전체 계획 `.scratch/plan.md`는 생성 파일이다.

## 설치처 정보
- 설치처의 정보(주소, 계정, 연결 정보, 설치처별 변환 플러그인)는 이 저장소에 넣지 않고 설치처의 비공개 저장소에 둔다(ADR 0003). 이 저장소의 표본 문서와 평가 세트는 공개 문서 묶음으로만 만든다.
- 비밀 값은 `.env`나 설치 환경의 비밀 저장소에만 둔다. `.env`에는 개발용 값만 두고 커밋하지 않는다.

## 문서 위치
- 킥오프의 입력(계획 제안)은 `.scratch/kickoff-input.md`다. 각 행의 설계 인터뷰가 그 문서에서 쓸 절(2·4·5·7·8절)을 읽고, 정한 것은 ADR, 용어집, 그 기능의 디렉터리에 둔다.
- ADR의 본문은 살아 있는 문서다. 개정은 그 ADR의 `## 이력`에 쌓는다.
