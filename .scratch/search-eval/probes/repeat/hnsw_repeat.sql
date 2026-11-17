-- 같은 벡터를 같은 순서로 넣은 표 둘에 HNSW 색인을 따로 지어, 같은 질의의 상위 50이 같은지 본다.
-- 제품의 검색처럼 hnsw.ef_search 를 후보 수 50 으로 둔다. 정확 스캔(색인을 끈 순차 스캔)의 상위 50과도 견준다.
--
-- search-eval 티켓 세션(2026-11-13)의 명세 검토가 처음 지어 돌렸고, 명세의 정확 스캔 항목과
-- ADR 0018 이력 2026-11-13 이 근거로 든다. 벡터는 무작위 64차원이라 실제 임베딩(bge-m3, 1024차원)에서의
-- 크기는 이 프로브가 재지 않는다.
--
-- 돌리기(테스트 PostgreSQL. 계정과 컨테이너 이름은 compose.test.yml 머리 주석):
--
--     docker exec rag-engine-test-postgres-1 psql -U rag_test -d rag_test -c "CREATE DATABASE probe_hnsw_repeat"
--     docker exec -i rag-engine-test-postgres-1 psql -U rag_test -d probe_hnsw_repeat -v ON_ERROR_STOP=1 -q \
--         < .scratch/search-eval/probes/repeat/hnsw_repeat.sql
--     docker exec rag-engine-test-postgres-1 psql -U rag_test -d rag_test -c "DROP DATABASE probe_hnsw_repeat"
--
-- 벡터는 setseed 로 정해진다. 같은 SQL 을 두 번 돌린 수가 달랐으므로(README) 행을 색인에 넣을 때의 난수는
-- setseed 를 따르지 않는 것으로 본다(pgvector 의 소스는 읽지 않았다. 어림). 빈 표에 색인을 먼저 짓고 행을
-- 나중에 넣는 것은 제품의 순서와 같다(어댑터가 판의 색인을 만든 뒤에 조각을 넣는다. 코드를 읽었다).
CREATE EXTENSION IF NOT EXISTS vector;
SELECT extversion AS pgvector FROM pg_extension WHERE extname = 'vector';
SELECT setseed(0.42);
CREATE TABLE src AS SELECT i AS id, ARRAY(SELECT random() - 0.5 FROM generate_series(1, 64) WHERE i > 0)::vector(64) AS v FROM generate_series(1, 3000) AS i;
CREATE TABLE q AS SELECT i AS id, ARRAY(SELECT random() - 0.5 FROM generate_series(1, 64) WHERE i > 0)::vector(64) AS v FROM generate_series(1, 100) AS i;
CREATE TABLE a (id int, v vector(64));
CREATE TABLE b (id int, v vector(64));
CREATE INDEX ON a USING hnsw (v vector_cosine_ops);
CREATE INDEX ON b USING hnsw (v vector_cosine_ops);
INSERT INTO a SELECT id, v FROM src ORDER BY id;
INSERT INTO b SELECT id, v FROM src ORDER BY id;
SET enable_seqscan = off;
SET hnsw.ef_search = 50;
CREATE TABLE ra AS SELECT q.id AS qid, ARRAY(SELECT a.id FROM a ORDER BY a.v <=> q.v LIMIT 50) AS ids FROM q;
CREATE TABLE rb AS SELECT q.id AS qid, ARRAY(SELECT b.id FROM b ORDER BY b.v <=> q.v LIMIT 50) AS ids FROM q;
SET enable_seqscan = on;
SET enable_indexscan = off;
CREATE TABLE re AS SELECT q.id AS qid, ARRAY(SELECT s.id FROM src s ORDER BY s.v <=> q.v LIMIT 50) AS ids FROM q;
SELECT count(*) FILTER (WHERE ra.ids <> rb.ids) AS lists_differ_a_b, count(*) FILTER (WHERE ra.ids[1:10] <> rb.ids[1:10]) AS top10_differ_a_b, count(*) FILTER (WHERE ra.ids <> re.ids) AS lists_differ_a_exact FROM ra JOIN rb USING (qid) JOIN re USING (qid);
-- 위 줄은 순서까지 견준다. 아래 줄은 순서를 지운 집합으로 견주고, 두 표의 상위 50 이 함께 가진 수(겹침)의
-- 최솟값과 평균을 낸다. 리랭크 기록이 덮어야 하는 것은 후보의 집합이다. 첫 재실행의 출력
-- hnsw_repeat_out.txt 는 이 줄을 더하기 전에 돌렸고, hnsw_repeat_set_out.txt 는 더한 뒤에 돌렸다.
SELECT count(*) FILTER (WHERE x.sa <> x.sb) AS sets_differ_a_b, count(*) FILTER (WHERE x.sa <> x.se) AS sets_differ_a_exact, min(x.overlap) AS min_overlap_a_b, round(avg(x.overlap), 2) AS mean_overlap_a_b FROM (SELECT ARRAY(SELECT unnest(ra.ids) ORDER BY 1) AS sa, ARRAY(SELECT unnest(rb.ids) ORDER BY 1) AS sb, ARRAY(SELECT unnest(re.ids) ORDER BY 1) AS se, cardinality(ARRAY(SELECT unnest(ra.ids) INTERSECT SELECT unnest(rb.ids))) AS overlap FROM ra JOIN rb USING (qid) JOIN re USING (qid)) AS x;
