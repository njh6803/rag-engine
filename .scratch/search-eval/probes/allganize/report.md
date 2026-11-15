# 검색 평가 보고서: allganize-rag-ko

- 보고서 판: 1.0.0
- 묶음 판: 1.0.0, 내용 해시: `b4e20d227759c50e128a46fb27df87fb0ffcb5b2592d4c04f39022b6452559e6`
- 문서 41개, 질문 174개, 질의 174개
- 실행 시각: 2026-11-15T09:49:22.533303+00:00, 커밋: 63fb219afaac8bdecf3adfd49d51c5cd1de9fdb9
- 잰 단계: vector, keyword, fused

## 구성

| 칸 | 값 |
|---|---|
| embedding_model | BAAI/bge-m3 |
| embedding_dimensions | 1024 |
| reranker_model | BAAI/bge-reranker-v2-m3 |
| chunking | strategy=structure_first, max_tokens=512, overlap_tokens=64 |
| search_candidates | 50 |
| tei_version | 1.9.4 |
| judge_model | claude-opus-5-5 |
| judge_prompt_version | 1 |

## 색인

| 칸 | 값 |
|---|---|
| schema_version | 1 |
| embedding_model | BAAI/bge-m3 |
| embedding_dimensions | 1024 |
| chunking_hash | 4181387325cdee16cb3a9b25c5b2c5f453f52a1088d781afe6dd61edfd1e5528 |
| tokenizer_version | kiwipiepy 0.24.1; kiwipiepy_model 0.24.0; keyword-rules 1 |
| chunks | 1197 |

## 질의 목록 `human`

| 단계 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 |
|---|---|---|---|---|---|---|---|---|---|
| vector | 174 | 0.580 | 0.759 | 0.787 | 0.828 | 0.672 | 0.828 | 0.710 | 0 |
| keyword | 174 | 0.460 | 0.626 | 0.661 | 0.736 | 0.555 | 0.736 | 0.598 | 0 |
| fused | 174 | 0.603 | 0.736 | 0.770 | 0.822 | 0.679 | 0.822 | 0.714 | 0 |

## 유형 표지별 지표 (단계 fused)

| 질의 목록 | 표지 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 |
|---|---|---|---|---|---|---|---|---|---|---|
| human | figure | 42 | 0.357 | 0.452 | 0.476 | 0.548 | 0.420 | 0.548 | 0.450 | 0 |
| human | table | 28 | 0.607 | 0.786 | 0.821 | 0.893 | 0.709 | 0.893 | 0.754 | 0 |

## 필터가 붙은 질의 (단계 fused)

| 질의 목록 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 | 벡터 후보가 모자란 질의 | 모자란 비율 |
|---|---|---|---|---|---|---|---|---|---|---|---|

## 놓친 질의 31개

| 탈락 지점 | 질의 수 |
|---|---|
| no_matching_chunk | 4 |
| not_in_candidates | 16 |
| lost_in_fusion | 11 |
| lost_in_rerank | 0 |

낱말 겹침이 0인 놓친 질의: 0개

| 질의 목록 | 기대 근거 | 탈락 지점 | 낱말 겹침 |
|---|---|---|---|
| human | finance-001 | not_in_candidates | 없음 |
| human | finance-002 | not_in_candidates | 없음 |
| human | finance-003 | not_in_candidates | 없음 |
| human | finance-004 | lost_in_fusion | 없음 |
| human | finance-005 | not_in_candidates | 없음 |
| human | finance-006 | not_in_candidates | 없음 |
| human | finance-007 | not_in_candidates | 없음 |
| human | finance-008 | not_in_candidates | 없음 |
| human | finance-021 | lost_in_fusion | 없음 |
| human | finance-022 | not_in_candidates | 없음 |
| human | finance-023 | not_in_candidates | 없음 |
| human | finance-024 | not_in_candidates | 없음 |
| human | finance-025 | lost_in_fusion | 없음 |
| human | finance-026 | not_in_candidates | 없음 |
| human | finance-027 | not_in_candidates | 없음 |
| human | finance-028 | not_in_candidates | 없음 |
| human | public-001 | lost_in_fusion | 없음 |
| human | public-030 | lost_in_fusion | 없음 |
| human | public-035 | no_matching_chunk | 없음 |
| human | public-036 | no_matching_chunk | 없음 |
| human | medical-003 | lost_in_fusion | 없음 |
| human | medical-009 | no_matching_chunk | 없음 |
| human | medical-020 | no_matching_chunk | 없음 |
| human | medical-023 | not_in_candidates | 없음 |
| human | law-004 | lost_in_fusion | 없음 |
| human | law-009 | lost_in_fusion | 없음 |
| human | law-020 | lost_in_fusion | 없음 |
| human | law-024 | lost_in_fusion | 없음 |
| human | law-027 | not_in_candidates | 없음 |
| human | law-028 | not_in_candidates | 없음 |
| human | law-042 | lost_in_fusion | 없음 |

## 사람 판정 (확인된 줄만)

| 까닭 | 수 |
|---|---|
| multi_document | 0 |
| no_context | 0 |
| other | 0 |
| table_or_figure | 0 |
| vocabulary | 0 |

## LLM 관련성 판정(참고 숫자)

숫자가 없다: judgments.jsonl이 없다. judge로 판정을 쌓은 뒤에 run을 다시 친다

## 추론 기록

| 칸 | 값 |
|---|---|
| 읽은 수 | 0 |
| 새로 계산한 수 | 0 |
