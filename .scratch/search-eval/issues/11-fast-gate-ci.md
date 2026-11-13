# 11: 빠른 게이트: CI가 검색에 영향을 주는 PR과 푸시에서 기준 보고서 대비 하락을 막는다

**What to build:** 검색에 영향을 주는 경로가 바뀐 PR과 dev·main 푸시, 수동 실행에서 CI의 빠른 게이트 잡이 평가 전용 compose를 띄워 공공 문서 묶음을 색인하고 빠른 실행을 돌려 `baseline-fast.json`과 견준다(스토리 12, 13, 15). 문서만 바꾼 PR에서는 평가하지 않고 필수 검사 `verify`가 초록이다. 첫 기준 보고서는 사용자가 승인한다. 하락폭과 시간 한도를 실제 실행의 측정으로 확정한다.

**Blocked by:** 08 (`compare`), 10 (질문과 임베딩 기록)

**Status:** ready-for-agent

- [ ] 경로 판정은 `tools/`의 순수 함수다(명세 "CI 게이트와 기준 보고서"). 평가하는 경로는 `src/`, `pyproject.toml`, `uv.lock`, `evals/`, `tools/search_eval.py`, `compose.eval.yml`, `.github/workflows/ci.yml`이다. 함수는 이벤트 셋을 받는다. PR이면 merge-base부터의 `git diff --name-only --no-renames`로 정하고(이름을 바꾼 파일은 옛 경로와 새 경로를 모두 판정한다), 푸시와 `workflow_dispatch`면 늘 평가하며, PR에서 merge-base나 바뀐 경로를 읽지 못하면 평가한다. `tests/tools/`가 이 셋과 목록, 그리고 `src/`의 파일을 목록 밖으로 옮긴 경우가 평가하는 것을 시험한다.
- [ ] `.github/workflows/ci.yml`에 잡 하나를 더한다. PR(base가 dev든 main이든)과 dev·main 푸시에서 늘 시작하고, 첫 스텝이 경로 판정으로 평가할지를 정하며, 평가하지 않으면 나머지 스텝을 스텝의 조건(`if`)으로 넘긴 채 성공으로 끝난다. 체크아웃은 merge-base를 구할 만큼 역사를 받는다. `verify`의 판정 줄은 고치지 않고 `needs`에 잡 이름만 더한다.
- [ ] 잡의 차례는 평가 전용 compose로 PostgreSQL과 임베딩 TEI(`--max-batch-tokens 4096`)를 띄우고 `validate`, `index`, `validate --indexed`, `run --through fused`, `compare --gate fast`다. 기록 방식은 `read`다. 보고서 둘은 성공이든 실패든 산출물로 올린다. 모델 파일은 CI 캐시에 둔다. 포크 PR이 캐시를 오염시킬 수 있는지는 GitHub의 공식 문서를 원문으로 읽어 확인하고, 읽은 자리를 `## Comments`에 적는다(명세 일지의 "다음").
- [ ] TEI가 4096으로 러너에서 뜨는지 실제 실행으로 본다. 뜨지 않으면 더 낮추고 그 값을 `compose.eval.yml`과 명세에 맞춘다(명세 "CI 게이트와 기준 보고서"의 4096 항목).
- [ ] `ci.yml`의 `on:`에 `workflow_dispatch`를 더한다. 15(전체 게이트)보다 먼저 dev에 들어가야 한다. 수동 실행에서 다른 잡과 `verify`가 어떻게 끝나는지는 이 티켓이 아니라 15가 실행 기록으로 확인한다. 기본 브랜치(dev)의 워크플로 파일에 이 계기가 들어가기 전에는 수동 실행이 뜨는지 GitHub 문서가 적지 않아, 이 티켓의 PR 안에서는 확인할 수 없기 때문이다(명세 "전체 게이트와 리랭커"의 전체 게이트의 모양 항목, PR #38 봇 첫 회차의 지적).
- [ ] 첫 기준 보고서: 이 PR의 빠른 게이트는 기준 보고서가 없어 실패한다. 올라온 산출물의 `report.json`을 사용자에게 보이고 **멈춘다**. 승인을 받은 뒤 `baseline-fast.json`으로 커밋하고, 승인을 이 티켓의 `## Comments`에 사용자의 글 그대로 적는다.
- [ ] 흔들림: 같은 커밋의 빠른 게이트를 CI에서 세 번 돌려(매번 새 색인) 실행 사이의 차를 잰다. 어느 숫자든 차가 질문 하나의 몫(상위 5 적중률 0.67%p)을 넘으면 **멈춰** 사용자에게 다시 묻는다. 넘지 않으면 하락폭(2%p, 0.02)이 첫 기준 보고서의 승인과 함께 확정된다.
- [ ] 시간: CI에서 걸린 잡의 시간을 재어 `.scratch/search-eval/probes/`의 README에 적는다. 15분을 넘으면 **멈춰** 사용자에게 다시 묻는다. `timeout-minutes`는 20이다.
- [ ] 실행 기록: 문서만 바꾼 커밋에서 이 잡이 평가하지 않고 `verify`가 초록인 것과, 숫자를 일부러 떨어뜨린 커밋에서 빨강인 것을 실행 기록(실행의 주소)으로 `## Comments`에 남긴다. 떨어뜨린 커밋은 병합하지 않는다.
- [ ] `docs/constitution/operations.md`의 CI 절(적중률이 기준치 아래로 떨어질 때라는 문장)을 게이트가 선 동작으로 고칠 문장의 초안을 사용자에게 보이고 **멈춘다**. 헌법의 개정은 사용자가 승인한다(헌법 거버넌스, PR #38 봇 첫 회차의 지적). 승인을 받은 뒤 고치고, 승인을 `## Comments`에 사용자의 글 그대로 적으며, 헌법 판을 patch로 올린다(`docs/constitution/README.md`의 `**Version**` 줄. 판을 올린 까닭은 그 README가 정한 대로 ADR 이력이나 그 PR의 일지에 적는다). `ci.yml`의 머리 주석(느린 검사를 main PR에만 둘지를 설계에 미룬 문장)도 고친다. 이 티켓이 헌법을 바꾸는 티켓을 첫 티켓으로 두는 규칙의 예외인 까닭은 명세 Further Notes에 있다.
- [ ] 게이트가 빨강일 때 에이전트는 기준 보고서를 스스로 갱신하지 않고 멈춰 보고한다.
- [ ] 검사 넷이 초록이다.
