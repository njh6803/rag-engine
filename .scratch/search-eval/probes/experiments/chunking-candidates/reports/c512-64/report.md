# 검색 평가 보고서: public-docs

- 보고서 판: 1.0.0
- 묶음 판: 1.0.0, 내용 해시: `270675fede5d412ff8bc63628ec5c64580f9ff5c7838698b551a86810edbc163`
- 문서 46개, 질문 155개, 질의 310개
- 실행 시각: 2026-11-16T18:03:28.792601+00:00, 커밋: a372cd61f4153e81fa494689160da283442e2553
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
| chunks | 2193 |

## 질의 목록 `human`

| 단계 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 |
|---|---|---|---|---|---|---|---|---|---|
| vector | 155 | 0.581 | 0.826 | 0.897 | 0.955 | 0.716 | 0.929 | 0.754 | 1 |
| keyword | 155 | 0.265 | 0.419 | 0.497 | 0.626 | 0.368 | 0.603 | 0.414 | 0 |
| fused | 155 | 0.471 | 0.716 | 0.832 | 0.923 | 0.616 | 0.886 | 0.673 | 1 |

## 질의 목록 `keyword`

| 단계 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 |
|---|---|---|---|---|---|---|---|---|---|
| vector | 155 | 0.561 | 0.723 | 0.826 | 0.910 | 0.670 | 0.887 | 0.709 | 2 |
| keyword | 155 | 0.284 | 0.497 | 0.587 | 0.690 | 0.412 | 0.654 | 0.462 | 0 |
| fused | 155 | 0.490 | 0.729 | 0.806 | 0.916 | 0.635 | 0.890 | 0.690 | 2 |

## 유형 표지별 지표 (단계 fused)

| 질의 목록 | 표지 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 |
|---|---|---|---|---|---|---|---|---|---|---|
| human | multi_document | 26 | 0.500 | 0.654 | 0.885 | 1.000 | 0.654 | 0.782 | 0.633 | 1 |
| human | no_context | 32 | 0.438 | 0.688 | 0.750 | 0.875 | 0.568 | 0.859 | 0.639 | 0 |
| human | table | 34 | 0.441 | 0.647 | 0.765 | 0.824 | 0.555 | 0.794 | 0.611 | 0 |
| keyword | multi_document | 26 | 0.500 | 0.769 | 0.769 | 0.962 | 0.654 | 0.808 | 0.648 | 1 |
| keyword | no_context | 32 | 0.438 | 0.688 | 0.750 | 0.781 | 0.573 | 0.781 | 0.623 | 1 |
| keyword | table | 34 | 0.382 | 0.618 | 0.735 | 0.824 | 0.526 | 0.794 | 0.587 | 0 |

## 필터가 붙은 질의 (단계 fused)

| 질의 목록 | 질의 | 적중률@1 | @3 | @5 | @10 | MRR | 재현율 | nDCG@10 | nDCG 잘림 | 벡터 후보가 모자란 질의 | 모자란 비율 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| human | 20 | 0.450 | 0.700 | 0.800 | 0.900 | 0.587 | 0.900 | 0.663 | 0 | 0 | 0.000 |

## 놓친 질의 25개

| 탈락 지점 | 질의 수 |
|---|---|
| no_matching_chunk | 0 |
| not_in_candidates | 0 |
| lost_in_fusion | 25 |
| lost_in_rerank | 0 |

낱말 겹침이 0인 놓친 질의: 11개

| 질의 목록 | 기대 근거 | 탈락 지점 | 낱말 겹침 |
|---|---|---|---|
| human | priv-01 | lost_in_fusion | 0.286 |
| human | priv-05 | lost_in_fusion | 0.000 |
| human | priv-12 | lost_in_fusion | 0.125 |
| human | priv-13 | lost_in_fusion | 0.000 |
| human | open-13 | lost_in_fusion | 0.000 |
| human | open-18 | lost_in_fusion | 0.000 |
| human | cult-01 | lost_in_fusion | 0.500 |
| human | cult-19 | lost_in_fusion | 0.000 |
| human | cult-20 | lost_in_fusion | 0.000 |
| human | cult-21 | lost_in_fusion | 0.000 |
| human | labr-10 | lost_in_fusion | 0.429 |
| human | radi-08 | lost_in_fusion | 0.417 |
| keyword | priv-12 | lost_in_fusion | 0.143 |
| keyword | priv-15 | lost_in_fusion | 0.000 |
| keyword | priv-22 | lost_in_fusion | 0.333 |
| keyword | open-13 | lost_in_fusion | 0.167 |
| keyword | cult-01 | lost_in_fusion | 0.600 |
| keyword | cult-19 | lost_in_fusion | 0.000 |
| keyword | cult-20 | lost_in_fusion | 0.000 |
| keyword | cult-21 | lost_in_fusion | 0.000 |
| keyword | labr-26 | lost_in_fusion | 0.333 |
| keyword | cons-06 | lost_in_fusion | 0.286 |
| keyword | cons-09 | lost_in_fusion | 0.375 |
| keyword | radi-07 | lost_in_fusion | 0.333 |
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
