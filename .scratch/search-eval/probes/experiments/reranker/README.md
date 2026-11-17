# 리랭커 켬·끔과 리랭크 후보 수 실험 (티켓 search-eval 17)

공공 문서 묶음(`evals/public-docs`, 문서 46개, 질문 155개를 사람 질문 목록과 키워드형 목록으로 각각 한 번씩 물어 질의 310개)에서 리랭커를 켠 줄(리랭크 뒤)과 끈 줄(합친 뒤)을 후보 수 5, 10, 20, 50, 100마다 견준 것이다. 질의 목록 하나의 질의는 155개라 질문 하나가 0.65%p다. 이 폴더의 `summary.md`가 후보 수마다의 전체 표(질의 목록 둘, 유형 표지 셋)이고 `report-fused-<후보 수>.json`과 `report-rerank-<후보 수>.json`이 그 원본 보고서다.

## 어떻게 돌렸나

모든 실행은 저장소의 `evals/public-docs`를 건드리지 않으려고 그 폴더를 스크래치로 복사한 묶음에서 돌렸다. 다른 세션이 같은 이름의 평가 스택(`compose.eval.yml`, 포트 55433·18083)을 띄워 두었으므로 `compose-gpu-17.yml`(프로젝트 이름 `rag-engine-eval-gpu-17`, 포트 55453·18093·18094)을 따로 썼다. 그 파일은 `tei-gpu/compose-gpu.yml`에서 프로젝트 이름과 포트만 바꾼 것이다.

```bash
docker compose -f .scratch/search-eval/probes/experiments/reranker/compose-gpu-17.yml up -d --wait
docker compose -f .scratch/search-eval/probes/experiments/reranker/compose-gpu-17.yml --profile rerank up -d --wait
export RAG_EVAL_DATABASE_URL=postgresql://rag_eval:rag_eval@127.0.0.1:55453/rag_eval
export RAG_EVAL_DATA_DIR=<빈 폴더>
export RAG_EVAL_EMBEDDING_URL=http://127.0.0.1:18093
export RAG_EVAL_RERANKER_URL=http://127.0.0.1:18094
# <묶음 사본> = evals/public-docs 를 통째로 복사한 폴더
uv run python tools/search_eval.py index <묶음 사본> --records read
# 후보 수 N마다. 실행 전에 <묶음 사본>/records 를 저장소의 것으로 되돌린다
uv run python tools/search_eval.py run --through rerank --records write --tei-device gpu \
    --config .scratch/search-eval/probes/experiments/reranker/config-candidates-N.json --out <출력 폴더> <묶음 사본>
uv run python tools/search_eval.py run --through fused --records read \
    --config .scratch/search-eval/probes/experiments/reranker/config-candidates-N.json --out <출력 폴더> <묶음 사본>
uv run python -X utf8 .scratch/search-eval/probes/experiments/reranker/rerank_latency_gpu.py http://127.0.0.1:18094
```

- 리랭크 실행에 `--records write`를 쓴 까닭: 기록에 이미 있는 쌍의 점수는 다시 계산하지 않고 옮기고 없는 쌍만 GPU로 계산하기 때문이다. `--records off`면 후보 수 50의 쌍 15,476개도 다시 계산해야 한다. `write`는 이번 실행이 쓴 열쇠만으로 사본의 `rerank.jsonl`을 다시 쓰므로 실행마다 사본의 `records/`를 저장소의 것으로 되돌렸다. 사본의 `rerank.jsonl`은 커밋하지 않는다(티켓: 실험 구성의 리랭크 점수는 커밋하지 않는다).
- `config-candidates-N.json`은 `evals/public-docs/config.json`에서 `search_candidates`만 N으로 바꾼 것이다(50은 같은 파일). 색인은 한 번이고 후보 수만 다른 구성이라 같은 데이터베이스에서 돌렸다.
- 점검 둘: 사본에서 후보 수 50의 빠른 실행 보고서는 커밋된 `evals/public-docs/baseline-fast.json`의 `rows`, `by_tag`, `filtered`와 같았고, 후보 수 50의 전체 실행 보고서는 `baseline-full.json`의 `rows`, `by_tag`, `filtered`, `misses`, `miss_counts`, `score_distribution`과 같았다(`compare_with_baseline.py`가 칸마다 `==`로 비교한다. 출력 `compare_with_baseline_out.txt`). 실험 환경이 기준을 다시 만든다는 뜻이다.
- 걸린 시간: 후보 수 5, 10, 20, 50은 기록만 읽어 각각 1분 안에 끝났고 새로 계산한 쌍이 0개다. 후보 수 100은 2026-11-17 01:57:14부터 06:41:05까지 4시간 43분 51초가 걸렸고 새로 계산한 쌍이 15,446개, 기록에서 읽은 것이 15,786개(질의 310 + 쌍 15,476)다. 평균 속도는 15,446쌍을 17,031초로 나눈 0.91쌍/초다(계산이다). `tei-gpu/rerank_throughput_gpu_out.txt`의 1.58쌍/초보다 낮은데 까닭은 재지 않았다. 장치는 GTX 1660 Ti, TEI `turing-1.9.4`이고 같은 PC에서 다른 세션이 CPU 평가 스택도 돌렸다.

## 품질: 리랭커를 켜면 무엇이 달라지나

`summary.md`의 표에서 옮긴다. 줄은 "합친 뒤"(끔)와 "리랭크 뒤"(켬)이고 셀은 끔→켬이다.

| 후보 수 | 질의 목록 | 적중@1 | 적중@5 | 적중@10 | MRR | 재현율 | nDCG@10 |
|---|---|---|---|---|---|---|---|
| 5 | human | 0.452→0.716 | 0.826→0.826 | 0.826→0.826 | 0.592→0.768 | 0.788→0.788 | 0.628→0.754 |
| 5 | keyword | 0.471→0.729 | 0.819→0.819 | 0.819→0.819 | 0.614→0.772 | 0.780→0.780 | 0.640→0.753 |
| 10 | human | 0.458→0.787 | 0.806→0.942 | 0.942→0.942 | 0.605→0.852 | 0.910→0.910 | 0.669→0.849 |
| 10 | keyword | 0.477→0.774 | 0.832→0.923 | 0.929→0.929 | 0.637→0.841 | 0.910→0.910 | 0.691→0.845 |
| 20 | human | 0.471→0.774 | 0.800→0.955 | 0.935→0.974 | 0.612→0.857 | 0.902→0.955 | 0.673→0.867 |
| 20 | keyword | 0.497→0.781 | 0.845→0.955 | 0.935→0.974 | 0.641→0.861 | 0.913→0.955 | 0.696→0.871 |
| 50 | human | 0.471→0.774 | 0.832→0.961 | 0.923→0.987 | 0.616→0.861 | 0.886→0.974 | 0.673→0.876 |
| 50 | keyword | 0.490→0.774 | 0.806→0.961 | 0.916→0.987 | 0.635→0.860 | 0.890→0.968 | 0.690→0.873 |
| 100 | human | 0.471→0.774 | 0.826→0.961 | 0.916→0.987 | 0.612→0.858 | 0.880→0.971 | 0.669→0.872 |
| 100 | keyword | 0.490→0.774 | 0.819→0.961 | 0.910→0.987 | 0.633→0.860 | 0.884→0.974 | 0.688→0.877 |

읽는 법(숫자는 위 표와 `summary.md`의 것이다. 판단은 사용자 몫이다).

- 리랭커를 켜면 후보 수 10 이상에서 적중@1이 0.28~0.33 오르고(끔 0.46~0.50에서 켬 0.77~0.79), MRR이 0.20~0.25, nDCG@10이 0.15~0.20 오른다. 유형 표지 셋(`multi_document`, `no_context`, `table`)도 두 질의 목록에서 모두 적중@1과 MRR이 오른다(`summary.md`).
- 후보 수 20, 50, 100 사이의 켬 줄 차이는 작다. 적중@1은 셋 모두 0.774~0.781이고, MRR은 0.004 안, nDCG@10은 0.009 안이며(질의 하나가 0.65%p라 이 차이는 질의 한두 개의 몫이다), 재현율은 20에서 0.955, 50과 100에서 0.968~0.974다. 후보 수 100은 50보다 낫지 않다.
- 후보 수 5와 10은 기대 근거가 후보에 들지 못하는 질의가 늘어난다(놓친 근거 55개와 20개, 후보 수 50은 4개). 적중@5와 재현율이 켜도 오르지 않는 것이 그 때문이다.
- 끄면 순위만 RRF 점수로 정해진다(ADR 0017: RRF 점수는 순위만으로 계산해 관련 정도를 담지 않는다). 끈 줄의 적중@5는 0.80~0.85, 켠 줄(후보 수 20 이상)은 0.95~0.96이다.
- 리랭크 뒤에도 놓친 근거 4개(`cult-19`, `cult-20`의 두 질의 목록)는 후보 수 50과 100에서 모두 `lost_in_rerank`다.
- 한계: 질의 목록 하나가 질문 155개이고 한 번 돌린 값이다(리랭크 점수는 기록이라 같은 기록이면 같은 숫자). 공공 문서 묶음 하나의 결과이고 다른 문서 묶음으로는 재지 않았다. 후보 수 20, 50, 100의 차이가 작다는 것은 이 묶음에서 그렇다는 뜻이다. 후보 수 100의 리랭크 점수 기록(사본의 `rerank.jsonl`, 30,922쌍)은 커밋하지 않았고, 후보 수 100 보고서의 `records.files` 해시는 그 사본의 것이라 저장소의 `records/`와 다르다.

## 지연: 같은 후보 수가 걸리는 시간

CPU의 값은 core 16의 프로브(`.scratch/core/probes/search-latency/probe_out.txt`, 코어를 묶지 않은 CPU 이미지, 개발 PC)에서 옮긴 것이고, `search` 한 번의 리랭크 시간(`rerank_ms`)이다. 후보 5개는 두 번(n=2) 쟀고 15.3~17.0초, 후보 10개는 한 번(n=1) 94.1초, 후보 50개는 한 번(n=1) 129.9초다. 검색 시간 제한의 기본(`RAG_SEARCH_TIMEOUT_SECONDS`)은 20초다.

GPU의 값은 `rerank_latency_gpu.py`가 잰 것이다(출력 `rerank_latency_gpu_out.txt`). 제품의 `TeiReranker.rerank`와 같이 쌍을 32개씩 차례로 `/rerank`에 보낸 시간만 재고, 글은 `tei-cpu/rerank_throughput.py`와 같은 합성 글이다(조각 크기를 흉내 낸 것이고 토큰 수는 재지 않았다). 후보 수마다 3번 쟀다.

| 후보 수 | 호출 수 | 3번 잰 값(초) | 중앙값 |
|---|---|---|---|
| 5 | 1 | 2.9, 2.9, 3.0 | 2.9 |
| 10 | 1 | 5.7, 6.0, 6.0 | 6.0 |
| 20 | 1 | 11.7, 11.6, 11.6 | 11.6 |
| 50 | 2 | 29.5, 29.4, 29.3 | 29.4 |
| 100 | 4 | 58.7, 58.6, 58.3 | 58.6 |

GTX 1660 Ti의 GPU 이미지로도 후보 50개의 리랭크 호출이 약 29초라 기본 검색 시간 제한 20초 안에 들지 못한다. 후보 20개는 약 12초다. 이 값은 리랭크 호출만이고 `search`가 질의 임베딩과 데이터베이스 검색에 쓰는 시간은 더해지지 않았다.

## 파일

| 파일 | 내용 |
|---|---|
| `compose-gpu-17.yml` | 다른 세션과 겹치지 않게 프로젝트 이름과 포트만 바꾼 GPU 평가 compose |
| `config-candidates-{5,10,20,50,100}.json` | `search_candidates`만 다른 구성 파일 |
| `report-fused-{N}.json`, `report-rerank-{N}.json` | 후보 수 N의 빠른 실행(리랭커 끔 기준)과 전체 실행(리랭커 켬) 보고서 |
| `summarize.py`, `summary.md` | 보고서를 옮겨 만든 표(스크립트는 숫자를 새로 재지 않는다) |
| `rerank_latency_gpu.py`, `rerank_latency_gpu_out.txt` | GPU 리랭크 호출의 후보 수별 시간 |
| `compare_with_baseline.py`, `compare_with_baseline_out.txt` | 후보 수 50의 두 보고서가 커밋된 `baseline-fast.json`, `baseline-full.json`과 같은 칸을 내는지 |
