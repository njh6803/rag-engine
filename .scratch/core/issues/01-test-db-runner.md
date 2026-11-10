# 01: 테스트 데이터베이스 러너

**What to build:** 개발자가 Docker만 켜 두면 `uv run pytest`와 커밋 훅의 검사 러너가 테스트 PostgreSQL을 스스로 띄워 core의 데이터베이스 시험을 돌리고, CI도 같은 판의 PostgreSQL에서 돈다. 데이터베이스가 없으면 시험은 skip이 아니라 실패한다(원칙 I). 설계 일지는 이 일을 하네스 티켓으로 적었지만 사용자가 2026-11-10 티켓 세션에서 core의 첫 티켓으로 골랐다(명세 Further Notes).

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `compose.test.yml`이 `pgvector/pgvector:0.8.7-pg18-trixie`(운영과 같은 판)를 띄우고, 테스트 역할에 데이터베이스 생성 권한이 있다(명세 "테스트 데이터베이스와 이미지 판" 절. 02~03의 템플릿 데이터베이스가 쓴다).
- [ ] 검사 러너(`CLAUDE.md` 검증 명령 절의 pre-commit 검사 러너)가 `RAG_TEST_DATABASE_URL`의 서버가 안 보이면 compose로 띄우고 준비될 때까지 기다린 뒤 pytest를 돈다. Docker가 없으면 무엇을 켜야 하는지 한 줄로 알리고 실패한다. 띄운 컨테이너를 내릴지 남길지 정하고 러너 독스트링에 적는다.
- [ ] `RAG_TEST_DATABASE_URL`이 없거나 닿지 않으면 데이터베이스를 쓰는 시험이 skip이 아니라 실패한다. 세션 픽스처가 서버에 붙어 `vector` 확장을 확인하는 시험 하나가 그것을 보인다(`.claude/rules/tests.md`, `tests/conftest.py`의 skip을 실패로 바꾸는 선례).
- [ ] pytest를 도는 CI의 `python` 잡(`.github/workflows/ci.yml`. 필수 검사 `verify`는 잡들의 결과를 모으기만 한다)이 같은 이미지를 서비스 컨테이너로 띄우고 `RAG_TEST_DATABASE_URL`을 넘긴다. 이 티켓의 PR에서 초록을 본다.
- [ ] 문서만 바뀐 커밋에서 pytest를 건너뛸지 정하고(설계 일지 `docs/journal/2026-11-09-2125-core-design.md`의 `## 다음`, `.scratch/plan-head.md` 순서 절), 정한 것과 까닭을 러너 독스트링과 일지에 남긴다. 규약 문서(`docs/constitution/operations.md`)를 바꾸면 그 문서의 개정 규칙을 따른다.
- [ ] next-session 결정표에, 이 티켓 뒤의 모든 커밋(문서 PR과 하네스 chore 포함)은 Docker가 있는 세션에서만 되고 Docker가 없는 클라우드 세션은 커밋할 수 없다는 갈래를 더한다(`.scratch/plan-head.md` 순서 절이 이 티켓에 맡겼다).
- [ ] `docs/constitution/tech.md` 테스트 칸의 마지막 문장(검사 러너가 compose를 띄우는 변경은 하네스 티켓이 core의 첫 구현 티켓 전에 한다)이 이 티켓으로 거짓이 된다. 고친 문구와 판(patch)을 사용자에게 제안하고, 승인받으면 고친 뒤 `docs/constitution/README.md`의 판을 올리고 까닭을 일지에 적는다(헌법 거버넌스. 티켓 세션은 승인 밖이라 고치지 않았다).
- [ ] 하네스를 바꿨으므로 실제 커밋 훅 실행으로 확인한다(CLAUDE.md 작업 규약 3). 검사 넷(`uv run pytest`, `uv run ruff check .`·`uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`)이 초록이다.
