---
status: accepted
date: 2026-11-09
---

# 임베딩과 리랭커는 설치 안의 TEI 컨테이너가 돌리고, 서버는 `/v1/embeddings`·`/tokenize`·`/rerank` 셋으로 부른다. 청킹 전략은 포트 뒤의 저장소 안 집합이다

서버와 작업자 이미지에는 torch가 없다. 임베딩과 리랭커는 Hugging Face text-embeddings-inference(TEI, 1.9.4, Apache-2.0) 컨테이너가 돌리고, 컨테이너 하나가 모델 하나를 든다. 기본 임베딩 모델은 bge-m3(MIT, 1024차원, 8192토큰), 리랭커는 bge-reranker-v2-m3(Apache-2.0)이고 첫 판부터 켠다. 지식베이스 설정에 임베딩 끝점, 모델 이름, 차원이 있어 지식베이스마다 모델이 다르면 TEI 컨테이너가 모델 수만큼 선다. 호출은 셋으로 고정한다. 임베딩은 OpenAI 호환 `/v1/embeddings`, 토큰 수와 경계는 TEI 고유 `/tokenize`(문자열 배열을 한 번에 받고 토큰마다 입력의 UTF-8 바이트 오프셋 `start`·`stop`을 돌려주며 특수 토큰은 둘 다 null이다. 1.9.4 `core/src/tokenization.rs`의 `into_tokens`가 `input.bytes().skip(start).take(stop - start)`로 토큰 글자를 자르는 것을 읽음. 파이썬 문자열의 글자 인덱스로 쓰려면 Embedder 어댑터가 바이트 경계를 글자 인덱스로 바꾸고 특수 토큰을 뺀다. 그 변환은 명세가 적는다), 리랭크는 TEI `/rerank` 형식이다. `Embedder` 포트는 임베딩과 토큰화를, `Reranker` 포트는 리랭크를 가진다. 개발과 CI는 CPU 이미지(`cpu-1.9.4` amd64 압축 239MB, 프로브 `facts/tei_images_and_models.py`)를 쓰고 배포 대상만 GPU 이미지를 쓴다.

청킹은 `Chunker` 포트 뒤의 전략이고 지식베이스 설정의 전략 이름으로 고른다. 첫 판의 전략은 구조 우선 하나다(파서가 준 제목·문단·표 경계를 우선하고, 넘치면 문장 경계에서 나누며, 조각 사이에 겹침을 둔다). 어느 전략이든 조각의 상한은 토큰 수로 재고 임베딩 서버의 `/tokenize`로 센다. 상한과 겹침의 기본값(512, 64 토큰)은 어림이고 search-eval의 적중률 보고서가 정한다. 전략 집합은 저장소 안에 있고 외부 플러그인 자리로 열지 않는다. 플러그인 자리를 셋으로 정한 ADR 0003의 판을 올리는 일이라서다.

까닭. `/v1/embeddings`에는 `truncate` 칸이 없고(OpenAPI 1.9.4 원문 대조, 프로브 `facts/tei_openapi_fields.py`), 서버 인자 `--auto-truncate`의 기본값이 true이며 그 경로의 처리기는 요청에 상관없이 그 값을 쓰므로(1.9.4의 `router/src/main.rs`와 `router/src/http/server.rs`를 읽음, 프로브 `facts/tei_images_and_models.py`), 조각이 모델 상한을 넘으면 서버가 거부하지 않고 뒤를 조용히 잘라 임베딩한다. 그래서 토큰 수를 정확히 재는 일이 품질이 아니라 조각의 끝이 색인에서 빠지는 내용 유실의 문제이고, 모델이 보는 토큰으로 세려면 그 모델을 든 서버의 토큰화를 쓰는 것이 맞다. 이미지를 가르면 서버·작업자 이미지가 가볍고 GPU 유무가 서버 코드에 들어오지 않으며, 모델별 컨테이너로 지식베이스마다 다른 모델이 된다. TEI 하나가 임베딩, 토큰화, 리랭크를 다 내준다. 시멘틱 청킹은 문장 수만큼 임베딩을 더 구해 수집이 두 배 가까이 느려지는데, 2024-10 논문(Qu·Tu·Bao, arXiv 2410.13070, 웹 요약)은 그 비용이 일관된 성능 향상으로 정당화되지 않는다고 봤다. 이득은 search-eval이 숫자로 재고 나서 더한다.

## Considered Options

- 같은 이미지에서 sentence-transformers로 직접 돌린다(처음 추천): torch가 이미지에 들어 2GB를 넘고 GPU 분기가 서버 코드에 들어온다.
- vLLM(0.33): 이미지가 7.7GB(`vllm/vllm-openai:v0.33.0-x86_64-zstd`, efa 판은 10.5GB. 프로브 `facts/tei_images_and_models.py`)이고 리눅스와 compute capability 7.5 이상의 GPU가 필요하다(vLLM 문서의 CUDA 설치 절 읽음). Ollama(MIT, 3.39GB, 같은 프로브)는 리랭크 끝점이 없다(API 문서 `docs/api.md`에 rerank가 0회, 2026-11-09 읽음). llama.cpp는 TEI와 같은 자리이나 임베딩 전용 기능이 적다(어림).
- 로컬 토크나이저(HF `tokenizers` 0.23.3, 분류자 Apache, 웹 요약): 네트워크 호출이 없지만 작업자 이미지에 의존성이 늘고 지식베이스마다 tokenizer.json을 폐쇄망에 모델과 함께 반입해야 하며 py.typed는 미확인이다.
- 글자 수로 재고 어림 계수로 환산: 상한을 넘기면 조각의 끝이 조용히 잘려 나가고 한국어·영어·표가 섞이면 조각 크기가 고르지 않다.
- 첫 판부터 시멘틱 청킹: 위의 비용과 논문의 결론.

## Consequences

- TEI 고유 끝점 의존이 둘(`/tokenize`, `/rerank`)이다. 다른 임베딩 서버 어댑터는 토큰화와 리랭크를 따로 마련한다. Qwen3-Reranker는 TEI가 지원하지 않는다(1.9.4 README의 지원 모델 표에서 Qwen3는 임베딩 행 셋뿐이고 리랭커 행은 XLM-RoBERTa·GTE·ModernBert다. 프로브 `facts/tei_images_and_models.py`).
- HTTP 호출의 오버헤드는 스텁 서버에서 p50 2.96ms다(프로브 `embedding/http_overhead.py`, 출력 `http_overhead_out.txt`. 옮기기 전 첫 실행은 2.69ms였다).
- 임베딩 모델이나 청킹 설정을 바꾸면 색인 판 전환이다(ADR 0008).
- compose의 메모리 예산은 32GB를 기준으로 잡고 16GB를 최소로 문서화한다(TEI 둘과 PostgreSQL `shared_buffers`를 포함).
- `docs/constitution/tech.md`의 "임베딩과 리랭커는 로컬에서 돈다"는 "설치 안의 TEI 컨테이너"로 읽는다. 이 ADR과 함께 그 칸을 고친다.
