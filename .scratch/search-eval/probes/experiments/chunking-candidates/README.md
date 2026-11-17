# 조각 크기·겹침과 후보 수 실험 (search-eval 16)

리랭커 없이 할 수 있는 설정 실험이다. 티켓 `.scratch/search-eval/issues/16-chunking-candidates-experiment.md`, 명세 "설정 실험과 참고 측정".
공공 문서 묶음(`evals/public-docs/`)을 구성 여섯(데이터베이스 넷)으로 색인하고 빠른 실행(`run --through fused`)의 보고서를 냈다. 묶음의
`config.json`은 고치지 않았고 `--config`로 구성 파일을 줬으며 모두 `--records off`(추론 기록을 읽지도 쓰지도 않음)다.

## 구성

| 이름 | 조각 상한 · 겹침 | 후보 수 | 색인 |
|---|---|---|---|
| `c256-32` | 256 · 32 | 50 | 새 데이터베이스 `rag_eval_c256_32` |
| `c512-64` | 512 · 64 (기본) | 50 (기본) | 새 데이터베이스 `rag_eval_c512_64` |
| `c512-128` | 512 · 128 | 50 | 새 데이터베이스 `rag_eval_c512_128` |
| `c1024-128` | 1024 · 128 | 50 | 새 데이터베이스 `rag_eval_c1024_128` |
| `c512-64-k20` | 512 · 64 | 20 | `rag_eval_c512_64`를 그대로 씀 |
| `c512-64-k100` | 512 · 64 | 100 | `rag_eval_c512_64`를 그대로 씀 |

후보 수만 다른 구성은 색인이 같아 데이터베이스를 새로 만들지 않았다(`compose.eval.yml` 머리 주석이 그 길을 허용한다). 구성 파일은
`configs/`, 보고서는 `reports/<이름>/report.json`과 `report.md`다. 숫자를 한 표로 모은 것이 `summary.md`이고 `summarize.py`가 만든다.

## 돌린 명령

저장소 루트(워크트리)에서 Git Bash로 돌렸다.

```bash
docker compose -f .scratch/search-eval/probes/experiments/chunking-candidates/compose-postgres.yml up -d --wait
bash .scratch/search-eval/probes/experiments/chunking-candidates/run_experiments.sh <저장소 밖 작업 폴더>
uv run python .scratch/search-eval/probes/experiments/chunking-candidates/summarize.py > .scratch/search-eval/probes/experiments/chunking-candidates/summary.md
```

`run_experiments.sh`가 구성마다 칠 명령은 다음과 같다(환경 변수는 스크립트가 구성마다 준다).

```bash
# 조각 크기가 다른 구성: 데이터베이스를 새로 만든 뒤
uv run python tools/search_eval.py index evals/public-docs --config <구성 파일> --records off
uv run python tools/search_eval.py run evals/public-docs --through fused --records off --config <구성 파일> --out <보고서 폴더>
```

환경 변수는 `RAG_EVAL_DATABASE_URL=postgresql://rag_eval:rag_eval@127.0.0.1:55463/rag_eval_<이름>`,
`RAG_EVAL_DATA_DIR=<작업 폴더>/data/rag_eval_<이름>`(데이터베이스마다 새 폴더. `c512-64-k20`과 `c512-64-k100`은 `c512-64`의 폴더를 함께 쓴다),
`RAG_EVAL_EMBEDDING_URL=http://127.0.0.1:18093`이다.

## 장치와 걸린 시간

- 임베딩: TEI `turing-1.9.4`(`/info`의 `model_dtype`이 float16이었다. 손으로 봤다), `BAAI/bge-m3`, `--max-batch-tokens 4096`, GTX 1660 Ti(VRAM 6GB), 드라이버 621.24.
  `tei-gpu/compose-gpu.yml`과 같은 이미지·명령이고, 이 실험은 같은 시각에 다른 세션(티켓 17)이 띄운 임베딩 TEI(포트 18093)를 함께 썼다.
  그 세션의 리랭커도 같은 GPU에서 돌고 있어 `nvidia-smi`의 사용률이 99%였다(손으로 봤다). 그래서 아래 시간은 GPU 단독 처리량이 아니다.
- PostgreSQL: `compose-postgres.yml`(pgvector 0.8.7), 이 실험 전용이다.
- 2026-11-17 01:59~06:27 (KST). 시간(초)은 `timings.tsv`의 값이다.

| 구성 | 조각 수 | index | run |
|---|---|---|---|
| `c512-64` | 2,193 | 3,717 | 104 |
| `c512-64-k20` | 2,193 | (재사용) | 89 |
| `c512-64-k100` | 2,193 | (재사용) | 92 |
| `c256-32` | 4,442 | 3,058 | 96 |
| `c512-128` | 2,444 | 3,330 | 90 |
| `c1024-128` | 1,068 | 3,115 | 87 |

`timings.tsv`에는 `c1024-128`의 `index` 줄이 둘이다. 첫 줄(2,232초, 종료 코드 127)은 아래 시간 제한 때문에 실행 스크립트를 중간에 멈춘 시도다. 종료 코드 127이 무엇을 뜻하는지는
가르지 않았다(멈춘 하위 프로세스의 값으로 보지만 확인하지 않았다).
조각 수는 같은 묶음에서 `chunks` 칸이 낸 값이다.

## 알아 둘 것

- **조각 1024에서는 도구의 기본값으로 색인이 끝나지 않았다.** 도구는 제품의 코드 기본값(TEI 배치 32개, 요청 시간 제한 60초)을 그대로 쓰고
  평가 전용 환경에는 이 값을 바꾸는 길이 없다(`_IsolatedSettings`는 `init_settings`만 읽는다). 첫 시도는 1024토큰 조각의 임베딩 요청이 60초
  안에 끝나지 않아 막혔다. 저장소 밖 로그(`job_finished` 줄 50개를 세었다. 손으로 센 값이고 커밋하지 않는다)에서 약 37분 동안 성공이 30건,
  `embedding_unavailable`로 재대기열에 들어간 것이 20건이었고, 재대기열 20건 가운데 4건은 두 번째 시도였다. 수는 작업 실행 횟수이고
  문서 수(46개)가 아니다. 원인은 가르지 않았다. 조각 1024 · 배치 32의 요청이 커서인지, 그 시각에 다른 세션이 GPU를 99% 쓰고 있어서인지
  나누지 않았고, 같은 GPU 조건에서 조각 512의 색인은 끝났다는 정황이 있을 뿐이다(어림). 이 실험은 `c1024-128`만
  **커밋하지 않은 로컬 임시 변경**(`src/rag_engine/adapters/settings.py`의 `tei_batch_size` 32를 8로, `tei_timeout_seconds` 60을 120으로)으로
  다시 돌렸고, 돌린 뒤 되돌렸다(`git diff`에 `src/`가 없다). 다시 돈 로그에서는 `embedding_unavailable`이 0건이었다(`grep -c`로 셌고 커밋하지
  않는 로그다). 보고서의 `meta.commit`은 깨끗한 커밋을 가리켜 이 임시 변경이 보고서에는 보이지 않는다. 임베딩 값은 요청의 묶음 크기와
  무관하다고 보지만 비트까지 같은지는 보지 않았다. 나머지 다섯 구성은 코드 기본값 그대로다. 조각 상한을 1024로 올리는 쪽을 고르면
  제품의 `RAG_TEI_BATCH_SIZE`와 `RAG_TEI_TIMEOUT_SECONDS`도 함께 봐야 할 수 있다는 뜻이다.
- **색인 조각 수가 구성마다 다르다.** 질의 한 개의 몫은 사람 질의 155개 가운데 0.65%p, 키워드형 155개 가운데 0.65%p다. 그래서 1~2개 질의
  차이(1.3%p 안팎)는 이 표만으로 구성 사이의 우열을 말할 수 없다. CI 러너에서 같은 커밋의 빠른 게이트를 세 번 돌렸을 때 합친 뒤 줄의 지표는
  모두 같았다(`ci-fast/`. 기록의 임베딩을 읽은 실행이다). 이 실험은 GPU에서 임베딩을 새로 계산한 실행이라 그 흔들림을 그대로 쓰지 못한다.
- **기본 구성은 커밋된 기준과 거의 같지만 같지는 않다.** `c512-64`의 합친 뒤 줄은 `evals/public-docs/baseline-fast.json`의 합친 뒤 줄과 상위
  1·3·5·10 적중률, MRR, 재현율(게이트가 보는 상위 5 적중률과 MRR 포함)이 모두 같고, 놓친 질의의 수와 탈락 지점, 조각 2,193개도 같다.
  합친 뒤 줄의 nDCG@10만 최대 0.0002 달랐다. 단계별 줄은 더 달랐다. 사람 질의의 벡터만 줄은 @1이 0.587에서 0.581, MRR이 0.719에서 0.716으로,
  키워드만 줄은 @3이 0.413에서 0.419, @10이 0.613에서 0.626(질의 2개), 재현율이 0.590에서 0.603으로 움직였다. 이 실험은 `--records off`로
  GPU에서 임베딩을 새로 계산했고 기준은 기록의 임베딩을 읽었다. 같은 글을 GPU에서 두 번 계산한 임베딩이 같지 않았다는 프로브(`tei-gpu/device_diff.py`:
  코사인 최솟값 0.99998)가 있어, 그 미세한 차가 순위를 질의 1~2개씩 바꾼 것으로 본다(어림. 가르지 않았다).
- **판단용 숫자의 범위.** 필터가 붙은 질의는 사람 질의 목록에만 20개 있고 키워드형 목록에는 없다. HNSW 계획의 벡터 후보 부족은 여섯 구성
  모두 0건이다(필터 질의 20개로 잰 값이다). 이 숫자로 무엇을 고칠지는 이 티켓에서 정하지 않는다(명세 Out of Scope).
- 임베딩 값은 `--records off`라 저장하지 않았고 커밋하지 않는다. 데이터베이스(`rag_eval_*`)와 원본 파일 폴더는 저장소 밖에 있고 커밋하지 않는다.
