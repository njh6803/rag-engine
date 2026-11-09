source https://raw.githubusercontent.com/pgvector/pgvector/v0.8.7/README.md lines 1361
--- /::vector\(/ hits=7
  649: CREATE INDEX ON items USING hnsw ((subvector(embedding, 1, 3)::vector(3)) vector_cosine_ops);
  655: SELECT * FROM items ORDER BY subvector(embedding, 1, 3)::vector(3) <=> subvector('[1,2,3,4,5]'::vector, 1, 3) LIMIT 5;
  662: SELECT * FROM items ORDER BY subvector(embedding, 1, 3)::vector(3) <=> subvector('[1,2,3,4,5]'::vector, 1, 3) LIMIT 20
  842: CREATE INDEX ON embeddings USING hnsw ((embedding::vector(3)) vector_l2_ops) WHERE (model_id = 123);
  848: SELECT * FROM embeddings WHERE model_id = 123 ORDER BY embedding::vector(3) <-> '[3,1,2]' LIMIT 5;
  871: CREATE INDEX ON items USING hnsw ((embedding::vector(3)) vector_l2_ops);
  877: SELECT * FROM items ORDER BY embedding::vector(3) <-> '[3,1,2]' LIMIT 5;
--- /iterative_scan/ hits=4
  453: SET hnsw.iterative_scan = strict_order;
  487: SET hnsw.iterative_scan = strict_order;
  493: SET hnsw.iterative_scan = relaxed_order;
  495: SET ivfflat.iterative_scan = relaxed_order;
--- /max_scan_tuples/ hits=3
  480: With approximate indexes, queries with filtering can return less results since filtering is applied *after* the index is scanned. Starting with 0.8.0, you can e
  527: SET hnsw.max_scan_tuples = 20000;
  538: Note: Try increasing this if increasing `hnsw.max_scan_tuples` does not improve recall
--- /scan_mem_multiplier/ hits=1
  535: SET hnsw.scan_mem_multiplier = 2;
--- /ef_search/ hits=4
  275: SET hnsw.ef_search = 100;
  284: SET LOCAL hnsw.ef_search = 100;
  450: With approximate indexes, filtering is applied *after* the index is scanned. If a condition matches 10% of rows, with HNSW and the default `hnsw.ef_search` of 4
  935: Results are limited by the size of the dynamic candidate list (`hnsw.ef_search`), which is 40 by default. There may be even less results due to dead tuples or f
--- /vector_cosine_ops/ hits=3
  229: CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops);
  363: CREATE INDEX ON items USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
  649: CREATE INDEX ON items USING hnsw ((subvector(embedding, 1, 3)::vector(3)) vector_cosine_ops);
--- /CREATE INDEX .* WHERE/ hits=2
  459: CREATE INDEX ON items USING hnsw (embedding vector_l2_ops) WHERE (category_id = 123);
  842: CREATE INDEX ON embeddings USING hnsw ((embedding::vector(3)) vector_l2_ops) WHERE (model_id = 123);
--- /partial index/ hits=1
  456: If filtering by only a few distinct values, consider [partial indexing](https://www.postgresql.org/docs/current/indexes-partial.html).
--- /does not have dimensions|without dimensions|untyped/ hits=0
--- /Filtering/ hits=6
  424: ## Filtering
  450: With approximate indexes, filtering is applied *after* the index is scanned. If a condition matches 10% of rows, with HNSW and the default `hnsw.ef_search` of 4
  456: If filtering by only a few distinct values, consider [partial indexing](https://www.postgresql.org/docs/current/indexes-partial.html).
  462: If filtering by many different values, consider [partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html).
  480: With approximate indexes, queries with filtering can return less results since filtering is applied *after* the index is scanned. Starting with 0.8.0, you can e
  935: Results are limited by the size of the dynamic candidate list (`hnsw.ef_search`), which is 40 by default. There may be even less results due to dead tuples or f
--- context 836-850
  836: CREATE TABLE embeddings (model_id bigint, item_id bigint, embedding vector, PRIMARY KEY (model_id, item_id));
  837: ```
  838: 
  839: However, you can only create indexes on rows with the same number of dimensions (using [expression](https://www.postgresql.org/docs/current/indexes-expressional.html) and [partial](https://www.postgre
  840: 
  841: ```sql
  842: CREATE INDEX ON embeddings USING hnsw ((embedding::vector(3)) vector_l2_ops) WHERE (model_id = 123);
  843: ```
  844: 
  845: and query with:
  846: 
  847: ```sql
  848: SELECT * FROM embeddings WHERE model_id = 123 ORDER BY embedding::vector(3) <-> '[3,1,2]' LIMIT 5;
  849: ```
  850: 
--- context 930-937
  930: ALTER TABLE items ALTER COLUMN embedding SET STORAGE PLAIN;
  931: ```
  932: 
  933: #### Why are there less results for a query after adding an HNSW index?
  934: 
  935: Results are limited by the size of the dynamic candidate list (`hnsw.ef_search`), which is 40 by default. There may be even less results due to dead tuples or filtering conditions in the query. Enabli
  936: 
  937: Also, note that `NULL` vectors are not indexed (as well as zero vectors for cosine distance).
