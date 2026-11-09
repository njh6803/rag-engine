---
status: accepted
date: 2026-11-09
---

# 데이터 접근은 SQLAlchemy 2.1 Core 비동기(psycopg 3)로 하고, 마이그레이션은 alembic이 한다

PostgreSQL(ADR 0002)에 붙는 드라이버와 마이그레이션 도구를 정한다. 처음 추천은 psycopg 3 직접 호출과 손으로 쓰는 SQL 마이그레이션이었으나, 사용자가 SQLAlchemy 2.1 Core와 alembic을 비동기로 쓸 수 있는지 물었고 프로브로 확인한 뒤 그쪽으로 정했다. `sqlalchemy[asyncio]` 2.1.x의 비동기 엔진을 `postgresql+psycopg` 방언으로 만들고(psycopg 3.3.x, LGPL-3.0-only, py.typed), 매핑은 ORM이 아니라 Core(`Table`, `select`, 텍스트 SQL)로 쓰며, `pgvector`의 SQLAlchemy 타입으로 벡터 열을 선언하고, 마이그레이션은 alembic(async 템플릿)이 맡는다. 프로브 `.scratch/core/probes/sqlalchemy-async/probe.py`는 비동기 방언 생성(`is_async True`), alembic의 async 템플릿, 네 패키지의 py.typed, pyright 0 오류(`pyright_out.json`)를 확인했고 greenlet 3.5.6(MIT AND PSF-2.0)이 따라오는 것을 보았다(출력 `probe_out.txt`).

까닭. alembic이 스키마 변경의 이력과 업그레이드 경로를 맡아 주어 색인 판의 스키마 요소(ADR 0008)와 작업 표(ADR 0009), 토큰 표(ADR 0014)의 변경을 한 이력으로 관리한다. Core는 SQL을 숨기지 않아 pgvector의 거리 연산자, `FOR UPDATE SKIP LOCKED`, 한 SQL의 RRF 같은 문장을 그대로 쓰면서도 표 정의와 타입을 파이썬에 둔다. 네 패키지가 모두 py.typed라 원칙 II 아래서 스텁 없이 쓴다.

## Considered Options

- psycopg 3 직접 + 손 마이그레이션(처음 추천): 의존성이 가장 적지만 스키마 변경의 이력과 순서를 우리가 관리해야 한다.
- asyncpg 0.32: 빠르지만 py.typed가 없어 스텁이 필요하다.
- SQLAlchemy ORM 매핑: 선언형 모델이 편하지만 strict 타입 검사에서 마찰이 있고(어림) 조각 표와 벡터 질의는 어차피 SQL에 가깝다.

## Consequences

- greenlet 의존이 든다. Windows에서 psycopg 비동기는 기본 ProactorEventLoop과 호환되지 않아 Selector 이벤트 루프가 필요하므로(psycopg 3 문서 비동기 절의 경고를 읽음. 프로브는 접속하지 않아 재지 않았다) 개발 기계의 테스트 설정에 반영한다.
- `rag-engine migrate`가 `alembic upgrade head`를 돌리고, 서버 기동 때 자동으로 돌리지 않는다. compose는 서버 앞에 한 번 도는 마이그레이션 서비스를 둔다.
- 엔진은 `create_async_engine(…, hide_parameters=True)`로 만든다. SQLAlchemy의 `StatementError`(그 하위의 `DBAPIError`도)는 메시지에 `[SQL: …]`와 `[parameters: …]`를 붙이고, 이 옵션이 참일 때만 뒤를 `[SQL parameters hidden due to hide_parameters=True]`로 바꾼다(2.1.8 `sqlalchemy/exc.py`의 `StatementError._sql_message`를 프로브 가상환경에서 읽음). 바인딩 값에는 조각 본문과 검색 질의가 들어 원칙 V와 ADR 0004의 대상이다. 로그 필드에 예외를 어떻게 싣는지는 ADR 0015다.
- `uv run --with`가 Windows에서 greenlet 휠 설치에 실패한 일(os error 32)이 있어 프로브는 임시 가상환경으로 돌렸다. 저장소 의존성으로 들이면 `uv sync`가 같은 휠을 설치하므로 첫 티켓에서 다시 확인한다.
