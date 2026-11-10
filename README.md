# rag-engine

MCP를 쓰는 어떤 클라이언트에서도 쓸 수 있는 설치형 문서 검색 서버(지식베이스)다. 여러 원천에서 문서를 수집하고 색인해서, 근거 위치와 갱신일이 붙은 검색 결과를 MCP 읽기 도구로 돌려준다. 답을 생성하지는 않는다. 제품 의도와 성공의 정의는 [docs/PRD.md](docs/PRD.md)에 있다.

지금은 core를 쌓는 중이다. HTTP 서버가 `/health`(인증 밖), 토큰으로 닫힌 MCP 끝점(`/mcp`, 아직 도구는 없다), 토큰 관리 API를 연다. 첫 기능은 core이고, 순서와 범위는 [.scratch/plan.md](.scratch/plan.md)에 있다.

## 판

이 서버의 판은 semver다(`pyproject.toml`의 `version`). 첫 공개 판 0.1 전에는 `0.0.0`이다. 헌법의 판은 따로이고 [docs/constitution/README.md](docs/constitution/README.md)에 있다.

## 개발

```bash
uv sync
uv run pre-commit install
uv run rag-engine serve          # http://127.0.0.1:8000/health, MCP 는 http://127.0.0.1:8000/mcp (토큰 필요)
```

`serve`는 환경 변수 `RAG_DATABASE_URL`, `RAG_DATA_DIR`, `RAG_ALLOWED_HOSTS` 셋이 없으면 종료 코드 1로 끝난다(`.env`에 적어도 된다). 처음에는 `rag-engine migrate`로 스키마를 올리고 `rag-engine bootstrap-token`으로 첫 admin 토큰을 받는다.

검증 명령은 `CLAUDE.md`의 검증 명령 칸이 원천이다. 테스트는 Docker로 띄운 PostgreSQL(`compose.test.yml`)이 필요하다. 커밋 훅의 검사 러너(`uv run python tools/run_checks.py`)가 없으면 띄우고, 손으로 `uv run pytest`를 칠 때는 먼저 띄운다.

```bash
docker compose -f compose.test.yml up -d --wait
```

```bash
RAG_TEST_DATABASE_URL=postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test uv run pytest
```

PowerShell에서는 이렇게 친다.

```powershell
$env:RAG_TEST_DATABASE_URL = "postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test"; uv run pytest
```

컨테이너 이미지:

```bash
docker build -t rag-engine .
docker run --rm -p 8000:8000 \
  -e RAG_DATABASE_URL=postgresql://사용자:비밀번호@호스트:5432/rag \
  -e RAG_DATA_DIR=/data -e RAG_ALLOWED_HOSTS=localhost rag-engine
```

## 트리

```
src/rag_engine/
  main.py      관리 명령(argparse). `rag-engine serve` 가 HTTP 서버를 띄우고 `rag-engine migrate` 가 스키마를 올려 기본 레코드를 보장하며 `rag-engine bootstrap-token` 이 첫 admin 토큰을 낸다
  server/      FastAPI 앱(app.py)과 출력 모델. /health 와 MCP Streamable HTTP(/mcp)를 한 앱이 연다(ADR 0005).
               MCP 출력 모델(tool_models.py), 수집 API 모델(ingest_models.py), Problem Details(problems.py, problem_response.py),
               요청 문맥 미들웨어(request_context.py: 요청 ID, 로그), 인증 미들웨어(auth.py), 토큰 관리 API(token_api.py)
  worker/      작업자 조립(슬라이스 1이 채운다)
  adapters/    포트의 구현. settings.py(설정 객체), log_format.py(JSON Lines·text 로그 포매터), index_elements.py(색인 판 요소), tei.py(임베딩 서버 어댑터), kiwi.py(키워드 토큰과 문장 분리), chunking.py(구조 우선 청킹), utf8_offsets.py(바이트 오프셋 변환), postgres/ 에 표 정의(tables.py), alembic 첫 판(migrations/), 작업 단위와 Catalog·VectorIndex·TokenStore 어댑터, migrate 와 bootstrap-token 의 조립(bootstrap.py)
  app/         유스케이스. default_records.py(migrate 의 기본 레코드 보장), tokens.py(토큰 발급·인증·폐기)
  domain/      엔티티, 포트 Protocol, 예외와 오류 코드, 파서 인터페이스, 색인에 넣는 글을 짓는 함수(index_text.py). 서드파티는 uuid6만 쓴다(금지 목록은 pyproject.toml의 import-linter 계약)
typings/       서드파티 타입 스텁. kiwipiepy에 py.typed가 없어 쓰는 면만 적었다(ADR 0006)
tests/
  contract/    MCP 계약 시험. 공식 SDK 클라이언트로 HTTP 접속해 도구 목록을 본다
  domain/      도메인 값 객체, 오류 코드, 파서 인터페이스의 시험
  server/      출력 모델, Problem Details, 인증, 토큰 관리 API, 요청 ID와 로그, MCP 전송 설정의 시험. 실제 uvicorn 서버에 HTTP로 접속한다
  adapters/    설정, 색인 판 요소, 작업 단위와 Catalog·VectorIndex 어댑터, alembic 첫 판이 만드는 색인 형식, TEI 어댑터, Kiwi 키워드, 구조 우선 청킹, 오프셋 변환의 시험. 일부는 테스트 PostgreSQL이 필요하다
  app/         유스케이스(토큰 발급·인증·폐기)의 시험. 테스트 PostgreSQL이 필요하다
  support/     시험이 끼우는 부품. TEI 스텁 서버(tei_stub.py)와 글자 수로 세는 가짜 토큰 세기(token_meters.py)
  conftest.py  테스트 PostgreSQL의 템플릿 데이터베이스(기본 레코드가 든 복제본 `seeded_database_url`), 설정 객체 공장 `make_settings`,
               실제 uvicorn 서버를 띄우는 `run_server`와 `server`, 서버 로그를 읽는 `log_capture`
  harness.py   시험이 함께 쓰는 값 객체(`RunningServer`, `LogCapture`)와 보조 함수. 시험은 `conftest`를 직접 import하지 않고 여기서 가져온다
  tools/       하네스 도구의 시험
compose.test.yml  테스트용 PostgreSQL(pgvector, 운영과 같은 이미지 판). 검사 러너가 없으면 띄운다
tools/         훅, 검사, 검사 러너. 규약은 .claude/rules/tools.md
docs/          헌법, ADR, PRD, 에이전트 문서, 일지
.scratch/      로컬 마크다운 이슈 트래커(기능 계획, 티켓, 회고 대기열)
```

아직 없는 것은 [.scratch/plan.md](.scratch/plan.md)의 목표 배치에 있다. 그 글의 원천은 손 파일 `.scratch/plan-head.md`다.

## 원천 표

사실 하나에 원천 하나. 다른 문서는 이 원천을 가리키기만 하고 요약하지 않는다. 두 곳이 다르면 원천이 맞고 나머지가 버그다.

| 사실 | 원천 | 비고 |
|---|---|---|
| 원칙과 거버넌스 | `docs/constitution/principles.md` | `CLAUDE.md`가 임포트 |
| 스택과 의존성의 결정 | `docs/constitution/tech.md` | 구현은 `pyproject.toml`과 `Dockerfile`. 둘이 다르면 구현을 맞추거나 ADR |
| 검증·운영 규약 | `docs/constitution/operations.md` | 검증 명령은 `CLAUDE.md`, 실행은 `.pre-commit-config.yaml`(커밋마다 도는 검사는 그것이 부르는 `tools/run_checks.py`의 `CHECKS`)과 `.github/workflows/ci.yml`. 명령이 바뀌면 넷 다. 워크플로 감사의 설정은 `.github/zizmor.yml` |
| 제품 의도와 성공의 정의 | `docs/PRD.md` | |
| 용어 | `GLOSSARY.md` | 피할 말 포함. 첫 용어가 정해질 때 생긴다 |
| 결정과 이유 | `docs/adr/`, 색인 `docs/adr/README.md` | 헌법과 rules는 번호로 인용만 |
| 판단 기준(리뷰) | `CODING_STANDARDS.md` | 더할지는 retro 스킬 4단계가 판정 |
| 리뷰 파이프라인(누가 언제 무엇을) | `docs/constitution/operations.md` | 봇 설정은 `.coderabbit.yaml`과 `.github/workflows/claude-code-review.yml`. 기준은 CODING_STANDARDS |
| 디렉터리별 규칙 | `.claude/rules/*.md` | 해당 파일을 Read 도구로 열 때만 실림 |
| 지침의 로드 시점 표 | `CLAUDE.md` 교정 루프 절 | |
| 훅과 검사의 등록 | `.claude/settings.json`, `.pre-commit-config.yaml` | 훅·검사의 규약은 `.claude/rules/tools.md` |
| 현재 구조 | 코드 | 이 README의 트리는 안내 |
| 미래 배치 | `.scratch/plan-head.md` | 손으로 쓴다. `.scratch/plan.md`의 머리에 그대로 붙는다 |
| 기능 순서, 슬라이스, 막는 기능, 상태 | 기능 계획 `.scratch/<slug>/plan.md`와 그 폴더의 티켓 | `.scratch/plan.md`는 `uv run python tools/plan_table.py`가 만든 생성 파일이라 손으로 고치지 않는다. 제품 기능만. 하네스 티켓의 상태는 티켓의 `Status:` |
| 기능 계획, 명세, 티켓 | `.scratch/<slug>/` | harness 티켓은 `.scratch/harness/issues/`. 규약은 `docs/agents/issue-tracker.md` |
| 회고가 낸 미반영 후보 | `.scratch/retro-queue/` | 모양과 규칙은 그 폴더의 `README.md` |
| 킥오프의 입력과 진행 | `.scratch/kickoff-input.md`, `.scratch/kickoff.md` | 킥오프 뒤에는 기록이다 |
| 설치된 스킬과 해시 | `skills-lock.json` | |
