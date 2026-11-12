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
- 보호 브랜치는 둘이다. main(설정은 `tools/protection.json`)은 필수 검사 `verify`, 최신 main 기준(strict), 강제 푸시와 삭제 금지를 건다. dev(티켓 `04-dev-branch-create`가 만드는 `tools/protection-dev.json`)는 같되 strict가 아니다. 두 브랜치 모두 선형 이력을 강제하지 않는다. 출시 PR과 되돌려 합치기 PR이 merge 커밋이기 때문이다. dev가 strict가 아닌 것은, strict이면 dev에 main에 없는 커밋이 있는 동안 머리가 main인 되돌려 합치기 PR이 늘 뒤처진 것으로 막히기 때문이다. 값은 ADR 0016이 정했고, 실제 설정은 티켓 `04-dev-branch-create`가 사용자의 승인을 다시 받고 바꾼다. 그 티켓이 병합되기 전에는 dev가 없고 main에 선형 이력 강제가 남아 있다.

## 브랜치와 병합
브랜치 모델은 agent-os의 ADR 0043을 따르고, 이 저장소에서 다른 것은 ADR 0016이 적는다. 용어는 `GLOSSARY.md`가 제품의 말만 들기 때문에 이 절이 정의한다(ADR 0016).
- **용어.** 티켓 PR은 티켓 하나를 가리키는 PR로, 기준 브랜치로 가서 커밋 하나로 합쳐진다. 운영 브랜치는 운영에 내보낼 수 있는 머리를 지키는 `main`이고 출시 PR과 핫픽스로만 바뀐다. 개발 브랜치는 티켓 PR이 모이는 `dev`이고 운영 브랜치보다 앞서 있다. 기준 브랜치는 브랜치 하나가 PR로 갈 브랜치다. 루트 브랜치는 주 체크아웃이 따르는 브랜치다. 출시 PR은 개발 브랜치의 머리를 운영 브랜치로 올리는 PR로 티켓을 가리키지 않고 커밋을 그대로 올린다. 핫픽스는 운영에서 발견된 버그를 `main`에서 따서 `main`으로 바로 돌려보내는 티켓 PR이다. 되돌려 합치기는 운영 브랜치에 먼저 오른 변경을 개발 브랜치에 합치는 것으로, 핫픽스나 출시 PR을 병합한 세션이 바로 한다.
- **기준 브랜치 규칙.** `hotfix/*`는 `origin/main`이고, 그 밖(`feature/*`, `chore/*`, `docs/*`와 앱이 만든 이름)은 이 클론에 `origin/dev`의 추적 ref가 있으면 `origin/dev`, 없으면 `origin/main`이다. 원격에 dev가 있어도 이 클론이 받은 적이 없으면 없는 것이므로 `git fetch origin`을 먼저 친다. 문서와 스킬의 `<기준 브랜치>`는 이 줄을 가리키고, 구현은 `tools/base_rule.py`다(`tools/check_ticket.py`의 `base_ref`와 `tools/hook_push_behind_main.py`의 `base_branch`가 같은 기준을 낸다). 루트 브랜치도 같은 규칙으로 dev가 있으면 dev, 없으면 main이다(`tidy-checkouts`). dev는 티켓 `04-dev-branch-create`가 딴다. 그때까지 모든 곳이 지금처럼 main이다.
- main과 dev에 바로 커밋하지 않는다. 두 브랜치는 보호된다(가드레일 절).
- PR마다 티켓 하나다. 티켓, 브랜치 이름, 면제 PR의 규약은 `docs/agents/issue-tracker.md`가 원천이고, 커밋 검사(`tools/check_ticket.py`)가 판정한다. 출시 PR(머리가 dev)과 되돌려 합치기 PR(머리가 main)은 티켓을 가리키지 않고 커밋 검사가 그대로 지난다.
- 티켓 PR과 핫픽스는 스쿼시 병합이고 출시 PR과 되돌려 합치기 PR은 merge 커밋이다. 병합 방법과 되돌려 합치는 순서는 `next-session` `merge.md`("병합 방법", "되돌려 합치기")가 원천이다. `/git-pr-merge`는 squash 병합과 main 갱신을 가정하므로 base가 main인 squash 병합(핫픽스 PR, dev가 생기기 전의 티켓 PR)에만 쓴다. base가 dev인 PR과 merge 커밋으로 병합하는 출시 PR은 사용자 수준 스킬이 dev와 merge 커밋을 가르치지 못해 `merge.md`의 "워크트리에서 병합할 때" 1~3으로 한다. PR은 `/git-pr`이 `.github/PULL_REQUEST_TEMPLATE.md`를 채워 연다. 그 스킬과 `gh pr create`는 base를 따로 주지 않으면 원격의 기본 브랜치로 잡으므로, 기본 브랜치가 dev가 된 뒤의 핫픽스 PR은 `gh pr create --base main`으로 연다.
- 출시 PR을 여는 순서와 main의 strict는 티켓 `05-dev-release-pr-step`이 정한다. 그때까지 출시 PR은 열지 않는다.
- 나란히 도는 두 티켓 PR이 각자 초록으로 병합된 뒤 dev가 빨개질 수 있다. dev에는 strict가 없기 때문이다. 늦게 병합하는 세션은 병합 직전에 `git fetch origin` 뒤 기준 브랜치를 합치고 저장소 상태 시험을 직접 돈다(`tests/test_plan_status.py` 머리 독스트링).

## 리뷰 파이프라인
- 커밋 전: `/code-review`로 셀프 리뷰하고 Critical과 Major를 고친다. 판단 기준은 `CODING_STANDARDS.md`다.
- PR 직전: CodeRabbit CLI로 한 번 더 본다(`.claude/agents/coderabbit-review.md`). CLI가 못 돌면 `.claude/agents/bug-perf-review.md`가 같은 축을 본다.
- PR: 공개 저장소이므로 CodeRabbit PR 리뷰와 Claude Code Review 워크플로가 함께 돈다. base 브랜치에 따른 차이는 아래 `/security-review`, 리뷰 봇, CodeRabbit 세 줄이 적는다.
- 내장 `/security-review`의 범위는 `origin/HEAD`부터다. 그 명령의 프롬프트가 커밋 목록과 diff를 `origin/HEAD...`로 채운다는 것은 agent-os가 2026-10에 `claude` 실행 파일에서 읽은 내용을 옮긴 것이고, 이 저장소에서 재 보지 않았다. `origin/HEAD`는 원격의 기본 브랜치를 가리키는 클론마다의 ref라, 기본 브랜치를 dev로 옮기면(티켓 `04-dev-branch-create`) 각 클론에서 `git remote set-head origin dev`를 쳐야 바뀐다. 기준 브랜치가 dev인 브랜치에서는 그 범위가 맞다. 기준 브랜치가 main인 핫픽스 브랜치에서는 커밋 목록에 main에 없는 dev의 커밋이 들어갈 것으로 보이므로(diff는 merge-base부터라 들지 않을 것이다. 프롬프트를 읽고 내린 추정이고 핫픽스로는 돌려 보지 않았다) 리뷰에 넘길 범위를 `git merge-base origin/main HEAD` 이후로 손으로 좁힌다.
- 리뷰 봇과 기준 브랜치(티켓 `02-dev-review-bot-off`와 `03-dev-base-skills-docs`가 적었다). Claude Code Review 워크플로는 머리가 dev이고 base가 main인 출시 PR을 건너뛴다. 그 PR의 내용은 모두 티켓 PR마다 리뷰를 받았기 때문이다. 되돌려 합치기 PR(머리 main, base dev)은 건너뛰지 않고 돈다. 충돌을 푼 줄은 그 PR에서 처음 생기는 코드라 리뷰가 필요하기 때문이다. 기본 브랜치가 dev인 동안 dev의 `claude-code-review.yml`이 아직 출시되지 않았으면, base가 main인 핫픽스 PR의 Claude Code Review가 액션의 워크플로 검증으로 건너뛰어져 코멘트 0개 가드가 빨개질 수 있다. 이것은 알려진 빨강이다. 필수 검사가 아니라 병합을 막지 않고, 그 PR의 리뷰는 PR 직전 리뷰와 셀프 리뷰가 대신한다. 이 갈래는 액션 소스의 오류 코드와 안내 문구에서 읽은 추론이고 서버 쪽 비교는 보지 못했으며, 첫 핫픽스 PR에서 처음 본다.
- CodeRabbit과 기준 브랜치. 자동 리뷰는 기본적으로 기본 브랜치를 base로 둔 PR만 본다. `reviews.auto_review.base_branches`가 다른 base를 더하고, 기본 브랜치는 늘 든다. 수동 호출은 자동 리뷰 설정과 상관없이 언제나 된다고 문서가 적는다(공식 문서 `docs.coderabbit.ai/configuration/auto-review.md`를 2026-11-12에 `curl`로 내려받아 읽었다). 이 저장소는 별이 10개 미만(2026-11-12에 `gh repo view`가 0개)이라 자동 리뷰가 어느 PR에도 돌지 않고 `@coderabbitai review`로 불러야 돈다(아래 실측). 그래서 base가 기본 브랜치가 아닌 PR(기본 브랜치가 dev가 된 뒤의 핫픽스 PR과 출시 PR)에서도 부르면 돈다고 본다. 이 결론은 문서가 base를 따로 가르지 않아 읽어 끌어낸 어림이고 그런 PR에서 불러 재 보지 않았다. 첫 핫픽스 PR에서 볼 일이다. 별이 10개를 넘겨 자동 리뷰가 열리면 `.coderabbit.yaml`의 `auto_review.base_branches`에 `main`이 필요한지 그때 다시 정한다. 기본 브랜치 dev는 늘 들어 있으므로 티켓 PR은 그대로 자동 리뷰를 받는다.
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
