# decision-word-residue: 결정이 "첫 티켓"의 뜻을 바꿨는데 그 말을 ADR까지 grep하지 않아 ADR 0007·0011의 문장이 거짓으로 남았다

**상태:** 열림
**어디로:** `CLAUDE.md` 작업 규약 4가 이미 있다. 다섯 번째면 계기 훅 후보(사용자 답이 번호나 이름의 뜻을 바꾸는 선택이면 그 말을 `docs/adr/`·`docs/constitution/`까지 grep하라고 넣는다)
**승인:** 자체 승인 2026-11-10, 3회차(작업 규약 4를 어긴 사건이라 회차를 센다), 일지 2026-11-10-1828-core-tickets.md, 2026-11-10-2250-core-02-contract-layers.md(2회차), 2026-11-11-0929-core-get-document-text-window.md(3회차: 도구의 모양을 바꾸고 옛 표현을 `.scratch/core/issues/`에서 grep하지 않아 티켓 09·10의 문장이 남았다), ADR 불필요

core 티켓 세션이 테스트 데이터베이스 러너를 core 01로 두며 "하네스 티켓"은 grep했지만 "첫 티켓"은 하지 않았다. ADR 0007 Consequences 둘과 ADR 0011의 greenlet 재확인이 옛 뜻의 첫 티켓을 가리켜 명세 축 Minor 3·4가 잡았다.

2회차는 core 02다. `server.py`가 `server/`가 되어 옛 경로를 grep했지만 범위를 `docs/`, `.claude/`, `tools/`로만 잡아 `.github/PULL_REQUEST_TEMPLATE.md:33`이 남았고 명세 축 리뷰가 잡았다(`.coderabbit.yaml`의 같은 경로는 문서 넷을 고치다 따로 찾아 고쳤다). 앞 사건은 grep의 대상 말이 모자랐고 이번은 대상 폴더가 모자랐다. 둘 다 "옛 표현을 grep해 잔존 0"의 범위를 이 결정이 닿는 곳보다 좁게 잡은 것이다.
