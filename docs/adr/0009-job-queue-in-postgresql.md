---
status: accepted
date: 2026-11-09
---

# 작업 대기열은 PostgreSQL 작업 표로 직접 구현한다(SKIP LOCKED + LISTEN/NOTIFY)

수집 작업자는 검색 서버와 다른 프로세스다(ADR 0007). 둘 사이의 작업 대기열은 브로커를 들이지 않고 PostgreSQL 작업 표로 직접 만든다. 작업 표(종류, 문서 ID, 상태, 시도 횟수, 예약 시각, 임대 만료, 실패 사유)는 alembic 마이그레이션에 들고, 작업자는 `SELECT … FOR UPDATE SKIP LOCKED`로 작업을 꺼내 임대하며, 서버는 `NOTIFY`로 작업자를 깨우고 작업자는 `LISTEN`과 주기 폴링을 함께 쓴다. 실패는 지수 백오프로 다시 예약하고, 같은 문서의 대기 작업은 부분 유일 인덱스로 하나만 둔다. 응용 층은 `JobQueue` 포트로만 다룬다.

까닭은 셋이다. 단독 compose의 컨테이너가 이미 다섯이라 브로커 하나(RabbitMQ 4 이미지 131MB, 프로브 `facts/rabbitmq_facts.py`)를 더 얹으면 운영 항목과 장애 지점이 늘고, 폐쇄망 설치처가 다룰 것이 하나 더 생긴다. 작업과 문서 상태가 같은 데이터베이스에 있어 문서의 새 판을 준비 상태로 두는 것과 작업을 넣는 것이 한 트랜잭션이다. 수집 규모(문서 수만, 작업자 몇)는 PostgreSQL 대기열로 충분하다(어림). 사용자가 RabbitMQ로 바로 갈지 두 번 물었고, 지금 규모에서는 과한 설계라는 설명 뒤에 이 안을 골랐다.

## Considered Options

- RabbitMQ(aio-pika Apache-2.0 또는 pika BSD-3): 브로커가 재시도와 라우팅을 맡지만, 작업 상태와 진행률은 어차피 데이터베이스에 두어야 해 작업 표가 outbox로 남아 저장이 둘이 된다.
- procrastinate 3.10(MIT): 같은 PostgreSQL 방식의 라이브러리지만 자기 마이그레이션 38개(프로브 `facts/procrastinate_migrations.py`)와 연결 풀을 들여와 우리 alembic 이력과 두 갈래가 된다.
- pgqueuer 1.6(MIT): pydantic-settings와 typer 의존이 우리 설정 층과 겹친다.

## Consequences

- 작업자가 늘면 폴링과 `NOTIFY` 비용이 데이터베이스에 든다. 작업자 수와 폴링 주기는 명세가 정한다.
- 나중에 RabbitMQ 어댑터를 끼우면 작업 표가 outbox가 되고 `JobQueue` 포트는 그대로다.
- 수집의 진행률은 MCP가 아니라 관리 API가 작업 표를 읽어 보여 준다(ADR 0001).
- 소프트 삭제의 정리(ADR 0013)와 재색인(ADR 0008)도 같은 대기열의 작업이다.
