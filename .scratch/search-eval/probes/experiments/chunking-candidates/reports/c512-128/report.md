# 검색 평가 보고서: public-docs

- 보고서 판: 1.0.0
- 묶음 판: 1.0.0, 내용 해시: `8b24cd80735ecac0472f1420e0f4416904a88cba985a10c1b66bda0fe6247581`
- 문서 46개, 질문 155개, 질의 310개
- 실행 시각: 2026-11-16T19:56:05.989199+00:00, 커밋: a372cd61f4153e81fa494689160da283442e2553
- 잰 단계: vector, keyword, fused

## 구성

| 칸 | 값 |
|---|---|
| embedding_model | BAAI/bge-m3 |
| embedding_dimensions | 1024 |
| reranker_model | BAAI/bge-reranker-v2-m3 |
| chunking | strategy=structure_first, max_tokens=512, overlap_tokens=128 |
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
| chunking_hash | 051b1cca0ef8113b1accd14f50e67fe67eae5217a3f1864cfefef51ddbaa5052 |
| tokenizer_version | kiwipiepy 0.24.1; kiwipiepy_model 0.24.0; keyword-rules 1 |
| chunks | 2444 |

## 질의 목록 `human`

| 단계 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 |
|---|---|---|---|---|---|---|---|---|---|
| vector | 155 | 0.587 | 0.826 | 0.910 | 0.961 | 0.718 | 0.942 | 0.762 | 1 |
| keyword | 155 | 0.239 | 0.445 | 0.516 | 0.639 | 0.359 | 0.605 | 0.406 | 1 |
| fused | 155 | 0.452 | 0.697 | 0.826 | 0.916 | 0.598 | 0.890 | 0.661 | 1 |

## 질의 목록 `keyword`

| 단계 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 |
|---|---|---|---|---|---|---|---|---|---|
| vector | 155 | 0.510 | 0.742 | 0.806 | 0.877 | 0.636 | 0.861 | 0.677 | 3 |
| keyword | 155 | 0.284 | 0.510 | 0.581 | 0.690 | 0.405 | 0.649 | 0.453 | 1 |
| fused | 155 | 0.477 | 0.690 | 0.774 | 0.877 | 0.607 | 0.855 | 0.661 | 1 |

## 유형 표지별 지표 (단계 fused)

| 질의 목록 | 표지 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 |
|---|---|---|---|---|---|---|---|---|---|---|
| human | multi_document | 26 | 0.462 | 0.731 | 0.885 | 1.000 | 0.641 | 0.846 | 0.640 | 1 |
| human | no_context | 32 | 0.469 | 0.688 | 0.812 | 0.844 | 0.596 | 0.828 | 0.647 | 0 |
| human | table | 34 | 0.382 | 0.529 | 0.706 | 0.765 | 0.494 | 0.750 | 0.557 | 0 |
| keyword | multi_document | 26 | 0.423 | 0.731 | 0.808 | 0.885 | 0.584 | 0.750 | 0.588 | 1 |
| keyword | no_context | 32 | 0.406 | 0.625 | 0.688 | 0.812 | 0.541 | 0.812 | 0.603 | 0 |
| keyword | table | 34 | 0.382 | 0.529 | 0.706 | 0.794 | 0.494 | 0.765 | 0.557 | 0 |

## 필터가 붙은 질의 (단계 fused)

| 질의 목록 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 | 벡터 후보가 모자란 질의 | 모자란 비율 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| human | 20 | 0.500 | 0.700 | 0.850 | 1.000 | 0.645 | 1.000 | 0.729 | 0 | 0 | 0.000 |

## 놓친 질의 32개

| 탈락 지점 | 질의 수 |
|---|---|
| no_matching_chunk | 0 |
| not_in_candidates | 0 |
| lost_in_fusion | 32 |
| lost_in_rerank | 0 |

낱말 겹침이 0인 놓친 질의: 9개

| 질의 목록 | 기대 근거 | 탈락 지점 | 낱말 겹침 |
|---|---|---|---|
| human | priv-05 | lost_in_fusion | 0.000 |
| human | priv-12 | lost_in_fusion | 0.125 |
| human | open-02 | lost_in_fusion | 0.286 |
| human | open-04 | lost_in_fusion | 0.200 |
| human | open-13 | lost_in_fusion | 0.000 |
| human | open-18 | lost_in_fusion | 0.000 |
| human | cult-19 | lost_in_fusion | 0.000 |
| human | cult-20 | lost_in_fusion | 0.000 |
| human | cult-21 | lost_in_fusion | 0.000 |
| human | cult-23 | lost_in_fusion | 0.250 |
| human | cons-06 | lost_in_fusion | 0.222 |
| human | radi-02 | lost_in_fusion | 0.273 |
| human | radi-08 | lost_in_fusion | 0.417 |
| keyword | priv-05 | lost_in_fusion | 0.000 |
| keyword | priv-12 | lost_in_fusion | 0.143 |
| keyword | priv-22 | lost_in_fusion | 0.333 |
| keyword | open-04 | lost_in_fusion | 0.500 |
| keyword | open-13 | lost_in_fusion | 0.167 |
| keyword | cult-01 | lost_in_fusion | 0.600 |
| keyword | cult-06 | lost_in_fusion | 0.600 |
| keyword | cult-15 | lost_in_fusion | 0.600 |
| keyword | cult-19 | lost_in_fusion | 0.000 |
| keyword | cult-20 | lost_in_fusion | 0.000 |
| keyword | cult-23 | lost_in_fusion | 0.286 |
| keyword | labr-07 | lost_in_fusion | 0.714 |
| keyword | labr-23 | lost_in_fusion | 0.375 |
| keyword | labr-26 | lost_in_fusion | 0.333 |
| keyword | cons-06 | lost_in_fusion | 0.286 |
| keyword | cons-09 | lost_in_fusion | 0.375 |
| keyword | radi-07 | lost_in_fusion | 0.333 |
| keyword | radi-08 | lost_in_fusion | 0.444 |
| keyword | radi-15 | lost_in_fusion | 0.500 |

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
