# 검색 평가 보고서: public-docs

- 보고서 판: 1.0.0
- 묶음 판: 1.0.0, 내용 해시: `24b1c67941efc704f93eb9e5e9f8425d2a205cf46505d2da821786450e266ad6`
- 문서 46개, 질문 155개, 질의 310개
- 실행 시각: 2026-11-16T21:27:04.966953+00:00, 커밋: a372cd61f4153e81fa494689160da283442e2553
- 잰 단계: vector, keyword, fused

## 구성

| 칸 | 값 |
|---|---|
| embedding_model | BAAI/bge-m3 |
| embedding_dimensions | 1024 |
| reranker_model | BAAI/bge-reranker-v2-m3 |
| chunking | strategy=structure_first, max_tokens=1024, overlap_tokens=128 |
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
| chunking_hash | 6884c097a00db27da90d7c691de922b0a3914d360d772fad66db6b997379c797 |
| tokenizer_version | kiwipiepy 0.24.1; kiwipiepy_model 0.24.0; keyword-rules 1 |
| chunks | 1068 |

## 질의 목록 `human`

| 단계 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 |
|---|---|---|---|---|---|---|---|---|---|
| vector | 155 | 0.503 | 0.800 | 0.858 | 0.948 | 0.661 | 0.923 | 0.715 | 2 |
| keyword | 155 | 0.265 | 0.503 | 0.600 | 0.729 | 0.403 | 0.691 | 0.465 | 0 |
| fused | 155 | 0.497 | 0.742 | 0.832 | 0.923 | 0.642 | 0.903 | 0.691 | 3 |

## 질의 목록 `keyword`

| 단계 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 |
|---|---|---|---|---|---|---|---|---|---|
| vector | 155 | 0.510 | 0.735 | 0.794 | 0.858 | 0.631 | 0.835 | 0.672 | 3 |
| keyword | 155 | 0.303 | 0.523 | 0.645 | 0.761 | 0.443 | 0.731 | 0.505 | 1 |
| fused | 155 | 0.490 | 0.716 | 0.800 | 0.916 | 0.628 | 0.887 | 0.683 | 2 |

## 유형 표지별 지표 (단계 fused)

| 질의 목록 | 표지 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 |
|---|---|---|---|---|---|---|---|---|---|---|
| human | multi_document | 26 | 0.654 | 0.769 | 0.808 | 0.885 | 0.729 | 0.769 | 0.649 | 3 |
| human | no_context | 32 | 0.438 | 0.781 | 0.844 | 0.938 | 0.619 | 0.938 | 0.685 | 1 |
| human | table | 34 | 0.529 | 0.794 | 0.824 | 0.971 | 0.676 | 0.941 | 0.733 | 0 |
| keyword | multi_document | 26 | 0.385 | 0.692 | 0.846 | 0.923 | 0.573 | 0.750 | 0.567 | 2 |
| keyword | no_context | 32 | 0.500 | 0.719 | 0.812 | 0.938 | 0.638 | 0.922 | 0.707 | 1 |
| keyword | table | 34 | 0.471 | 0.794 | 0.853 | 0.971 | 0.646 | 0.941 | 0.712 | 0 |

## 필터가 붙은 질의 (단계 fused)

| 질의 목록 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 | 벡터 후보가 모자란 질의 | 모자란 비율 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| human | 20 | 0.600 | 0.700 | 0.800 | 0.900 | 0.689 | 0.900 | 0.739 | 0 | 0 | 0.000 |

## 놓친 질의 25개

| 탈락 지점 | 질의 수 |
|---|---|
| no_matching_chunk | 0 |
| not_in_candidates | 0 |
| lost_in_fusion | 25 |
| lost_in_rerank | 0 |

낱말 겹침이 0인 놓친 질의: 1개

| 질의 목록 | 기대 근거 | 탈락 지점 | 낱말 겹침 |
|---|---|---|---|
| human | priv-05 | lost_in_fusion | 0.000 |
| human | priv-11 | lost_in_fusion | 0.083 |
| human | priv-12 | lost_in_fusion | 0.125 |
| human | open-04 | lost_in_fusion | 0.200 |
| human | open-06 | lost_in_fusion | 0.364 |
| human | open-08 | lost_in_fusion | 0.667 |
| human | cult-01 | lost_in_fusion | 0.500 |
| human | cult-06 | lost_in_fusion | 0.727 |
| human | labr-07 | lost_in_fusion | 0.571 |
| human | cons-06 | lost_in_fusion | 0.222 |
| human | radi-08 | lost_in_fusion | 0.417 |
| human | radi-23 | lost_in_fusion | 0.222 |
| keyword | priv-03 | lost_in_fusion | 0.167 |
| keyword | priv-12 | lost_in_fusion | 0.143 |
| keyword | priv-22 | lost_in_fusion | 0.333 |
| keyword | open-04 | lost_in_fusion | 0.500 |
| keyword | cult-01 | lost_in_fusion | 0.600 |
| keyword | cult-06 | lost_in_fusion | 0.600 |
| keyword | labr-07 | lost_in_fusion | 0.714 |
| keyword | labr-13 | lost_in_fusion | 0.800 |
| keyword | labr-23 | lost_in_fusion | 0.375 |
| keyword | labr-26 | lost_in_fusion | 0.333 |
| keyword | cons-03 | lost_in_fusion | 0.857 |
| keyword | cons-06 | lost_in_fusion | 0.286 |
| keyword | radi-08 | lost_in_fusion | 0.444 |

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
