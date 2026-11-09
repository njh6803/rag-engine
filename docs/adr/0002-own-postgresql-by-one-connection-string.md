---
status: accepted
date: 2026-11-09
---

# 이 서버는 자기 PostgreSQL 데이터베이스를 쓰고 연결 문자열 하나만 받는다

이 서버의 데이터(원천 설정, 문서와 조각의 메타데이터, 작업 기록, 벡터 저장소를 pgvector로 고르면 색인까지)는 이 서버의 PostgreSQL 데이터베이스에 둔다. 설정은 연결 문자열 하나이고, 스키마와 마이그레이션은 이 저장소가 맡는다. 단독 compose는 자기 PostgreSQL을 함께 띄우고, 설치 환경에 이미 PostgreSQL이 있으면 연결 문자열만 바꿔 그쪽에 붙인다(바뀜: 이력 2026-11-09 "지원하는 데이터베이스는 compose가 동봉한 PostgreSQL 18 하나다"). 다른 서비스의 데이터베이스는 읽지 않는다. 문서를 가져오는 원천으로서의 데이터베이스(db-source)는 이 결정과 별개로, 읽기 전용 계정의 커넥터다.

## Consequences

- 설치 환경의 PostgreSQL에 붙일 때는 이 서버가 쓰는 확장(벡터 저장소와 한국어 키워드 검색을 PostgreSQL로 고르면 pgvector, pg_bigm이나 PGroonga 등)이 그쪽에도 있어야 한다(바뀜: 이력 2026-11-09 "지원하는 데이터베이스는 compose가 동봉한 PostgreSQL 18 하나다"). core 설계 인터뷰가 벡터 저장소를 고를 때 이 비용을 기준에 넣는다.
- 백업과 복원(backup-upgrade)은 이 데이터베이스 하나와 색인, 원본 문서를 대상으로 한다.

## 이력

### 2026-11-09 지원하는 데이터베이스는 compose가 동봉한 PostgreSQL 18 하나다

core 설계 인터뷰에서 사용자가 "POSTgreSQL은 우리 제품의 DB로 쓰는건데?", "우리 제품의 DB로써 동작하는거고 고객사의 연동은 데이터베이스 연동으로 하는거 아니야?"라고 되물어(일지 2026-11-09-2125-core-design.md 라운드 16·17), 설치처의 기존 PostgreSQL에 붙이는 장면은 지원 범위가 아니고 고객사와의 연동은 SQL 원천 커넥터(db-source, 1.0)로 한다고 정했다. 그래서 본문의 "설치 환경에 이미 PostgreSQL이 있으면 연결 문자열만 바꿔 그쪽에 붙인다"는 지원 범위에서 빠진다. 연결 문자열은 그대로 하나이고 다른 PostgreSQL을 가리키는 것을 막지는 않지만, 지원하고 테스트하는 것은 compose가 동봉한 PostgreSQL 18(pgvector 0.8.x가 든 공식 이미지, ADR 0006)뿐이고 CI도 18 하나다. Consequences의 "설치 환경의 PostgreSQL에 붙일 때는" 항목도 같은 까닭으로 닫힌다. 벡터 저장소는 ADR 0006이 pgvector로 정했고, 테스트용 PostgreSQL은 같은 이미지를 Docker로 띄운다(`docs/constitution/tech.md` 테스트 칸).
