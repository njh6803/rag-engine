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

**Status:** ready-for-agent

- [ ] 병합 직전에 01과 02의 `Status:`가 done이고 `git log origin/main`에 병합됐는지 봤다. 아직이면 병합하지 않고 기다리거나, 끊을 때 지시문의 "확인할 선행 조건"에 적었다
- [ ] 티켓 끝에 곳마다 `main`의 뜻을 가른 표가 있다
- [ ] `operations.md` "브랜치와 병합"이 기준 브랜치 규칙과 agent-os `CONTEXT.md`의 브랜치 모델 용어를 정의하고, "가드레일"이 보호 브랜치 둘을 적으며, 헌법 판이 올랐다
- [ ] `merge.md`에 병합 방법과 "되돌려 합치기"의 순서와 계기가 있고, `next-session` 결정표의 첫 줄이 되돌려 합칠 것이 남았는지 본다. "hotfix가 사라진다"는 옮기지 않았다
- [ ] 출시 PR을 여는 순서는 적지 않았고 05를 가리킨다
- [ ] CodeRabbit을 부른 리뷰가 base가 기본 브랜치가 아닌 PR에서 도는지의 확인 결과와 근거의 종류(원문을 읽었다, 어림)를 티켓 끝에 적었다
- [ ] 살아 있는 문서에서 기준 브랜치를 main으로 전제한 옛 표현의 잔존이 0이다(`CLAUDE.md` 작업 규약 4의 grep. 기록과 일지 인용은 뺀다). 설계 세션이 본 예는 `docs/agents/issue-tracker.md`의 "main에 들어가는 PR", `docs/constitution/operations.md`의 "최신 main 위에서", `tests/test_plan_status.py` 머리 독스트링의 strict 문장이다. 찾는 말은 `main에`, `main으로`, `main 위`, `origin/main`, `strict`이고, 운영 브랜치를 뜻하는 main은 남긴다
- [ ] 바꾼 스킬은 새 세션에서 불러 보았다(작업 규약 3)
- [ ] 검사 넷이 초록이다
