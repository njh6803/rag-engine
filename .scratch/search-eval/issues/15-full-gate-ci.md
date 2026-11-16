# 15: 전체 게이트: main으로 가는 PR에서 리랭크 뒤 줄을 기준 보고서와 견준다

**What to build:** base가 main인 PR과 수동 실행에서 CI의 전체 게이트 잡이 리랭크 기록으로 전체 실행을 돌려 `baseline-full.json`의 리랭크 뒤 줄과 견준다(스토리 12). CI는 리랭커를 띄우지 않고 기록에서만 점수를 읽는다(ADR 0018 이력 2026-11-13). dev로 가는 PR은 빠른 게이트만 보므로, 출시 PR 앞에서 리랭크 기록과 `baseline-full.json`을 맞추는 절차를 출시 절차에 적는다.

**Blocked by:** 11 (빠른 게이트와 `workflow_dispatch` 계기), 14 (리랭크 기록)

**Status:** done

- [x] `.github/workflows/ci.yml`에 잡 하나를 더한다. 빠른 게이트와 같은 방법으로 늘 시작하고, base가 main인 PR과 `workflow_dispatch`에서만 평가하며 그 밖에는 스텝의 조건으로 넘긴 채 성공으로 끝난다. main 푸시에서는 평가하지 않는다. `verify`의 `needs`에 잡 이름만 더한다(명세 "전체 게이트와 리랭커"의 전체 게이트의 모양 항목).
- [x] 잡의 차례는 빠른 게이트와 같고 `run --through rerank`와 `compare --gate full`만 다르다. 리랭커의 끝점을 주지 않아, 기록에 없는 쌍이 하나라도 있으면 실패한다. 보고서 둘을 산출물로 올린다.
- [x] 수동 실행의 다른 잡: 11이 `workflow_dispatch`를 dev에 넣은 뒤이므로 이 브랜치(dev가 아닌 브랜치)에서 `gh workflow run ci.yml --ref <브랜치>`로 수동 실행을 띄워, 다른 잡(`ticket`, `python`, `image`)과 `verify`가 어떻게 끝나는지 실행 기록으로 확인한다. 같은 브랜치에 푸시를 이어 넣어 `concurrency`가 앞 실행을 취소하게 하고, 취소된 실행에서 `verify`가 어떻게 끝나는지도 실행 기록으로 확인한다(명세 일지의 "다음". 11에서 옮겼다, PR #38 봇 첫 회차의 지적). 가를 일이 생기면 잡의 조건이 아니라 스텝의 조건으로 가른다.
- [x] 첫 `baseline-full.json`: 이 브랜치(dev가 아닌 브랜치)에서 `gh workflow run ci.yml --ref <브랜치>`로 수동 실행을 띄우고, 올라온 산출물의 `report.json`을 사용자에게 보이고 **멈춘다**. 승인을 받은 뒤 커밋하고 승인을 `## Comments`에 사용자의 글 그대로 적는다.
- [x] 출시 절차에 맞추는 PR을 적는다(명세의 dev와 main 사이에서 기록과 기준을 맞추는 절차 항목). 합친 뒤의 후보를 바꾸는 변경이나 묶음을 고친 변경이 dev에 들어갔으면, 출시 PR 앞에 GPU가 있는 기계에서 `run --through rerank --records write`로 `rerank.jsonl`을 다시 만들고, 그 브랜치의 수동 실행이 올린 보고서로 `baseline-full.json`을 갈아 승인을 받는 PR을 하나 둔다. 적는 자리는 `.claude/skills/next-session/merge.md`의 "출시 PR" 절이고, main에서 딴 핫픽스가 후보를 바꿀 때도 같다는 것을 함께 적는다. 하네스 문서를 고치므로 `CLAUDE.md` 작업 규약 4대로 그 절차를 인용하는 곳을 grep한다.
- [ ] 실행 기록: base가 dev인 PR에서 이 잡이 평가하지 않고 `verify`가 초록인 것과, 수동 실행에서 평가하는 것, 리랭크 뒤 숫자를 일부러 떨어뜨린 커밋의 수동 실행에서 빨강인 것을 실행의 주소로 `## Comments`에 남긴다(명세 Testing Decisions의 게이트 잡 항목). 떨어뜨린 커밋은 병합하지 않는다.
- [x] 검사 넷이 초록이다.

## Comments

### 2026-11-16 수동 실행: 다른 잡과 `verify`

`gh workflow run ci.yml --ref feature/15-full-gate-ci`로 커밋 `b700333`을 수동 실행했다(실행 43766794021, <https://github.com/njh6803/rag-engine/actions/runs/43766794021>). 잡별 결과는 `python`·`image`·`ticket`·`eval-fast`가 성공, `eval-full`이 실패, `verify`가 실패다. `eval-full`은 4분 20초 만에 `validate`, `index --records read`, `validate --indexed`, `run --through rerank --records read`까지 성공했고 마지막 `compare --gate full`만 종료 코드 1이었다. 로그의 원인 문장은 "기준 보고서가 없다: baseline-full.json. 견줄 값이 없어 실패한다"다. 첫 기준이 없으니 예상한 실패다. 리랭커 끝점을 주지 않았는데도 추론 기록 15,786건을 모두 읽었고 새로 계산한 수는 0이었다. 산출물 `eval-full-report-1`(`report.json`, `report.md`)이 올라왔다.

### 2026-11-16 `concurrency` 취소 관찰

티켓은 "같은 브랜치에 푸시를 이어 넣어" 앞 실행을 취소하게 하라고 적었으나, 이 저장소의 `ci.yml`은 `push`를 main과 dev에서만 받으므로 다른 브랜치의 푸시는 CI를 띄우지 않는다. 그래서 같은 `--ref`로 수동 실행을 연달아 두 번 띄웠다. 앞 실행 43768005935(<https://github.com/njh6803/rag-engine/actions/runs/43768005935>)가 뒤 실행 43768046697에 취소됐다. 취소된 실행의 잡은 `python`·`eval-full`·`image`·`eval-fast`가 `cancelled`, `ticket`이 `success`(이미 끝나 있었다), `verify`가 `failure`다. 다른 잡이 성공하지 못했으므로 `verify`가 빨강으로 끝나는 것이 맞고, 취소된 실행이 초록으로 남아 병합을 허용하는 일은 없다. 뒤 실행은 관찰만 하고 취소했다.

### 2026-11-16 실행 기록: 리랭크 뒤 숫자를 떨어뜨린 커밋의 수동 실행

`baseline-full.json`의 리랭크 줄 상위 5 적중률과 MRR을 0.05씩 올린 임시 커밋 `70bbfc2`(`human`·`keyword` 두 질의 목록, 네 숫자, 서식은 그대로)를 만들어 분리 HEAD에서 커밋하고(브랜치 이름이 티켓을 가리켜야 하는 `check-ticket`은 분리 HEAD에서 지나간다) `scratch/15-gate-drop`으로 올려 `gh workflow run ci.yml --ref scratch/15-gate-drop`으로 수동 실행했다. 실행 43811661719(<https://github.com/njh6803/rag-engine/actions/runs/43811661719>)에서 `eval-full`이 `compare --gate full`에서 실패했고 `python`·`image`·`ticket`·`eval-fast`는 성공, `verify`는 실패다. 로그의 문장은 "게이트 full: 하락폭을 넘어 떨어진 숫자가 4개 있다. 하락폭은 상위 5 적중률 2%p, MRR 0.02이고 정확히 그만큼은 통과한다"이고, 네 줄은 `human`·`keyword`의 `hit_at_5`(차 0.038709677)와 `mrr`(차 0.049999843, 0.049999664)다. 이 임시 브랜치는 병합하지 않고 실행 기록을 남긴 뒤 원격에서 지웠다. 이 기록도 검색 코드를 망가뜨려 만든 것이 아니라 기준의 숫자를 올려 게이트의 하락 판정 동작만 보인 것이다(티켓 11 Comments의 같은 한계). 실제 품질 저하를 이 게이트가 잡는지는 이 기록으로 보지 못했다.

### 2026-11-16 첫 `baseline-full.json` 승인

사용자에게 실행 43766794021의 산출물 `report.json`(sha256 `cc2236b86b7c930c0f1d5a94ab961ef58ea8a9961bf36138f7ec48d8dcab679b`)을 보이고 기준으로 쓸지 물었다. 리랭크 단계의 `human` 목록은 적중률@1 0.774, @5 0.961, MRR 0.861이고 `keyword` 목록은 적중률@1 0.774, @5 0.961, MRR 0.860이다. 놓친 질의 4개는 모두 `lost_in_rerank`다. LLM 관련성 판정 숫자는 `judgments.jsonl`이 없어 비어 있다. 사용자의 답은 다음과 같다.

> 승인

승인받은 `report.json`을 고치지 않고 `evals/public-docs/baseline-full.json`으로 복사했다(복사 뒤 sha256이 위와 같다).

### 2026-11-16 헌법과 ADR 개정의 승인

사용자에게 `docs/constitution/operations.md` 9행(게이트가 둘이 됨)과 24행(출시 PR 앞의 확인), 헌법 판 1.3.2에서 1.3.3(patch), ADR 0018의 새 이력과 본문 포인터 셋(Consequences 36·39·42행)의 초안을 보이고 그대로 고쳐도 되는지 물었다. 사용자의 답은 다음과 같다.

> 승인

승인받은 초안대로 고쳤다. 9행은 "검색 품질은 search-eval의 게이트 둘이 지킨다"로 시작하고 전체 게이트의 동작(base가 main인 PR과 수동 실행에서 `eval-full`이 리랭크 뒤 줄을 `baseline-full.json`과 견주고, 푸시와 base가 dev인 PR에서는 평가하지 않고 성공으로 끝난다)을 더했다. 24행은 출시 PR을 열기 전에 dev의 머리에서 전체 게이트가 초록인지 보고, 합친 뒤의 후보를 바꾼 변경이 있으면 리랭크 기록과 `baseline-full.json`을 맞추는 PR을 하나 두라고 더했다. 새 원칙이나 새 절 없이 기존 절의 줄을 고쳐 patch다. `Last Amended`는 승인한 날(2026-11-16)이다. ADR 0016 12행은 "같은 잡을 돈다"가 글자 그대로 여전히 참이고 `(바뀜: ADR 0018)` 포인터가 이미 있어 고치지 않았다. `uv run python tools/check_adr_pointers.py`는 종료 코드 0이고 `uv run python tools/sibling_overlap.py`는 0이다(형제가 쓴 가장 높은 헌법 판 1.3.2, 겹침 없음).
### 2026-11-16 티켓 18 세션이 넘긴 메모 (수용 기준이 아니다)

전체 게이트는 리랭커 끝점 없이 기록만으로 돈다. 티켓 18 세션의 둘째 평가 데이터베이스(같은 묶음, 같은 조각 수 2,193개, 같은 명령)에서는 질의 310개 가운데 122개에서 후보 1~7개(합계 214쌍)가 리랭크 기록에 없어 `run --through rerank --records read`가 리랭커 끝점 없이 "기록에 없는 쌍이 있고" 오류로 멈췄다. 첫 전체 실행의 데이터베이스에서는 없었고 까닭은 조사하지 않았다(증거와 방법은 티켓 18 Comments). CI의 데이터베이스가 기록을 만든 데이터베이스와 같은 후보를 뽑는지는 이 티켓의 첫 수동 실행이 가를 일이다.

이 티켓의 답(2026-11-16). 첫 수동 실행(실행 43766794021)에서 `eval-full`은 리랭커 끝점 없이 `run --through rerank --records read`를 끝냈고, 보고서의 추론 기록 칸이 읽은 수 15,786, 새로 계산한 수 0이었다. 그 실행의 CI 데이터베이스는 기록에 없는 쌍을 뽑지 않았다. 한 번의 실행이라 CI의 데이터베이스가 늘 같은 후보를 뽑는다는 보증은 아니고, 티켓 18 세션의 둘째 데이터베이스에서 난 일의 까닭은 이 티켓도 조사하지 않았다. 기록에 없는 쌍이 생기면 `run --through rerank --records read`가 "기록에 없는 쌍이 있고" 오류로 멈추므로 게이트는 빨개지고, 조용히 초록이 되지는 않는다.
