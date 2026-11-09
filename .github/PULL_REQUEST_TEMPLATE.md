## 변경사항

<!-- 무엇을 바꿨는지는 diff가 보여준다. 리뷰어(사람과 봇)가 필요한 것은 "왜"와 "남긴 위험"이다 -->

### 변경 유형

- [ ] `feat` 새 기능
- [ ] `fix` 버그 수정
- [ ] `refactor` 리팩토링 (기능 변경 없음)
- [ ] `test` 테스트만
- [ ] `docs` 문서·지침
- [ ] `chore` 빌드·의존성·설정·하네스
- [ ] `perf` 성능
- [ ] `style` 포맷만

### 왜 이렇게 했나

<!-- 대안이 있었다면 왜 택하지 않았는지. 여러 티켓에 걸쳐 구속력을 갖는 결정이면 docs/adr/ 링크 -->

### 남긴 위험

<!-- 이 PR이 하지 않은 것, 다음 티켓으로 미룬 것, 확신이 없는 판단. 없으면 "없음" -->

### 계약 영향

<!-- 계약(헌법 원칙 VII: 검색 도구의 형식, 수집 API, 커넥터·변환·파서 인터페이스, 색인 형식)과 헌법에 닿지 않았으면 "없음".
     닿았으면 어느 계약의 무엇이 바뀌었는지, 그 때문에 함께 바꾼 것(칸을 지우거나 뜻을 바꿨으면 올린 판, ADR, 계약 시험 `tests/contract/`, 헌법 판 `docs/constitution/README.md`), 이 변경을 기다리는 티켓을 적는다 -->

## 변경된 영역

<!-- 실제로 바뀐 경로만 체크한다. 괄호는 그 영역을 바꿀 때 같이 확인할 것 -->

- [ ] `src/rag_engine/server.py` — HTTP와 MCP 표면(FastAPI 앱, `/health`, `/mcp`) (MCP에는 읽기 도구만 등록했는가(원칙 IV, ADR 0001). 검색 도구의 형식을 바꿨으면 `tests/contract/`의 계약 시험과 판을 함께 바꿨는가(원칙 VII). 인증 없는 요청과, 접근 그룹을 쓰는 설치에서 주체 없는 요청을 거부하는가(원칙 V). 질문 내용·연결 정보·원본 문서의 내용이 로그·오류 응답에 실리지 않는가(원칙 V, ADR 0004). mcp·FastAPI의 타입이 계약과 도메인으로 새지 않는가(`CODING_STANDARDS.md`))
- [ ] `src/rag_engine/main.py` — 관리 명령 (쓰기(수집, 삭제, 재색인)는 관리 명령·관리 API·수집 API로만 여는가(원칙 IV). `main → server` 방향은 `pyproject.toml`의 import-linter 계약이 판정한다)
- [ ] `src/rag_engine/`의 새 모듈·층 — 층은 core 설계 인터뷰가 정한다 (새 층을 더했으면 import-linter 계약에 넣었는가, 플러그인 자리 셋(커넥터·변환·파서, ADR 0003) 밖의 새 추상화가 아닌가, 설치처의 정보가 들어오지 않았는가(ADR 0003))
- [ ] `tests/contract/` — 계약 시험 (공식 MCP SDK의 클라이언트로 HTTP 접속해 보는가, 쓰기 도구가 없음을 계속 보는가)
- [ ] `tests/` — 행동을 검증하는가, skip이 초록으로 읽히지 않는가(원칙 I)
- [ ] `.claude/`, `tools/`, `.pre-commit-config.yaml` — 하네스 (실제 실행으로 확인했는가, 새 검사는 `tools/mutate.py`로 변이를 넣어 빨강을 봤는가, 이 검사가 **못 보는 것**을 어디에 적었고 그 주장을 쟀는가, 훅은 `tools/hook_payloads.toml`에 발동 페이로드와 발동하지 말아야 할 **실제** 입력을 더했는가(`tools/run_hooks.py`가 pre-commit에서 돈다), 구조가 바뀌었으면 README도 갱신했는가)
- [ ] `docs/`, `CLAUDE.md`, `GLOSSARY.md`, `CODING_STANDARDS.md` — 지침·헌법·ADR (원천 하나, CLAUDE.md 200줄 이하, 헌법을 고쳤으면 판을 올렸는가)
- [ ] `.github/` — 워크플로 (`claude-code-review.yml`을 바꾸면 별도 PR로 먼저 병합. 그 PR은 claude-review가 건너뛰므로(그 파일의 머리 주석) CodeRabbit 코멘트와 셀프 리뷰를 손으로 본다. 그 PR에서 코멘트 0개 가드(`Fail when Claude left no comment` 스텝)는 코멘트를 세지 않는 대신, 그 파일과 그 스텝이 허용한 경로(일지·대기열 등. 원천은 그 스텝의 패턴) 밖의 파일이 함께 실리면 실패한다. 그래서 그 워크플로의 동작을 서술한 문서 가운데 허용 경로 밖의 것(이 템플릿, `operations.md` 등)은 그 PR이 병합된 뒤 따로 고친다. 다른 워크플로만 바꾼 PR은 리뷰가 돌고 가드가 코멘트를 센다)
  - 필수 검사 `verify`의 판정을 바꿨으면 빨강이어야 하는 경우(실패·취소·건너뛴 잡, needs 밖의 잡)와 실패한 잡만 다시 돌린 시도를 실제 실행해 봤는가(`.github/workflows/ci.yml`의 verify 주석)

## 체크리스트

<!-- 실제로 실행한 것만 체크한다. 커밋의 pre-commit이나 `uv run python tools/run_checks.py`가 돌린 검사도 실행이고(러너의 pytest는 프로세스를 나눠 돈다), 그 출력에서 Skipped인 검사는 실행이 아니다(헌법 원칙 I: skip은 초록이 아니다). 안 돌렸으면 비워 두고 이유를 한 줄 적는다 -->

- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] `uv run pyright`
- [ ] `uv run lint-imports`
- [ ] `uv run pytest -q` (계약 시험 `tests/contract/`도 여기서 돈다)
- [ ] 커밋 전 `/code-review`로 셀프 리뷰하고 Critical·Major를 반영했다. 보류한 지적은 별도 티켓이나 회고 후보로 뺐고, 다른 층·티켓에 넘긴 것은 받는 쪽에 적었다
- [ ] PR 직전 `coderabbit-review` 서브에이전트를 돌렸다(보안·버그·성능 축). **`coderabbit auth status`의 `Seat:` 줄은 보고에 옮기는 값이고, CLI 축인지는 리뷰가 실제로 끝까지 도는지로 가른다 — agent-os에서 `Seat: not assigned`에서도 리뷰가 돌았다.** CLI가 돌지 못하면(미설치, 로그인 없음, 좌석 거절, 한도 초과) 내장 `/security-review`(보안, 작업을 커밋하고 origin/main을 합친 뒤에)와 `bug-perf-review` 서브에이전트(버그·성능)를 대신 돌리고, 무엇이 돌았는지와 결과를 적는다. **문서만 바뀐 PR도 면제가 아니다** — 설계 문서의 침묵이 곧 구현의 침묵이다(agent-os에서 코드 0줄인 PR 넷에서 CWE 넷). 한도와 좌석은 `.claude/agents/coderabbit-review.md`
- [ ] 결정을 바꿨다면 그것을 참조하는 스킬·훅·rules·명세도 같이 고쳤다
- [ ] 새 환경 변수는 `.env.example`에 있다

## 확인 방법

```bash
uv run ruff check . && uv run ruff format --check .
uv run python tools/run_checks.py
```

<!-- 위 외에 확인한 시나리오, 재현 절차, 실행한 명령과 결과 -->

## 관련 티켓

<!-- 이 브랜치가 가리키는 티켓 경로. 기능 디렉터리의 티켓은 .scratch/<slug>/issues/NN-<slug>.md(명세는 .scratch/<slug>/spec.md),
     harness 티켓은 .scratch/harness/issues/<slug>.md. 티켓을 쓰지 않는 면제 PR이면 면제의 종류(기능의 설계·명세·티켓, 기록만)를 적는다.
     규약은 docs/agents/issue-tracker.md -->

## 리뷰어 참고

<!-- 특히 봐줬으면 하는 부분, 불확실했던 판단. 기준은 CODING_STANDARDS.md의 심각도와 리뷰 관점 넷.
     누가 어느 축을 보는지는 operations.md 리뷰 파이프라인. PR 직전 리뷰(CLI 또는 대체 둘) 결과는 위 체크리스트에.
     코멘트 0개인 초록은 리뷰 없음일 수 있다(operations.md) -->
