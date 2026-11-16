# 15: 전체 게이트: main으로 가는 PR에서 리랭크 뒤 줄을 기준 보고서와 견준다

**What to build:** base가 main인 PR과 수동 실행에서 CI의 전체 게이트 잡이 리랭크 기록으로 전체 실행을 돌려 `baseline-full.json`의 리랭크 뒤 줄과 견준다(스토리 12). CI는 리랭커를 띄우지 않고 기록에서만 점수를 읽는다(ADR 0018 이력 2026-11-13). dev로 가는 PR은 빠른 게이트만 보므로, 출시 PR 앞에서 리랭크 기록과 `baseline-full.json`을 맞추는 절차를 출시 절차에 적는다.

**Blocked by:** 11 (빠른 게이트와 `workflow_dispatch` 계기), 14 (리랭크 기록)

**Status:** in-progress

- [ ] `.github/workflows/ci.yml`에 잡 하나를 더한다. 빠른 게이트와 같은 방법으로 늘 시작하고, base가 main인 PR과 `workflow_dispatch`에서만 평가하며 그 밖에는 스텝의 조건으로 넘긴 채 성공으로 끝난다. main 푸시에서는 평가하지 않는다. `verify`의 `needs`에 잡 이름만 더한다(명세 "전체 게이트와 리랭커"의 전체 게이트의 모양 항목).
- [ ] 잡의 차례는 빠른 게이트와 같고 `run --through rerank`와 `compare --gate full`만 다르다. 리랭커의 끝점을 주지 않아, 기록에 없는 쌍이 하나라도 있으면 실패한다. 보고서 둘을 산출물로 올린다.
- [ ] 수동 실행의 다른 잡: 11이 `workflow_dispatch`를 dev에 넣은 뒤이므로 이 브랜치(dev가 아닌 브랜치)에서 `gh workflow run ci.yml --ref <브랜치>`로 수동 실행을 띄워, 다른 잡(`ticket`, `python`, `image`)과 `verify`가 어떻게 끝나는지 실행 기록으로 확인한다. 같은 브랜치에 푸시를 이어 넣어 `concurrency`가 앞 실행을 취소하게 하고, 취소된 실행에서 `verify`가 어떻게 끝나는지도 실행 기록으로 확인한다(명세 일지의 "다음". 11에서 옮겼다, PR #38 봇 첫 회차의 지적). 가를 일이 생기면 잡의 조건이 아니라 스텝의 조건으로 가른다.
- [ ] 첫 `baseline-full.json`: 이 브랜치(dev가 아닌 브랜치)에서 `gh workflow run ci.yml --ref <브랜치>`로 수동 실행을 띄우고, 올라온 산출물의 `report.json`을 사용자에게 보이고 **멈춘다**. 승인을 받은 뒤 커밋하고 승인을 `## Comments`에 사용자의 글 그대로 적는다.
- [ ] 출시 절차에 맞추는 PR을 적는다(명세의 dev와 main 사이에서 기록과 기준을 맞추는 절차 항목). 합친 뒤의 후보를 바꾸는 변경이나 묶음을 고친 변경이 dev에 들어갔으면, 출시 PR 앞에 GPU가 있는 기계에서 `run --through rerank --records write`로 `rerank.jsonl`을 다시 만들고, 그 브랜치의 수동 실행이 올린 보고서로 `baseline-full.json`을 갈아 승인을 받는 PR을 하나 둔다. 적는 자리는 `.claude/skills/next-session/merge.md`의 "출시 PR" 절이고, main에서 딴 핫픽스가 후보를 바꿀 때도 같다는 것을 함께 적는다. 하네스 문서를 고치므로 `CLAUDE.md` 작업 규약 4대로 그 절차를 인용하는 곳을 grep한다.
- [ ] 실행 기록: base가 dev인 PR에서 이 잡이 평가하지 않고 `verify`가 초록인 것과, 수동 실행에서 평가하는 것, 리랭크 뒤 숫자를 일부러 떨어뜨린 커밋의 수동 실행에서 빨강인 것을 실행의 주소로 `## Comments`에 남긴다(명세 Testing Decisions의 게이트 잡 항목). 떨어뜨린 커밋은 병합하지 않는다.
- [ ] 검사 넷이 초록이다.

## Comments

### 2026-11-16 수동 실행: 다른 잡과 `verify`

`gh workflow run ci.yml --ref feature/15-full-gate-ci`로 커밋 `b700333`을 수동 실행했다(실행 43766794021, <https://github.com/njh6803/rag-engine/actions/runs/43766794021>). 잡별 결과는 `python`·`image`·`ticket`·`eval-fast`가 성공, `eval-full`이 실패, `verify`가 실패다. `eval-full`은 4분 20초 만에 `validate`, `index --records read`, `validate --indexed`, `run --through rerank --records read`까지 성공했고 마지막 `compare --gate full`만 종료 코드 1이었다. 로그의 원인 문장은 "기준 보고서가 없다: baseline-full.json. 견줄 값이 없어 실패한다"다. 첫 기준이 없으니 예상한 실패다. 리랭커 끝점을 주지 않았는데도 추론 기록 15,786건을 모두 읽었고 새로 계산한 수는 0이었다. 산출물 `eval-full-report-1`(`report.json`, `report.md`)이 올라왔다.

### 2026-11-16 `concurrency` 취소 관찰

티켓은 "같은 브랜치에 푸시를 이어 넣어" 앞 실행을 취소하게 하라고 적었으나, 이 저장소의 `ci.yml`은 `push`를 main과 dev에서만 받으므로 다른 브랜치의 푸시는 CI를 띄우지 않는다. 그래서 같은 `--ref`로 수동 실행을 연달아 두 번 띄웠다. 앞 실행 43768005935(<https://github.com/njh6803/rag-engine/actions/runs/43768005935>)가 뒤 실행 43768046697에 취소됐다. 취소된 실행의 잡은 `python`·`eval-full`·`image`·`eval-fast`가 `cancelled`, `ticket`이 `success`(이미 끝나 있었다), `verify`가 `failure`다. 다른 잡이 성공하지 못했으므로 `verify`가 빨강으로 끝나는 것이 맞고, 취소된 실행이 초록으로 남아 병합을 허용하는 일은 없다. 뒤 실행은 관찰만 하고 취소했다.

### 2026-11-16 첫 `baseline-full.json` 승인

사용자에게 실행 43766794021의 산출물 `report.json`(sha256 `cc2236b86b7c930c0f1d5a94ab961ef58ea8a9961bf36138f7ec48d8dcab679b`)을 보이고 기준으로 쓸지 물었다. 리랭크 단계의 `human` 목록은 적중률@1 0.774, @5 0.961, MRR 0.861이고 `keyword` 목록은 적중률@1 0.774, @5 0.961, MRR 0.860이다. 놓친 질의 4개는 모두 `lost_in_rerank`다. LLM 관련성 판정 숫자는 `judgments.jsonl`이 없어 비어 있다. 사용자의 답은 다음과 같다.

> 승인

승인받은 `report.json`을 고치지 않고 `evals/public-docs/baseline-full.json`으로 복사했다(복사 뒤 sha256이 위와 같다).
