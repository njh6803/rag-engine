# ADR 색인

번호열은 하나다. 지역 결정도 여기 넣고 제목에 범위를 적는다. 형식은 domain-modeling 스킬의 ADR-FORMAT(짧게, 결정과 이유). 새 ADR을 쓰면 이 표에 한 줄 더한다.

| 번호 | 제목 | 상태 | 날짜 |
|---|---|---|---|
| [0001](0001-mcp-opens-read-tools-only.md) | MCP로는 읽기 도구만 열고, 쓰기는 관리 API와 수집 API로 나눈다 | accepted | 2026-11-09 |
| [0002](0002-own-postgresql-by-one-connection-string.md) | 이 서버는 자기 PostgreSQL 데이터베이스를 쓰고 연결 문자열 하나만 받는다 | accepted | 2026-11-09 |
| [0003](0003-three-plugin-slots-and-private-transforms.md) | 수집 파이프라인에 플러그인 자리 셋을 두고, 설치처별 변환 플러그인은 설치처의 비공개 저장소에 둔다 | accepted | 2026-11-09 |
| [0004](0004-keep-latency-not-questions.md) | 검색 질문의 내용을 남기지 않고 지연 시간만 남긴다 | accepted | 2026-11-09 |
| [0005](0005-rest-and-mcp-in-one-fastapi-app.md) | REST와 MCP는 한 FastAPI 앱이 열고, MCP는 공식 SDK 2.x의 Streamable HTTP를 `/mcp`에 붙인다 | accepted | 2026-11-09 |
