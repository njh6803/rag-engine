# glossary-review-workflow-pan-names: 리뷰 워크플로 주석의 판 두 곳을 버전으로 바꾼다 · 2026-11-21

PR 90(일지 `2026-11-20-2107-glossary-standalone-pan-names.md`)을 병합한 같은 세션이 그 일지 "다음"의 첫째 일을 이어서 한 기록이다(Sonnet 5.5, high). 티켓은 `.scratch/harness/issues/glossary-review-workflow-pan-names.md`, 브랜치는 `chore/glossary-review-workflow-pan-names`이고 `origin/dev`(`172b8cd`, PR 90까지 든 것)에서 새로 땄다. 용어집의 이름을 agent-os의 결정에 맞추는 일의 열한 번째 PR이다. 셀프 리뷰 이후의 절은 PR을 연 뒤 이어 쓴다.

## 계기

PR 90 병합 보고의 끝에서 사용자에게 `claude-code-review.yml`의 판 두 줄을 고치는 작은 PR을 이 세션에서 이어 낼지 물었고 "네, 이어서"라고 답했다. 요청 범위는 PR과 병합까지다. 이 파일을 바꾸는 PR은 일지·대기열·티켓·하네스 탐침 밖의 파일을 함께 싣지 못하므로(같은 파일 95~127행의 `Fail when Claude left no comment` 스텝, 허용 정규식은 119행) 앞 영역(PR 90)과 따로 낸다.

## 한 것

- `.github/workflows/claude-code-review.yml` 21행 `판은 손으로 올린다`를 `버전은 손으로 올린다`로, 87행 `판이 바뀌면`을 `버전이 바뀌면`으로 바꿨다. 둘 다 주석이다. 21행은 리뷰 액션의 번호이고 87행은 액션을 올리면 바뀌는 Claude Code의 번호다. 이 파일에 남은 `판`은 75·77·78행의 `판단`뿐이다.
- 티켓 `.scratch/harness/issues/glossary-review-workflow-pan-names.md`를 썼다.
- 대기열 `glossary-plain-names-left`에 이 영역을 한 문단 더했다. 31행이 남은 일로 적은 이 두 줄이 끝났고, 홀로 쓰인 판은 마지막 영역의 몫만 남았다. 앞 영역의 Nit(`deploy/standalone/compose.yaml` 78행 `CPU 버전`은 이미지의 종류를 가리켜 `CPU 이미지`가 낫다는 지적)을 마지막 영역에 맡긴다고 적었다.
- 헌법은 건드리지 않았다. 주석 두 줄이라 헌법 버전은 1.5.7 그대로다.

## 검증

- `uv run python tools/sibling_overlap.py`: 번호 겹침 없음, 새 번호 없음, 함께 고친 파일 없음. 형제가 쓴 가장 높은 헌법 버전은 1.5.7(`origin/dev`)이다.
- YAML이 그대로 읽힌다(`yaml.safe_load`로 읽어 잡 `claude-review` 하나가 나왔다).
- `git diff`는 파일 하나, 두 줄 추가, 두 줄 삭제다. 이 파일을 인용하는 시험은 `tests/`에 없다(`claude-code-review`와 옛 문구를 `tests/`에서 grep해 0건).
- 전체 pytest와 나머지 훅은 커밋이 부르는 pre-commit의 검사 러너가 돈다. `zizmor`를 포함한 CI의 파일 검사는 PR에서 본다.

## 셀프 리뷰

`code-review` 스킬로 기준 `172b8cd`(`origin/dev` 끝)에서 수정 1개 파일, 미추적 1개(티켓), 커밋 0개를 두 축으로 봤다(일지는 이 시점에 아직 없었다). 표준 축은 sonnet·high, 명세 축은 본 세션의 모델로 돌렸다. Critical과 Major는 없었고 Minor 넷이 나왔다.

**고친 것.**
- 표준·명세 축 Minor(같은 지적). 티켓이 가드를 "일지·티켓·프로브 밖의 파일을 함께 싣지 못하는 검사"로 적었는데 실제 허용 집합에는 대기열 폴더가 든다. 앞 티켓의 문구를 옮겨 온 좁은 요약이었다. "일지·대기열·티켓·하네스 탐침"으로 고치고 같은 파일의 95~127행을 댔다.
- 표준·명세 축 Minor(같은 지적). 티켓이 87행의 판을 "액션의 번호"로, 첫 문단에서는 "도구나 이미지의 번호"로 적었다. 이 두 곳에 이미지는 없고 87행은 액션을 올리면 바뀌는 Claude Code의 번호다. 고쳤다.
- 표준 축 Minor. 앞 영역 PR 79·87·90이 모두 대기열 `glossary-plain-names-left`를 고쳤는데 이 티켓은 `대기열:`을 달고도 그 항목을 갱신하는 수용 기준이 없었다. 가드가 대기열 경로를 허용하므로 기준을 더하고 항목에 문단을 더했다.

**남긴 것과 이유.** 없음.

**PR 직전 리뷰에 밀 주장(이 반영으로 새로 쓴 문장).**
- 티켓: 같은 파일의 95~127행 스텝이 일지·대기열·티켓·하네스 탐침 밖의 파일을 함께 싣지 못하게 한다.
- 티켓: 87행의 판은 액션을 올리면 바뀌는 Claude Code의 번호를 뜻한다.
- 대기열 새 문단: `deploy/standalone/compose.yaml` 78행의 `CPU 버전`은 이미지의 종류를 가리킨다는 지적이 있었고, 미룬 두 줄은 `tests/tools/test_check_notes.py` 875행과 `.claude/skills/code-review/SKILL.md` 108행이다.

**다시 돌린 명령.** 고친 글은 문서뿐이다. 아래 "커밋"의 pre-commit 결과가 갈음한다.

## PR 직전 리뷰

CodeRabbit CLI는 이 계정에서 거부되어(앞 PR들과 같다) 버그·성능 축은 `bug-perf-review` 에이전트로, 보안 축은 변경을 직접 읽어 대신했다.

**보안.** 지적 없음. 워크플로에서 바뀐 것은 `#` 주석 두 줄이고 `claude_args`, `run`, `env`, `permissions`, `${{ }}` 표현식, 허용·거부 도구 목록은 그대로다. 87행의 주석은 `claude_args: >-` 바로 위라 값 안에 들어가지 않는다.

**버그·성능(`bug-perf-review`).** 유효 1, 오탐 0. Critical·Major 없음. 이전과 이후 파일을 글자 단위로 맞댔고 바뀐 글자는 21행과 87행의 `판`→`버전`뿐이었다. 밀 주장(95~127행 스텝의 허용 집합, 87행의 Claude Code 번호, `CPU 버전`이 TEI 이미지 태그를 가리킴, 미룬 두 줄의 위치, 헌법 버전 1.5.7)이 모두 맞았다.

**고친 것.**
- Minor. 대기열 새 문단이 마지막 영역의 파일 묶음 전체에 홀로 쓰인 판이 있는 것처럼 읽혔다. 실제로 홀로 쓰인 판이 든 곳은 `src/`, 평가 묶음, `README.md`뿐이고, `GLOSSARY.md`는 옛 이름을 적은 `_Avoid_` 줄뿐이며, `docs/constitution/operations.md`와 PR 서식에는 색인 판 계열과 agent-os ADR 0056의 결정 이름 인용(남길 것)만 있다. 그렇게 가르도록 문단을 고쳤다. `operations.md`의 판 줄은 직접 다시 읽어 맞다고 확인했다.

**남긴 것.** 없음.

**다시 돌린 명령.** 고친 글은 문서뿐이다. 아래 "커밋"의 pre-commit 결과가 갈음한다.
