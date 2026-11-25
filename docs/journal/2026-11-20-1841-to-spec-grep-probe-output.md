# to-spec-grep-probe-output: `to-spec` 3단계에 쟀다고 적기 전의 출력 확인 문단을 더한다 · 2026-11-20

대기열 항목 `measured-claim-beyond-probe`(16회차)를 반영하는 harness 티켓의 기록이다(Sonnet 5.5, high). 티켓은 `.scratch/harness/issues/to-spec-grep-probe-output.md`, 브랜치는 `chore/to-spec-grep-probe-output`이다. 나란히 연 다섯 티켓 가운데 하나이고 대상 파일이 서로 겹치지 않는다. 계기, 한 것, 검증, 셀프 리뷰, 커밋, PR 직전 리뷰, 회고, 다음을 차례로 둔다. PR 봇 회차의 절은 PR을 연 뒤 이어 쓴다.

## 계기

next-session 지시문으로 연 새 세션이다. 요청 범위는 PR과 병합까지다. 주 체크아웃이 `origin/dev`보다 뒤처져 있어(로컬 dev `cdf3bc5`, 원격 `3cd84f5`) `tidy-checkouts`를 먼저 돌았고, 루트를 당긴 뒤 `EnterWorktree`로 새 워크트리에 들어가 브랜치 이름을 `chore/to-spec-grep-probe-output`으로 바꿨다. `uv run python tools/sibling_overlap.py`는 번호 겹침과 함께 고친 파일이 없다고 냈다.

## 한 것

- `.claude/skills/to-spec/SKILL.md` 3단계에 문단 하나를 더했다. "쟀다"("실측"도 같다)고 적기 전에 프로브의 커밋한 출력 파일에서 값을 Grep으로 글자로 찾아보고, 그 값이 사실을 보이는 줄에 있는지 본다. 계산한 값은 계산에 쓴 값들을 찾고 계산을 함께 적는다. 찾지 못하거나 프로브가 없으면 프로브를 고쳐 다시 돌리거나 그 명령과 함께 손으로 봤다·코드를 읽었다·어림으로 적는다. 규칙의 원천은 `docs/agents/issue-tracker.md`의 프로브와 근거 절이라고 가리킨다.
- 같은 파일 첫머리 `프로젝트 사본` 주석의 3단계 측정 규칙 항목 끝에 새 출처를 덧붙였다. 센티널 낱말과 여섯을 더했다는 수는 그대로다.
- 티켓을 썼고, 대기열 항목 `measured-claim-beyond-probe`를 닫았다. 닫힘 줄에 안 닿은 자리를 적었다.

## 검증

- `uv run python tools/check_instructions.py`: 출력 없이 통과. `uv run python tools/plan_table.py --check`: 통과(전체 계획은 바뀌지 않는다).
- 티켓에 든 사실 주장을 직접 대 봤다. `.scratch/**/probes` 아래에 `*_out.txt` 48개, `*.json` 41개, `report_*.txt` 6개, `*.tsv` 2개가 있다(`find`로 셌다. `report_diff_out.txt`처럼 두 꼴에 드는 파일이 있고, `*.json`에는 출력이 아닌 입력 설정도 든다). 그래서 새 문단은 출력 파일의 이름 꼴을 정하지 않는다. `hook_measure_word`와 `hook_probe_citing_doc`은 `tools/`에도 `.claude/settings.json`에도 없다(`ls`와 `grep`으로 0건을 확인했다).
- 전체 pytest와 나머지 검사는 커밋이 부르는 pre-commit의 검사 러너가 돈다.

## 셀프 리뷰

`code-review` 스킬로 기준 `3cd84f5`(`origin/dev` 끝)에서 수정 1개 파일, 미추적 1개(티켓), 커밋 0개를 두 축으로 봤다. 표준 축은 sonnet·high, 명세 축은 본 세션의 모델이다. Critical은 없었다. 사실 주장 오류가 Major 수준으로 둘 나왔다.

**고친 것.**
- 티켓이 이미 `hook_measure_word`와 `hook_probe_citing_doc`이 계기를 내는데도 났다고 적었으나, 이 저장소에 두 훅의 파일이 없다(표준 축이 짚었고 직접 확인했다). `.claude/rules/tools.md`와 대기열 항목 본문은 agent-os에서 옮겨 온 문장이다. 티켓의 해당 절을 훅이 이 저장소에 없다는 사실과 지침이 어겨진 뒤에만 훅을 더한다는 순서로 다시 썼다. 항목 본문은 기록이라 고치지 않았다.
- 티켓의 첫 문장이 명세에서만 열여섯 번 났다고 읽혔다. 항목의 회차 가운데 3·4·7~13·16회차가 독스트링, 프로브 README, 티켓 Comments, ADR 이력, 일지에서 났으므로 난 자리는 명세뿐이 아니라고 고치고, 처방이 닿는 곳이 `to-spec` 하나라는 것과 넓히기를 미루는 근거를 적었다. 이 줄은 PR 직전 리뷰가 다시 고쳤다(아래 PR 직전 리뷰 절).
- 새 문단이 `*_out.txt` 꼴을 관례처럼 적었다. 위 검증의 수대로 이름 꼴을 정하지 않고 커밋한 출력 파일이라고만 적었다.
- 새 문단에서 값은 Grep할 수 있으나 사실은 할 수 없다는 지적(두 축)에, 값이 사실을 보이는 줄에 있는지 본다는 말을 더했다. 평균이나 비율처럼 계산한 값과 프로브가 없는 문장은 갈래가 없다는 지적(두 축)에, 계산을 함께 적는 말과 다른 표기로 내려가는 말을 더했다. 손으로 봤다에는 그 명령과 함께를 붙였다(`docs/agents/issue-tracker.md` 26행).
- 센티널 주석이 괄호 속 대기열 번호는 agent-os의 기록이라고 하는데 새 인용은 이 저장소의 항목 이름이라 오독하기 쉬웠다. 인용 앞에 이 저장소 대기열의 라고 붙였다.
- 티켓의 체크박스가 문단이 그 절을 가리킨다고 적었으나 가리키는 곳이 앞 문단이었다. 새 문단 끝 문장에 가리키는 말을 넣고 체크박스도 그에 맞췄다.

**남긴 것과 이유.**
- 점검이 쟀다·실측에만 걸리고 재 보니·측정했다로 빠져나간다는 지적(표준 축). 낱말 목록은 닫힌 주장이 되어 새 반례를 부른다. 그 낱말을 근거로 적을 때 이 문단이 걸리는 것이 목적이고, 다른 낱말 문제는 issue-tracker의 일반 규칙이 맡는다.
- 이미 써 둔 문장을 압축 뒤에 다시 훑는 단계가 없다는 지적(표준 축). 명세를 쓴 뒤의 차례(셀프 리뷰, 서두의 수 세기, ADR 승인, 커밋)는 이 티켓이 바꾸지 않는다. 두 축의 리뷰가 그 확인을 맡는다.
- 출력 값이 둥글려졌거나 단위가 다르면 글자 Grep에 걸리지 않는다는 지적(표준 축). 계산한 값을 계산과 함께 적는 갈래가 그 경우도 덮는다고 보고 더 늘리지 않았다.
- 문단이 한 줄이 아니라는 지적(표준 축, 경미). 두 축이 짚은 구멍을 메우느라 한 줄에서 한 문단이 되었고, 티켓은 문단이라고 적었다.

## 커밋

커밋 `6a86256`(제목 "chore: 명세가 쟀다고 적기 전에 출력 파일을 찾아보게 한다 (harness to-spec-grep-probe-output)")이 첫 시도에서 들어갔다. pre-commit의 검사 러너가 11개 검사를 모두 통과시켰고(pytest 674초), 인용 대조는 경고가 없었다.

## PR 직전 리뷰

CodeRabbit CLI는 이 계정에서 쓰지 못해 `bug-perf-review`(밀 주장 다섯을 브리프에 넣었다)와 내장 `/security-review`로 갈음했다.

- `/security-review`: 발견 없음. 바뀐 파일이 모두 마크다운이고 실행되는 코드, 워크플로, 설정, 권한이 바뀌지 않았다.
- `bug-perf-review`: Critical·Major 없음, Minor 넷. 밀 주장 다섯은 모두 맞았다(출력 파일 수, 두 훅의 부재, 회차의 출처 자리, 절 이름과 26행의 종류, 셀프 리뷰 서술과 diff).

**고친 것.**
- 새 문단이 손으로 봤다·코드를 읽었다·어림 모두에 그 명령을 붙이게 읽혔다. `docs/agents/issue-tracker.md` 26행대로 손으로 봤다는 그 명령과, 코드를 읽었다는 파일과 판과 함께 적고, 재지 않은 값은 어림이라고 적도록 나눴다.
- 출력 파일이 커밋되지 않은 프로브(예: `.scratch/core/probes/jobs_active_index_plan.py`)를 다시 돌려 터미널에만 찍어도 문단을 지킨 것이 되었고, 프로브가 없을 때 새로 두라는 말이 없었다. 프로브를 새로 두거나 고쳐 다시 돌려 그 출력을 커밋한 뒤 그 파일에서 찾도록 고쳤다.
- 티켓과 대기열 닫힘 줄의 회차 열거가 항목 본문과 어긋났다. 본문은 2회차(프로브 README, 07 티켓)와 5회차(프로브 README, `rerank_throughput.py` 독스트링)도 명세 밖에서 났다고 적으므로 2~5·7~13·16회차로 고쳤다. 넓힐지를 반영하는 chore가 정한다는 말은 3회차에만 있고 4회차와 8회차는 넓힐 자리를 적은 쪽이라서, 인용을 고치고 `어디로`가 정한 한 곳만 하고 닫는 까닭을 티켓과 닫힘 줄에 적었다.
- 위 검증의 파일 수 서술이 꼴이 겹치는 것과 입력 설정이 든 것을 밝히지 않았다. 존재하는 꼴을 적는 문장으로 고쳤다.

**남긴 것과 이유.**
- 출력 성격의 파일이 이 꼴들 밖에도 있다는 참고(`fetch_raw*.txt`, `*_server_log.txt`, `report.md` 등). 새 문단이 이름 꼴을 정하지 않으므로 고칠 문장이 없다.
- `.claude/rules/tools.md`가 Write·Edit 훅으로 든 열 훅 가운데 파일이 있는 것은 셋뿐이라는 참고. 아래 회고 후보에 옮겼다.

## PR 봇 회차

PR 86을 연 뒤 첫 회차(머리 `e77c12c`)의 결과다. `tools/wait_ci.py 86`이 모든 검사가 통과했고 CodeRabbit이 끝났다고 냈다.

- claude-review: 지적 없음. 바뀐 것이 지침·기록 문서뿐이라 계약, 포트, MCP 도구, 플러그인 자리, 클라이언트 의존을 건드리지 않았다고 PR 코멘트에 적었다.
- CodeRabbit(`@coderabbitai review`로 요청): 인라인 지적과 리뷰 본문 없이 요약 코멘트만 달고 `Finished`로 끝났다.
- CI: `python`, `ticket`, `title`, `image`, `standalone`, `eval-fast`, `eval-full`, `verify`가 통과했다.
- 이 절을 적으려고 일지만 바꾼 커밋이 하나 더 들어가므로 머리가 바뀐다. 병합 전에 새 머리에서 CI를 다시 확인한다.

## 회고

후보 하나를 냈다.

- **계기 훅 이름이 옮겨 온 규칙과 항목에 남았지만 파일이 없다**(후보, 회차를 세지 않는다). 사건: `.claude/rules/tools.md`의 Write·Edit 훅 열 개 가운데 `tools/`에 파일이 있는 것은 `hook_journal_retro`, `hook_ruff_line_width`, `hook_line_separators` 셋뿐이다. 나머지 일곱(`hook_scratch_probe_rule`, `hook_probe_conclusion`, `hook_journal_evidence`, `hook_ui_design`, `hook_web_edit_check`, `hook_measure_word`, `hook_probe_citing_doc`)은 규칙 문장에만 남았다(`ls`로 셌다). 이 세션의 티켓이 그 가운데 둘을 있는 훅으로 믿고 근거로 들었고 표준 축이 잡았다. 고침은 이 티켓에서 했다(고침 하나는 사건 하나다). 규칙 파일의 훅 목록 전체를 이 저장소에 맞출지는 사용자가 정할 일이라 이 PR에서 하지 않았다. 같은 일이 되풀이되는지는 다음 사건에서 센다.

## 다음

- 이 티켓의 처방은 `to-spec`에만 닿는다. 코드 독스트링, 프로브 README, 티켓 Comments에서 같은 사건이 나면 17회차로 세고 넓힐지는 그때 retro가 정한다.
- 나란히 연 나머지 티켓 넷(`env-traps-crlf-and-utf8`, `mutate-show-marker-candidates`, `implement-journal-before-review`, `commit-title-hook-before-checks`)은 각자의 세션이 맡는다.
