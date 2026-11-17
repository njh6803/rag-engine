# 검색 평가 보고서: public-docs

- 보고서 판: 1.0.0
- 묶음 판: 1.0.0, 내용 해시: `8847976a2f01436345a6d83dc7d60ccd3d4899854079c289bb20f5fc0cd939be`
- 문서 46개, 질문 155개, 질의 310개
- 실행 시각: 2026-11-16T18:59:04.808928+00:00, 커밋: a372cd61f4153e81fa494689160da283442e2553
- 잰 단계: vector, keyword, fused

## 구성

| 칸 | 값 |
|---|---|
| embedding_model | BAAI/bge-m3 |
| embedding_dimensions | 1024 |
| reranker_model | BAAI/bge-reranker-v2-m3 |
| chunking | strategy=structure_first, max_tokens=256, overlap_tokens=32 |
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
| chunking_hash | a722efd5c56b4d3f46a0efddf0a769dfcf05709664e929982bc345cf144dc106 |
| tokenizer_version | kiwipiepy 0.24.1; kiwipiepy_model 0.24.0; keyword-rules 1 |
| chunks | 4442 |

## 질의 목록 `human`

| 단계 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 |
|---|---|---|---|---|---|---|---|---|---|
| vector | 155 | 0.574 | 0.800 | 0.852 | 0.929 | 0.696 | 0.894 | 0.728 | 1 |
| keyword | 155 | 0.200 | 0.342 | 0.458 | 0.568 | 0.303 | 0.537 | 0.352 | 0 |
| fused | 155 | 0.419 | 0.671 | 0.697 | 0.858 | 0.555 | 0.832 | 0.611 | 0 |

## 질의 목록 `keyword`

| 단계 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 |
|---|---|---|---|---|---|---|---|---|---|
| vector | 155 | 0.626 | 0.794 | 0.819 | 0.890 | 0.715 | 0.872 | 0.737 | 1 |
| keyword | 155 | 0.258 | 0.439 | 0.535 | 0.671 | 0.380 | 0.644 | 0.435 | 0 |
| fused | 155 | 0.484 | 0.684 | 0.774 | 0.852 | 0.603 | 0.833 | 0.651 | 0 |

## 유형 표지별 지표 (단계 fused)

| 질의 목록 | 표지 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 |
|---|---|---|---|---|---|---|---|---|---|---|
| human | multi_document | 26 | 0.500 | 0.654 | 0.654 | 0.808 | 0.597 | 0.654 | 0.547 | 0 |
| human | no_context | 32 | 0.469 | 0.625 | 0.656 | 0.812 | 0.571 | 0.802 | 0.614 | 0 |
| human | table | 34 | 0.265 | 0.500 | 0.529 | 0.765 | 0.397 | 0.765 | 0.484 | 0 |
| keyword | multi_document | 26 | 0.577 | 0.731 | 0.731 | 0.846 | 0.665 | 0.737 | 0.634 | 0 |
| keyword | no_context | 32 | 0.469 | 0.594 | 0.625 | 0.750 | 0.544 | 0.740 | 0.581 | 0 |
| keyword | table | 34 | 0.235 | 0.529 | 0.647 | 0.765 | 0.400 | 0.750 | 0.481 | 0 |

## 필터가 붙은 질의 (단계 fused)

| 질의 목록 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 | 벡터 후보가 모자란 질의 | 모자란 비율 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| human | 20 | 0.500 | 0.850 | 0.900 | 1.000 | 0.682 | 1.000 | 0.756 | 0 | 0 | 0.000 |

## 놓친 질의 45개

| 탈락 지점 | 질의 수 |
|---|---|
| no_matching_chunk | 0 |
| not_in_candidates | 6 |
| lost_in_fusion | 39 |
| lost_in_rerank | 0 |

낱말 겹침이 0인 놓친 질의: 11개

| 질의 목록 | 기대 근거 | 탈락 지점 | 낱말 겹침 |
|---|---|---|---|
| human | priv-02 | lost_in_fusion | 0.000 |
| human | priv-05 | lost_in_fusion | 0.000 |
| human | priv-12 | lost_in_fusion | 0.125 |
| human | priv-22 | lost_in_fusion | 0.000 |
| human | priv-23 | lost_in_fusion | 0.167 |
| human | priv-26 | lost_in_fusion | 0.273 |
| human | open-02 | lost_in_fusion | 0.286 |
| human | open-04 | not_in_candidates | 0.200 |
| human | open-13 | lost_in_fusion | 0.000 |
| human | open-18 | lost_in_fusion | 0.000 |
| human | cult-01 | lost_in_fusion | 0.500 |
| human | cult-06 | lost_in_fusion | 0.727 |
| human | cult-13 | lost_in_fusion | 0.364 |
| human | cult-17 | lost_in_fusion | 0.333 |
| human | cult-20 | lost_in_fusion | 0.000 |
| human | cult-21 | not_in_candidates | 0.000 |
| human | cult-25 | lost_in_fusion | 0.182 |
| human | cons-09 | lost_in_fusion | 0.286 |
| human | radi-02 | lost_in_fusion | 0.273 |
| human | radi-13 | lost_in_fusion | 0.556 |
| human | radi-22 | not_in_candidates | 0.429 |
| human | radi-23 | lost_in_fusion | 0.222 |
| keyword | priv-02 | lost_in_fusion | 0.500 |
| keyword | priv-05 | lost_in_fusion | 0.000 |
| keyword | priv-12 | not_in_candidates | 0.143 |
| keyword | priv-22 | not_in_candidates | 0.333 |
| keyword | open-04 | not_in_candidates | 0.500 |
| keyword | open-13 | lost_in_fusion | 0.167 |
| keyword | open-23 | lost_in_fusion | 0.571 |
| keyword | cult-01 | lost_in_fusion | 0.600 |
| keyword | cult-06 | lost_in_fusion | 0.600 |
| keyword | cult-18 | lost_in_fusion | 0.429 |
| keyword | cult-20 | lost_in_fusion | 0.000 |
| keyword | cult-21 | lost_in_fusion | 0.000 |
| keyword | cult-22 | lost_in_fusion | 0.000 |
| keyword | cult-25 | lost_in_fusion | 0.250 |
| keyword | labr-26 | lost_in_fusion | 0.333 |
| keyword | cons-01 | lost_in_fusion | 0.600 |
| keyword | cons-06 | lost_in_fusion | 0.286 |
| keyword | cons-09 | lost_in_fusion | 0.375 |
| keyword | cons-13 | lost_in_fusion | 0.400 |
| keyword | radi-03 | lost_in_fusion | 0.286 |
| keyword | radi-07 | lost_in_fusion | 0.333 |
| keyword | radi-22 | lost_in_fusion | 0.750 |
| keyword | radi-28 | lost_in_fusion | 1.000 |

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
