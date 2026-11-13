# 15: 전체 게이트: main으로 가는 PR에서 리랭크 뒤 줄을 기준 보고서와 견준다

**What to build:** base가 main인 PR과 수동 실행에서 CI의 전체 게이트 잡이 리랭크 기록으로 전체 실행을 돌려 `baseline-full.json`의 리랭크 뒤 줄과 견준다(스토리 12). CI는 리랭커를 띄우지 않고 기록에서만 점수를 읽는다(ADR 0018 이력 2026-11-13). dev로 가는 PR은 빠른 게이트만 보므로, 출시 PR 앞에서 리랭크 기록과 `baseline-full.json`을 맞추는 절차를 출시 절차에 적는다.

**Blocked by:** 11 (빠른 게이트와 `workflow_dispatch` 계기), 14 (리랭크 기록)

**Status:** ready-for-agent

- [ ] `.github/workflows/ci.yml`에 잡 하나를 더한다. 빠른 게이트와 같은 방법으로 늘 시작하고, base가 main인 PR과 `workflow_dispatch`에서만 평가하며 그 밖에는 스텝의 조건으로 넘긴 채 성공으로 끝난다. main 푸시에서는 평가하지 않는다. `verify`의 `needs`에 잡 이름만 더한다(명세 "전체 게이트와 리랭커"의 전체 게이트의 모양 항목).
- [ ] 잡의 차례는 빠른 게이트와 같고 `run --through rerank`와 `compare --gate full`만 다르다. 리랭커의 끝점을 주지 않아, 기록에 없는 쌍이 하나라도 있으면 실패한다. 보고서 둘을 산출물로 올린다.
- [ ] 첫 `baseline-full.json`: 이 브랜치(dev가 아닌 브랜치)에서 `gh workflow run ci.yml --ref <브랜치>`로 수동 실행을 띄우고, 올라온 산출물의 `report.json`을 사용자에게 보이고 **멈춘다**. 승인을 받은 뒤 커밋하고 승인을 `## Comments`에 사용자의 글 그대로 적는다.
- [ ] 출시 절차에 맞추는 PR을 적는다(명세의 dev와 main 사이에서 기록과 기준을 맞추는 절차 항목). 합친 뒤의 후보를 바꾸는 변경이나 묶음을 고친 변경이 dev에 들어갔으면, 출시 PR 앞에 GPU가 있는 기계에서 `run --through rerank --records write`로 `rerank.jsonl`을 다시 만들고, 그 브랜치의 수동 실행이 올린 보고서로 `baseline-full.json`을 갈아 승인을 받는 PR을 하나 둔다. 적는 자리는 `.claude/skills/next-session/merge.md`의 "출시 PR" 절이고, main에서 딴 핫픽스가 후보를 바꿀 때도 같다는 것을 함께 적는다. 하네스 문서를 고치므로 `CLAUDE.md` 작업 규약 4대로 그 절차를 인용하는 곳을 grep한다.
- [ ] 실행 기록: base가 dev인 PR에서 이 잡이 평가하지 않고 `verify`가 초록인 것과, 수동 실행에서 평가하는 것, 리랭크 뒤 숫자를 일부러 떨어뜨린 커밋의 수동 실행에서 빨강인 것을 실행의 주소로 `## Comments`에 남긴다(명세 Testing Decisions의 게이트 잡 항목). 떨어뜨린 커밋은 병합하지 않는다.
- [ ] 검사 넷이 초록이다.
