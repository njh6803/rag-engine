# 03: 스킬과 규약 문서를 기준 브랜치 규칙에 맞추고 되돌려 합치는 순서를 적는다

**What to build:** agent-os 티켓 4(`dev-base-skills-docs`, #537)가 그 저장소의 스킬과 규약 문서에 한 변경과, 티켓 5(`dev-branch-create`, #541)가 보호 설정을 정한 뒤 고친 문장(결과 4 "닫을 때 할 일")을 이 저장소의 판에 손으로 맞춘다. 이 저장소의 스킬과 문서는 agent-os 판에서 고친 곳이 많아 diff를 그대로 얹지 않는다. 원격 설정은 이미 ADR 0016이 정했으므로(기본 브랜치 dev, dev는 strict 없음, main은 선형 이력 강제 없음) 그 값으로 쓴다.

- 스킬: `next-session`(`SKILL.md`, `merge.md`, `directive.md`), `tidy-checkouts`, `code-review`, `open-session`, `retro`, `implement`. 곳마다 `main`이 기준 브랜치인지(바꾼다), 운영 브랜치인지(그대로 둔다), 루트 브랜치인지(주 체크아웃이 따르는 브랜치. `origin/dev`가 있으면 dev)를 가른다. agent-os 티켓 4 결과 1의 표가 출발점이다. 이 저장소에 없는 스킬(`sync-design-system`)은 뺀다.
- `merge.md`: 병합 방법(티켓 PR과 핫픽스는 squash, 출시 PR과 되돌려 합치기 PR은 merge 커밋)과 "되돌려 합치기"(머리 `main`, base `dev`인 PR. 계기는 `merge.md`의 병합 길과 `next-session` 결정표의 첫 줄, agent-os 티켓 4 결과 2)를 적는다. agent-os ADR 0043의 "잊으면 다음 dev→main에서 hotfix가 사라진다"는 옮기지 않는다. agent-os의 `merge.md`가 고친 대로 같은 곳을 고쳤으면 충돌할 수 있다고 적는다. base가 dev인 PR과 출시 PR은 사용자 수준 `/git-pr-merge`를 쓰지 않고 "워크트리에서 병합할 때"의 길로 병합한다(사용자 수준 스킬은 저장소 밖이라 고치지 않는다).
- 출시 PR을 여는 순서는 적지 않는다(05). 그때까지 출시 PR은 열지 않는다고만 적는다.
- 문서: `CLAUDE.md`의 환경 함정, `docs/constitution/operations.md`의 "브랜치와 병합"(기준 브랜치 규칙과, agent-os `CONTEXT.md`가 정의한 브랜치 모델의 용어 티켓 PR·운영 브랜치·개발 브랜치·기준 브랜치·루트 브랜치·출시 PR·핫픽스·되돌려 합치기의 정의. ADR 0016 "용어는 `GLOSSARY.md`가 아니라 운영 문서에 둔다"), "가드레일"(보호 브랜치 둘과 그 설정 파일), "리뷰 파이프라인"(`/security-review`의 `origin/HEAD`, 핫픽스 PR은 `gh pr create --base main`), `docs/agents/issue-tracker.md`(규약 첫 항목의 "main에 들어가는 PR"), `tests/test_plan_status.py`의 머리 독스트링(나란히 돈 마지막 티켓 둘이 main의 strict로 막힌다는 문장. dev에는 strict가 없어 늦게 병합하는 세션이 dev를 합쳐 직접 시험을 돈다), `.github/PULL_REQUEST_TEMPLATE.md`, `.claude/agents/bug-perf-review.md`, `.claude/rules/adr.md`. `.claude/rules/adr.md`의 둘째 항목에 있는 "ADR 0016이 0010의 의존 방향을 바꿨다"는 agent-os의 번호인데, 이 저장소에도 ADR 0016이 생겨 이 저장소의 것으로 읽힌다. agent-os의 번호임을 밝힌다(설계 PR은 이 파일이 면제 모양이 아니라 고치지 못했다).
- 헌법 판: 운영 문서를 바꾸므로 `docs/constitution/README.md`의 판을 올리고 `tools/check_constitution_version.py`가 통과한다. ADR 0016이 그 개정의 근거다.
- CodeRabbit(ADR 0016 Consequences "리뷰 봇 두 갈래"의 뒤의 것): 이 저장소는 별이 10개 미만이라 자동 리뷰가 어느 PR에도 돌지 않고 `@coderabbitai review`로 불러야 돈다(운영 문서 "리뷰 파이프라인"의 2026-11-09~10 실측. 별 수가 바뀌었을 수 있으니 다시 본다). 그래서 확인할 것은 부른 리뷰가 base가 기본 브랜치가 아닌 PR(기본 브랜치가 dev가 된 뒤의 핫픽스 PR과 출시 PR)에서도 도는지다. 공식 문서 원문으로 확인하거나, 확인하지 못하면 어림으로 적고 첫 핫픽스 PR에서 볼 일로 운영 문서에 남긴다. 자동 리뷰가 열리면 `.coderabbit.yaml`의 `auto_review.base_branches`가 필요한지도 함께 적는다.
- 02가 넘긴 것(리뷰 봇이 main을 머리로 둔 PR에서 건너뛰는 갈래를 알려진 빨강으로 두기로 했으면 그 사실)을 운영 문서에 적는다. 그래서 이 티켓은 02가 병합된 뒤에 병합한다.

**Blocked by:** 없음 (01·02와 나란히 돌되, 01과 02가 병합된 뒤에 병합한다. 문서가 가리키는 도구가 main에 있어야 하고, 02가 넘긴 것을 적어야 하기 때문이다)

**Status:** done

- [x] 병합 직전에 01과 02의 `Status:`가 done이고 `git log origin/main`에 병합됐는지 봤다. 아직이면 병합하지 않고 기다리거나, 끊을 때 지시문의 "확인할 선행 조건"에 적었다 (2026-11-12 `git fetch origin` 뒤 `git log origin/main`에 02는 PR #24로 병합됐고 01은 없다. 01을 병합하기 전에는 이 PR을 병합하지 않고 다음 지시문의 "확인할 선행 조건"에 적는다)
- [x] 티켓 끝에 곳마다 `main`의 뜻을 가른 표가 있다
- [x] `operations.md` "브랜치와 병합"이 기준 브랜치 규칙과 agent-os `CONTEXT.md`의 브랜치 모델 용어를 정의하고, "가드레일"이 보호 브랜치 둘을 적으며, 헌법 판이 올랐다
- [x] `merge.md`에 병합 방법과 "되돌려 합치기"의 순서와 계기가 있고, `next-session` 결정표의 첫 줄이 되돌려 합칠 것이 남았는지 본다. "hotfix가 사라진다"는 옮기지 않았다
- [x] 출시 PR을 여는 순서는 적지 않았고 05를 가리킨다
- [x] CodeRabbit을 부른 리뷰가 base가 기본 브랜치가 아닌 PR에서 도는지의 확인 결과와 근거의 종류(원문을 읽었다, 어림)를 티켓 끝에 적었다
- [x] 02가 넘긴 결정과 위 CodeRabbit 확인 결과로 ADR 0016 Consequences "리뷰 봇 두 갈래"의 추론·확인할 것 문장을 고쳤고, ADR의 `## 이력`(없으면 만든다)에 날짜와 티켓을 적었다. 02의 PR은 기록 밖의 파일을 실을 수 없어 이 몫이 03에 있다 (본문 문장은 `.claude/rules/adr.md`대로 두고 포인터와 `## 이력`으로 적었다)
- [x] 살아 있는 문서에서 기준 브랜치를 main으로 전제한 옛 표현의 잔존이 0이다(`CLAUDE.md` 작업 규약 4의 grep. 기록과 일지 인용은 뺀다). 설계 세션이 본 예는 `docs/agents/issue-tracker.md`의 "main에 들어가는 PR", `docs/constitution/operations.md`의 "최신 main 위에서", `tests/test_plan_status.py` 머리 독스트링의 strict 문장이다. 찾는 말은 `main에`, `main으로`, `main 위`, `origin/main`, `strict`이고, 운영 브랜치를 뜻하는 main은 남긴다
- [x] 바꾼 스킬은 새 세션에서 불러 보았다(작업 규약 3)
- [x] 검사 넷이 초록이다
- [x] 회고 반영: 새 대기열 항목 `adr-body-rewrite-vs-pointer`(1회차)를 적었고 이 세션에서는 반영하지 않았다, 일지 `2026-11-12-1837-dev-base-skills-docs.md`

## 결과

### 1. 곳마다 `main`의 뜻을 가른 표

출발점은 agent-os 티켓 4(`dev-base-skills-docs`) 결과 1의 표와, 그 PR(#537)과 #541이 고친 스킬·문서의 diff다. 파일마다 `git merge-file`로 3-way를 시도했으나 이 저장소의 사본이 달라(킥오프에서 뺀 대목, 대기열·일지 번호) 충돌이 났고, 충돌이 없던 파일도 문장을 하나씩 읽어 이 저장소의 사실로 손으로 맞췄다. 기준 브랜치는 `docs/constitution/operations.md` "브랜치와 병합"이 원천이고, 루트 브랜치(주 체크아웃이 따르는 브랜치)는 `tidy-checkouts`가 정한다. 판은 "바꾼다"(기준 브랜치나 루트 브랜치로), "그대로"(운영 브랜치이거나 main이 브랜치 이름이 아니다), "문장 더함"이다.

| 곳 | `main`의 뜻 | 판 |
|---|---|---|
| `next-session/SKILL.md` 형제 설명(`sibling_overlap`이 보는 것) | 병합처(기준 브랜치) | 바꾼다 |
| `next-session/SKILL.md` 칩(`spawn_task`) | 기본 브랜치 = 운영 브랜치. 칩은 거기서 뜨고 티켓 PR은 dev로 병합된다 | 문장을 바꾼다(`origin/<기준 브랜치>`를 받아 그 위에서 시작하게 한다) |
| `next-session/SKILL.md` 대기열 도구의 `--ref` | 병합처 | 바꾼다 |
| `next-session/SKILL.md` 결정표 | — | 첫 줄을 더한다(되돌려 합칠 것이 남았는가) |
| `next-session/directive.md` 1(티켓 이름 겹침), 3(캐시가 되는 예) | 기준 브랜치 | 바꾼다 |
| `next-session/directive.md` 5(워크트리 문장 조건) | 루트 브랜치 | 바꾼다 |
| `next-session/directive.md` 6(주 체크아웃 미갱신) | 병합 대상이 dev냐 main이냐에 따라 새 세션이 낡은 정도가 다르다 | 둘을 가른 문장을 더한다 |
| `next-session/merge.md` 병합 길(4) | 둘 다(base가 dev인 PR은 `/git-pr-merge`를 쓰지 않는다) | 문장을 더하고 "병합 방법" 표를 신설한다 |
| `next-session/merge.md` "워크트리에서 병합할 때" 머리말·1·2·3·5 | base(PR 종류마다 main이나 dev) | 바꾼다 |
| `next-session/merge.md` "되돌려 합치기" | main→dev | 신설한다 |
| `next-session/merge.md` 병합 길의 `/git-pr-merge`가 main을 가로챈다는 문장 | 사용자 수준 스킬이 박은 main | 그대로 |
| `tidy-checkouts/SKILL.md` 설명·머리말·2·끝·하지 않는 것 | 루트 브랜치 | 바꾼다. 루트 브랜치 정의를 더한다 |
| `tidy-checkouts/SKILL.md` 3의 병합 판정(`origin/main`에 닿는지) | 병합처 | 그대로 두고 문장을 더한다. 병합처를 몇 개로 보는지는 도구 독스트링이 원천(01) |
| `code-review/SKILL.md` 고정점 예와 이유 | 예시 ref | 바꾼다. 셀프 리뷰의 고정점이 기준 브랜치임을 더한다 |
| `open-session/SKILL.md` 1(루트가 `[main]`이 아니다), 6(`origin/main`에서 따기) | 루트 브랜치, 기준 브랜치 | 바꾼다 |
| `retro/SKILL.md` 손상 정의 | 둘 다 | "main이나 dev"로 바꾼다 |
| `retro/SKILL.md` 만료의 `--ref origin/main` | 병합처 | 바꾼다 |
| `implement/SKILL.md` 11행(주 체크아웃이 main도 이 티켓의 브랜치도 아닐 때) | 루트 브랜치 | 바꾼다 |
| `.claude/agents/bug-perf-review.md` 범위 잡기 | 기준 | 바꾼다 |
| `.claude/agents/spec-reviewer.md` 32행 | 티켓 일부만 병합된 통합 브랜치 | 바꾼다(티켓이 이름으로 들지 않은 같은 종류의 잔존) |
| `.claude/rules/adr.md` 17행(`git diff --merge-base origin/main`, "main에 이미 있던 같은 번호") | 병합처 | 바꾼다 |
| `.claude/rules/adr.md` 둘째 항목의 "ADR 0016이 0010의 의존 방향을 바꿨다" | agent-os의 ADR 번호 | agent-os의 것임을 밝힌다(이 저장소의 ADR 0016은 브랜치 모델) |
| `.github/PULL_REQUEST_TEMPLATE.md` `/security-review` 줄 | 병합처 | 바꾼다 |
| `.github/PULL_REQUEST_TEMPLATE.md` `.github/` 줄의 `claude-code-review.yml` 별도 PR | 파일 이름 | 그대로 |
| `CLAUDE.md` 환경 함정(커밋 전 브랜치 확인) | 운영 브랜치(훅이 막는 곳), 병합처 | main과 dev로, 기준 브랜치 규칙을 한 문장 더한다 |
| `CLAUDE.md` 교정 루프의 손상 정의 | 둘 다 | "main이나 dev"로 바꾼다 |
| `docs/constitution/operations.md` 브랜치와 병합 | 기준 브랜치 | 용어 여덟(agent-os `CONTEXT.md`의 브랜치 모델)과 규칙을 신설하고 병합 방법과 `--base main`을 적는다 |
| `docs/constitution/operations.md` 가드레일 | main 보호 설정 | 보호 브랜치 둘과 설정 파일(`tools/protection.json`, `tools/protection-dev.json`)을 적는다 |
| `docs/constitution/operations.md` 리뷰 파이프라인 | `/security-review`의 `origin/HEAD`, 리뷰 봇의 기본 브랜치 비교, CodeRabbit의 base | 문장을 더한다(02가 넘긴 것과 CodeRabbit 확인 결과) |
| `docs/constitution/operations.md` 리뷰 파이프라인의 실측(PR #1~#3) | 기록 | 그대로 |
| `docs/agents/issue-tracker.md` 규약 첫 항목 | 기준 브랜치와 병합처 | 바꾼다. 출시 PR과 되돌려 합치기 PR은 티켓을 가리키지 않는다 |
| `tests/test_plan_status.py` 머리 독스트링 | 병합처 | 바꾼다. dev에는 strict가 없어 늦게 병합하는 세션이 직접 시험을 돈다 |
| ADR 0016 | Consequences "리뷰 봇 두 갈래" | 본문 문장은 그대로 두고 끝에 `(바뀜: 이력 …)` 포인터를 달았으며, 02의 결정과 CodeRabbit 문서 확인은 `## 이력`을 만들어 적었다(`.claude/rules/adr.md`는 본문의 다른 글자를 고치지 않는다) |
| `GLOSSARY.md` | 제품의 말만 든다(ADR 0016) | 고치지 않는다 |
| `docs/constitution/README.md` | 판 | 1.1.2 → 1.2.0(절 추가: 브랜치 용어·기준 브랜치 규칙·보호 브랜치 둘·리뷰 봇 갈래) |

이 저장소에 없는 스킬 `sync-design-system`은 뺐다. `next-session/handoff.md`와 `writing-for-agents`는 `main`이 든 곳이 없거나 영어 낱말이라 건드리지 않았다.

### 2. 사용자 수준 스킬(저장소 밖, 고치지 않았다)

`~/.claude/skills/git-pr`, `git-pr-merge`, `git-pr-feedback`, `git-branch`는 agent-os 티켓 4가 읽어 목록으로 남긴 대로 기본 브랜치 감지가 실패하면 `main`으로 떨어지거나 병합 뒤 `main`으로 돌아가 당기는 박힘이 있다. 이 저장소는 base가 dev인 PR과 출시 PR에 `/git-pr-merge`를 쓰지 않는 길을 `merge.md`에 적었고, 핫픽스 PR은 `gh pr create --base main`으로 열게 했다. 기본 브랜치를 dev로 옮기면(04) `git-pr`의 base 감지와 `git-branch`의 브랜치 따기는 우회 없이 dev로 간다고 본다(agent-os 티켓의 읽기 결과에서 옮긴 어림이고 이 세션에서 그 파일을 다시 읽지 않았다). 고칠지는 사용자가 정한다.

### 3. CodeRabbit이 base가 기본 브랜치가 아닌 PR에서 도는지: 원문을 읽었고 결론은 어림이다

2026-11-12에 공식 문서 `https://docs.coderabbit.ai/configuration/auto-review.md`(13214바이트)를 `curl`로 내려받아 읽었다(웹 요약이 아니다). 근거 문장은 셋이다. 하나, `base_branches`의 기본값은 기본 브랜치만이다(11행과 28행). 둘, 기본 브랜치는 `base_branches`를 주어도 늘 든다(48행). 셋, 자동 리뷰 설정과 상관없이 `@coderabbitai review`나 `@coderabbitai full review` 댓글로 언제나 수동으로 리뷰를 부를 수 있다(15행). 별 수는 `gh repo view --json stargazerCount`가 0이라 10개 미만이다. 그래서 이 저장소는 자동 리뷰가 어느 PR에도 돌지 않고 수동 호출만 쓰므로, base가 기본 브랜치가 아닌 PR(기본 브랜치가 dev가 된 뒤의 핫픽스 PR과 출시 PR)에서도 부르면 돈다고 본다. 문서가 수동 호출이 base에 따라 달라지는지를 따로 말하지 않아 이 결론은 읽어 끌어낸 어림이고, 그런 PR에서 불러 재 보지 않았다. 첫 핫픽스 PR에서 볼 일이라 운영 문서 "리뷰 파이프라인"에 적었다. 자동 리뷰가 열리면(별 10개 이상) 기본 브랜치 dev는 늘 들어 있어 티켓 PR은 그대로 자동 리뷰를 받고, base가 main인 핫픽스 PR과 출시 PR은 `.coderabbit.yaml`의 `auto_review.base_branches`에 `main`을 더해야 자동으로 본다. 근거의 종류: 원문 확인(자동 리뷰의 범위와 수동 호출), 어림(수동 호출의 base 무관).

### 4. 02가 넘긴 것

02의 티켓 끝 "03에 넘긴다"대로 운영 문서 "리뷰 파이프라인"에 셋을 적었다. 출시 PR은 봇이 건너뛰고, 기본 브랜치가 dev인 동안 dev에서 `claude-code-review.yml`이 아직 출시되지 않았으면 base가 main인 핫픽스 PR이 액션의 워크플로 검증으로 건너뛰어져 가드가 빨개질 수 있으며(알려진 빨강, 필수 검사가 아니라 병합을 막지 않는다), 되돌려 합치기 PR은 봇이 돈다. 근거의 종류(액션 소스를 읽은 추론이고 서버 쪽 비교는 보지 못했다)도 그대로 적었다. ADR 0016 Consequences "리뷰 봇 두 갈래"에는 포인터를 달고 `## 이력`에 결과를 적었다. 02의 결정은 02 티켓 안의 "03에 넘긴다" 절에서 옮긴 것이고, 이 PR의 트리에는 02가 병합되기 전이라 그 결정이 없다. 그래서 이 PR은 02가 병합된 뒤에 병합한다(위 첫 체크박스).

### 5. 자기 리뷰에서 바로잡은 것

되돌려 합치기의 필요 판정을 `git diff`(내용)에서 `git merge-base --is-ancestor origin/main origin/dev`(커밋 포함)로 바꿨다. 출시 PR의 merge 커밋은 main에만 남고 main의 strict가 머리에 main의 끝을 요구해, 그 커밋이 dev에 없으면 다음 출시 PR이 뒤처졌다고 막히기 때문이다(agent-os 체크아웃의 `merge.md` 64·96·103행과 `SKILL.md` 49·50행이 같은 판정을 쓰는 것을 읽었다. 그 이유는 이 세션에서 위 strict 규칙으로 따져 적었다). 되돌려 합치기 PR의 `tools/wait_ci.py`가 `--expect`와 무관하게 CodeRabbit의 "Review skipped"를 요청되지 않은 리뷰로 세어 종료 4로 끝나므로, 그 종료를 예상한 끝으로 적었다.
