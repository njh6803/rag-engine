# journal-cite-on-reworded-lines: 낱말만 바꾼 줄에 든 agent-os 일지 인용을 `sibling_overlap`이 이 저장소에 없는 일지를 가리킨 새 인용으로 읽는다

**상태:** 열림
**어디로:** `tools/sibling_overlap.py`(일지 인용 검사가 줄이 바뀐 것과 인용이 새로 더해진 것을 가르게 한다)
**승인:** 자체 승인 2026-11-19, 1회차(고침이라 사건 하나로 반영한다), 일지 2026-11-19-0202-glossary-constitution-version-names.md, ADR 불필요

`glossary-constitution-version-names`는 도구 독스트링의 "판"을 "버전"으로 바꿨다. 바뀐 줄 안에 agent-os 일지 인용(`일지 2026-09-25-01` 등)이 들어 있어, `sibling_overlap`가 "어디에도 없는 일지를 가리킨 인용"으로 읽고 종료 1을 냈다. 인용을 코드 스팬으로 감싸 풀었으나 `rewrap_comments.py`가 줄을 다시 쪼개 새 줄에 인용이 올라가면 다시 걸려 세 번 돌렸다. 인용은 낱말만 바뀐 줄에 원래 있던 것이라 이 PR이 더한 인용이 아니다. 이름 바꾸기 PR이 `glossary-plain-names-left`에 아직 여럿 남았으므로 같은 일이 되풀이된다.
