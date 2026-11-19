# glossary-contract-version-review-bot: 리뷰 봇 지시문의 계약 번호 "판" 둘을 "계약 버전"으로 바꾼다 · 2026-11-19

PR 78(일지 `2026-11-19-1044-glossary-contract-version-names.md`)을 병합한 같은 세션이 그 일지의 "다음" 둘째 항목을 이어서 한 기록이다(Sonnet 5.5, high). 티켓은 `.scratch/harness/issues/glossary-contract-version-review-bot.md`, 브랜치는 `chore/glossary-contract-version-review-bot`이고, PR 78의 워크트리 `glossary-contract-version-names`에서 `origin/dev`(`fa85261`)로 브랜치를 새로 땄다. 용어집의 이름을 agent-os의 결정에 맞추는 일의 여덟째 PR이다. 계기, 한 것, 훑은 것, 검증, 셀프 리뷰, 커밋, PR 직전 리뷰, 회고, 다음을 차례로 둔다. PR 봇 회차의 절은 PR을 연 뒤 이어 쓴다.

## 계기

PR 78의 보고 끝에서 사용자에게 "리뷰 봇 지시문(yml) 후속 PR을 이 세션에서 이어서 낼까요?"를 물었고 사용자가 "네, 이어서"라고 답했다. 이 파일을 바꾼 PR은 같은 파일의 가드(`Fail when Claude left no comment` 스텝)가 일지·대기열·티켓·하네스 탐침 밖의 파일을 함께 실으면 실패시키므로 PR 78이 이 파일을 되돌리고 따로 PR로 남겼다. 이번 요청 범위는 PR과 병합까지다.

세션 카드(`start_session`의 `own_initiative`)로 이 일을 올리려 했으나 이 저장소의 훅이 모델이 스스로 내는 세션 카드를 막아(ADR 0037 "세션 카드"), 후속 일은 PR 78 일지의 "다음"에 적고 사용자에게 물어 이 세션에서 이어 갔다.

## 한 것

- `.github/workflows/claude-code-review.yml` 78행(리뷰 봇에게 주는 지시문의 3번 절차)의 계약 번호 "판" 둘을 바꿨다. "계약이 바뀌었는데 판, 계약 시험(tests/contract/), ADR, 명세가 같이 바뀌었는지"는 "계약이 바뀌었는데 계약 버전, …"으로, "계약의 판에서 앞자리를 올리는 변경"은 "계약 버전에서 앞자리를 올리는 변경"으로 바꿨다. 뒤의 구절은 `docs/constitution/operations.md` 39행의 "계약 버전에서 앞자리를 올리는 변경(원칙 VII)"과 같은 말이다. 규칙은 그대로이고 낱말만 바뀐다.
- 티켓 `.scratch/harness/issues/glossary-contract-version-review-bot.md`를 썼다.

## 훑은 것

PR 78 일지가 정한 훑기 모양(일치 지점의 앞뒤 글자, UTF-8, 양성 대조)을 지켰다. 스크래치패드의 스크립트 `sweep_pan.py`가 파일에서 "판"의 모든 자리를 앞뒤 30자와 함께 찍는다.

- 바꾸기 전: 8곳. 21행("판은 손으로 올린다". 외부 액션의 고정 방식), 75행·77행·78행 앞쪽·78행 뒤쪽의 "판단" 넷, 78행의 계약 번호 "판" 둘(338번째와 751번째 글자), 87행("판이 바뀌면". 외부 액션의 판). 양성 대조로 알려진 78행의 두 자리가 나왔다.
- 바꾼 뒤: 6곳. 모두 "판단"(75, 77, 78 둘)이거나 외부 액션의 판(21, 87)이다. 양성 대조 두 자리는 없어졌다.

## 검증

손으로 친 것은 파이프 없이 하나씩 쳤다.

- `uv run python tools/check_instructions.py`, `uv run python tools/plan_table.py --check`: 출력 없이 통과. `uv run ruff format --check .`: 772개 파일 이미 맞음.
- `uv run python tools/sibling_overlap.py`: 번호 겹침 없음, 함께 고친 파일 없음, 형제가 쓴 가장 높은 헌법 버전은 1.5.3(`origin/dev`)이고 이 브랜치는 헌법 파일을 고치지 않는다.
- 이 PR은 코드를 바꾸지 않으므로 전체 pytest와 `zizmor`, `run-hooks`는 커밋이 부르는 pre-commit의 검사 러너가 돈다.
- 첫 커밋 시도의 pre-commit에서 `zizmor`, `check-ticket`, `lint-imports`, `check-instructions`, `check-type-escapes`, `pyright`(두 환경), `run-hooks`는 통과했다. 전체 pytest는 4686건 중 1건이 실패했다: `tests/app/test_job_lease.py`의 `test_작업_담당_기록을_잃은_것이_드러나면_처리를_멈추고_문서에도_작업_행에도_쓰지_않는다`가 `assert time.monotonic() - started < 5`에서 5.2초(`739065.656 - 739060.437`)로 상한을 넘었다. 이 PR은 yml, 티켓, 대기열, 일지만 바꿔 그 시험의 코드 경로와 닿지 않고, 러너가 pytest를 11분 넘게 돌려 다른 프로세스와 겹친 부하에서 난 시간 시험 실패다. 부하 시간 시험 종류는 사용자가 2026-11-15에 닫힌 채 두기로 했으므로 새 사례는 일지에만 적고 다시 묻지 않는다. 같은 시험이 두 번 연속 실패하면 추측 수정을 멈추고 `diagnosing-bugs`를 쓴다는 규약에 따라, 다시 커밋해 같은 시험이 또 실패하는지 본다.

## 셀프 리뷰

`code-review` 스킬로 기준 `fa85261`(PR 78의 병합 커밋 = `origin/dev` 끝)에서 수정 1개 파일과 미추적 1개(티켓), 커밋 0개를 두 축으로 봤다(일지는 리뷰 시점에 아직 없었다). 표준 축은 sonnet·high, 명세 축은 본 세션의 모델로 돌렸다. Critical과 Major는 없었다.

**고친 것.**
- 티켓의 가드 줄 범위 "93~127행"이 부정확했다(표준 축, Minor). `Fail when Claude left no comment` 스텝은 93행에서 시작해 파일 끝(135행)까지이고, "이 파일을 바꾼 PR" 분기가 114~127행이다. 티켓을 93행에서 시작하는 스텝과 114~127행의 분기로 나눠 적도록 고쳤다. 앞 티켓(`glossary-contract-version-names.md`)과 PR 78 일지가 적은 "96~125행"은 그 PR의 기록이라 고치지 않는다.
- 티켓이 일지가 없던 시점에 수용 기준 둘째·다섯째를 `[x]`로 앞서 체크하고 있었다(두 축, Minor). 지금은 일지를 만들었으므로 둘째는 맞고, 넷째(`zizmor`·`run-hooks` 초록)와 다섯째(PR 직전 리뷰 결과)는 커밋과 PR 직전 리뷰를 거친 뒤에만 체크하도록 되돌렸다.
- 티켓이 "판단·판정"이라 적었으나 이 파일에 "판정"은 0건이었다(명세 축 참고). "판단"만 남기고 21행과 87행을 외부 액션의 판으로 적었다.
- 대기열 항목에 이어 쓴 문장이 계약 번호를 뜻하는 판이 살아 있는 글에서 모두 바뀌었다고 적었는데, 이는 닫힌 주장이라 표준 축이 짚은 `.scratch/release-image/spec.md` 같은 릴리스 영역의 글과 어긋난다. "릴리스 영역에 묶이지 않은 계약 번호의 판은"으로 좁히고 릴리스 영역에 묶인 글을 이름으로 적었다.

**남긴 것과 이유.**
- Duplicated Code(경미, 표준 축 냄새): 78행의 느낌표 기준 구절이 `operations.md` 39행과 같은 기준을 따로 적는다. 이번 변경은 두 글의 낱말을 맞추는 쪽이라 중복을 키우지 않고, 3번 절차가 "기준을 여기서 다시 정하지 않는다"고 한 것은 기준 자체를 가리키는 문장이라 판단 호출로 두었다.
- Mysterious Name(경미): "계약이 바뀌었는데 계약 버전, 계약 시험…"에서 "계약"이 세 번 겹쳐 무겁지만, "계약 버전"은 용어집의 이름이고 PR 서식도 같은 이름을 쓰므로 고치지 않는다.

**표준 축이 계약 번호 뜻으로 남았다고 짚은 곳(이번 범위 밖).** `tools/release.py`, `tests/tools/test_release.py`, `src/rag_engine/main.py`의 릴리스 노트 절 이름 "계약의 판"은 릴리스 영역의 몫이다. `.scratch/release-image/spec.md`와 `.scratch/search-eval/spec.md` 같은 명세는 릴리스 영역이거나 끝난 기능의 기록이다.

**다시 돌린 명령.** 위 "검증"에 있다. 전체 pytest는 커밋의 pre-commit이 돈다.

## 커밋

커밋 `38808363`(제목 "chore: 리뷰 봇 지시문의 판을 버전으로 (harness glossary-contract-version-review-bot)")은 두 번째 시도에서 들어갔다. 첫 시도는 위 "검증"의 시간 시험 한 건(5.2초)에서 pre-commit이 실패했고, 파일을 하나도 바꾸지 않고 다시 커밋하자 같은 시험이 지나갔다. 같은 시험이 두 번 연속 실패한 것이 아니므로 `diagnosing-bugs`는 쓰지 않았다. 두 번째 시도의 pre-commit에서 `zizmor`와 `run-hooks`를 포함한 검사가 모두 초록이어서 티켓의 넷째 수용 기준을 체크했다.

pre-commit의 인용 대조(`quotes` 훅)가 경고 다섯 건을 냈다. 훅은 막지 않고 알리기만 한다. 티켓 6·7행은 이번에 바꾼 옛 구절을 따옴표로 옮긴 것이라 저장소 어디에도 더는 글자 그대로 없고(바꾸기 전 문장을 보이려는 것이라 의도한 것이다), 이 일지의 사용자 질문 인용과 "93행에서 시작하는 스텝, 분기는 114~127행"은 요약해 옮긴 말이다. 따옴표를 떼지 않고 그대로 둔다. 원문 대조가 필요한 인용은 없다.

## PR 직전 리뷰

이 PR은 `.github/workflows/claude-code-review.yml`을 바꾸므로 PR 봇(claude-review)이 건너뛴다. 그래서 PR 직전 층 둘을 손으로 돌렸다. CodeRabbit CLI는 이 계정에서 거부되어 `bug-perf-review`와 `/security-review`로 갈음했다.

- `bug-perf-review`: 지적 0건. 바뀐 YAML이 문법상 유효하다는 것과, 이 일지와 티켓과 대기열에 적은 사실 주장 여섯(a~f)이 diff와 저장소에 맞는다는 것을 확인했다. 경계 메모로, `src/rag_engine/app/eval_report.py`의 `format_version`은 계약 번호가 아니라 평가 보고서 기록의 형식 번호라 이번 범위 밖이라는 점을 짚었다.
- `/security-review`: 발견 없음. diff를 보면 리뷰 봇 지시문의 낱말 둘만 바뀌었고 권한, 도구 허용 목록, 비밀 처리의 줄은 바뀌지 않았다.

## 회고

후보 셋을 냈고 승인 1, 기각 2, 넘김 0이다.

- **커밋 제목 길이 검사가 느린 검사 뒤에 돈다**(승인, 회차를 센다). 사건: 앞 PR 78의 일지 커밋 제목이 75자로 72자 제한을 넘어 `parallel-checks`를 약 617초 돈 뒤에야 `commit-msg`가 막았다. 명령이 `git commit -m`이라 `hook_bash_commit_msg`가 못 보는 설계된 사각이다. 간 자리는 `.scratch/retro-queue/commit-msg-after-slow-checks.md`이고 6회차에서 7회차가 되었다. 더하는 것이라 다섯 번째에 반영하는 항목인데 이미 5회차를 넘었으므로, 다음 하네스 chore 배치의 대상이 된다(다섯 번째 이후의 반영 시점은 그 chore가 정한다).
- **부하에서 5초 상한을 넘은 시간 시험**(기각). 사건: `tests/app/test_job_lease.py`의 한 시험이 11분 넘게 도는 pytest의 부하에서 5.2초가 되었다. 부하 시간 시험 종류는 사용자가 2026-11-15에 닫힌 채 두기로 했으므로 대기열에 잇지 않고 이 일지에만 적는다.
- **훅이 모델이 스스로 낸 세션 카드를 막음**(기각). 이미 있는 훅이 그 자리에서 막았고(ADR 0037), 후속 일은 일지의 "다음"과 사용자에게 묻는 길로 갔다.

만료할 항목은 없었다(`uv run python tools/queue_open_rows.py`의 "만료할 항목"이 비었다). 이 세션이 더한 대기열 변경은 `commit-msg-after-slow-checks`의 회차와 `glossary-plain-names-left`의 이어 쓴 문단뿐이다. `rename-sweep-misses-forms`는 PR 78에서 5회차가 되었고 이번 PR에서는 훑기가 이미 처방대로(앞뒤 글자, UTF-8, 양성 대조) 이뤄져 회차를 더하지 않았다.

## 다음

남은 판 영역은 셋이다. 어느 것이든 사용자가 시키면 이어 간다.

1. **릴리스 번호를 가리키는 판.** PR 77이 병합되어 시작할 수 있다. 릴리스 노트의 절 이름 "계약의 판", `tools/release.py`와 그 시험, `--version` 출력, `.scratch/release-image/`의 명세와 티켓, `.scratch/diag-bundle/plan.md`를 함께 본다.
2. **홀로 쓰인 판과 `format_version`.** `src/rag_engine/app/eval_report.py`의 `format_version` 주변 문구와 평가 묶음, 추론 기록의 형식 번호, 파일이나 도구의 사본·개정을 뜻하는 판, 이 파일의 21행과 87행처럼 외부 액션의 판을 가른다.
3. **색인 판 계열**(색인 판, 현재 판, 건설 중인 판, 물러난 판, 살아 있는 판, 판 전환, 스키마 판, 토크나이저 판). 사용자가 "버전으로 바꾼다"를 골랐고 가장 마지막에 한다.

하네스 chore 배치의 조건을 채운 대기열 항목에 `commit-msg-after-slow-checks`(7회차)와 `rename-sweep-misses-forms`(5회차)가 있다. 이 PR을 병합한 뒤 `tools/queue_open_rows.py --ref origin/dev`로 다시 센다.
