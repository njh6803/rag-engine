# rag-engine 단독 설치 안내

이 문서는 서버 한 대에 rag-engine을 올리는 운영자를 위한 안내입니다. 묶음을 푼 폴더 안에서 아래 순서대로 따라 하면 환경 변수 파일과 인증서와 모델 폴더를 채워 띄우고, 떴는지 확인하고, 첫 인증 토큰을 내고, 문서를 넣고, MCP 클라이언트로 검색할 수 있습니다.

rag-engine은 여러 곳의 문서를 모아 색인하고 검색까지 맡는 서버입니다. 답을 만들지는 않습니다. MCP를 쓰는 클라이언트가 이 서버에 접속해 문서를 검색합니다.

## 1. 시작하기 전에

### 보증하는 환경

- 리눅스 x86-64 서버의 Docker Engine 28.3.3 이상과 Docker Compose 2.20.2 이상입니다. Compose는 상태 확인의 짧은 확인 간격(`start_interval`)을 받는 2.20.2부터입니다. GPU는 필요 없습니다. 임베딩 서버와 리랭커는 CPU 이미지로 뜹니다.
- 측정은 Engine 29.9.2와 Compose 5.6.1에서만 했습니다. 최소 판(Engine 28.3.3, Compose 2.20.2)에서는 재지 않았습니다. 이 안내에서 "개발 PC"는 그 측정과 명령 시험을 한 Windows PC(Docker Desktop)를 말합니다. 리눅스 서버에서는 달라질 수 있는 값(폴더 크기, 파일 소유)을 재지 않았습니다.
- 범위 밖입니다: Podman, ARM 서버, GPU 이미지로 바꾸는 설치.
- rootless 모드의 Docker와 사용자 네임스페이스 재매핑(`userns-remap`)에서는 컨테이너의 uid·gid가 호스트의 같은 번호와 대응하지 않습니다. 3-2와 3-3이 정한 소유(101, 10001)가 컨테이너 안에서 읽히지 않아 컨테이너가 시작에서 끝날 수 있습니다(재지 않았습니다). 이 두 모드는 보증하는 환경이 아닙니다.

### 서버의 메모리

메모리는 기준 32GB, 최소 16GB입니다. 임베딩 서버와 리랭커를 모두 띄우고 PostgreSQL까지 함께 도는 설치의 값입니다. 개발 PC에서 임베딩 서버는 뜬 직후 약 6.6GiB를 썼고 검색 부하 중에는 최대 7497MiB까지 올랐습니다(`--max-batch-tokens 4096`으로 띄운 값입니다. compose가 같은 값으로 띄웁니다). 리랭커는 9절에 따로 적었습니다.

### 서버 이름과 포트

- 클라이언트가 접속할 서버 이름(DNS 이름)이 필요합니다. 이 안내는 `rag.example.com`으로 적습니다. 이름은 3-1의 `RAG_ALLOWED_HOSTS`와 3-2의 인증서에 들어갑니다.
- 서버 방화벽에서 열 포트는 443 하나입니다. 80은 열지 않으며 HTTP를 HTTPS로 넘기는 응답도 없습니다. 서버에서 443이 비어 있어야 합니다. 다른 프로그램이 쥐고 있으면 프록시가 뜨지 못합니다.
- 서버, 작업자, PostgreSQL, 임베딩 서버는 밖으로 포트를 열지 않습니다.

## 2. 묶음 풀기

릴리스에서 받은 `rag-engine-<번호>.tar.gz`를 서버에서 풉니다. 풀면 같은 이름의 폴더가 하나 나옵니다. 이 안내의 명령은 모두 그 폴더 안에서 칩니다.

```bash
tar xzf rag-engine-<번호>.tar.gz
cd rag-engine-<번호>
```

폴더에는 아래가 있습니다.

- `compose.yaml`: 고치지 않습니다(8절).
- `.env.example`: 환경 변수 파일의 틀입니다. 이미지 이름공간과 번호는 채워져 있습니다.
- `proxy/`: 프록시 설정입니다(`nginx.conf`, `site.conf`). 처음에는 고치지 않습니다.
- `tls/`: 인증서와 키를 두는 폴더입니다. 안의 `README.txt`가 파일 이름과 권한을 적습니다.
- `models/`: 모델 폴더를 두는 자리입니다. 안의 `README.txt`가 내려받기와 옮기는 법을 적습니다.
- `README.md`: 이 문서입니다.

## 3. 채우기

### 3-1. 환경 변수 파일

```bash
cp .env.example .env
chmod 600 .env
```

`.env`에는 비밀 값이 들어갑니다. 운영자만 읽을 수 있게 두십시오(위의 `chmod 600 .env`). 아래 칸을 채웁니다.

- `RAG_ALLOWED_HOSTS`: 서버 이름입니다. 클라이언트가 접속하는 이름을 쉼표로 적습니다(예: `rag.example.com`). 서버는 이 목록에 없는 이름으로 온 요청을 421로 거절합니다.
- `POSTGRES_PASSWORD`: 데이터베이스 비밀번호입니다. 데이터베이스 주소에 들어가므로 깨지지 않는 16진수로 만듭니다.

```bash
openssl rand -hex 24
```

두 칸이 비어 있으면 컨테이너를 하나도 띄우지 않고 무엇이 없는지 적은 문구로 멈춥니다. `RAG_ENGINE_NAMESPACE`와 `RAG_ENGINE_VERSION`은 묶음을 만든 릴리스의 값이 이미 적혀 있으므로 고치지 않습니다. 번호는 업그레이드할 때만 바꿉니다(14절).

서버 설정(`RAG_`로 시작하는 환경 변수)을 바꾸려면 compose를 고치지 않고 `.env`에 줄을 더합니다. 서버, 작업자, 마이그레이션 컨테이너가 `.env`를 통째로 받습니다. 다만 `RAG_DATABASE_URL`, `RAG_DATA_DIR`, `RAG_DEFAULT_EMBEDDING_URL`은 compose가 정하므로 `.env`에 적어도 compose의 값이 이깁니다.

올리는 파일의 크기 상한(`RAG_MAX_UPLOAD_MB`, 기본 100)을 올리는 설치는 `.env`의 `RAG_ENGINE_SERVER_TMP_SIZE`도 함께 올립니다. 서버는 1MiB를 넘는 파일을 받는 동안 임시 파일을 `/tmp`에 두는데, 그 자리의 크기가 기본 1GiB로 막혀 있기 때문입니다. 이 자리는 메모리에 잡히므로 올린 만큼 서버 메모리를 더 씁니다. `.env.example`에 주석 처리한 예시 줄이 있습니다. compose 파일을 고쳐서 올리지 마십시오. 업그레이드 때 새 `compose.yaml`로 바꾸면 그 고침이 사라집니다.

```bash
RAG_ENGINE_SERVER_TMP_SIZE=2g
RAG_MAX_UPLOAD_MB=200
```

### 3-2. 인증서와 키

프록시는 `tls/fullchain.pem`(인증서에 중간 인증서를 이어 붙인 것)과 `tls/privkey.pem`(키)을 읽습니다. 사내 인증 기관이나 공인 기관이 발급한 인증서도 같은 이름으로 두면 됩니다.

내 인증서가 없으면 시험 삼아 스스로 서명한 인증서를 만들어 먼저 띄워 볼 수 있습니다. 서버 이름은 3-1의 `RAG_ALLOWED_HOSTS`와 같은 이름으로 적습니다.

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
  -keyout tls/privkey.pem -out tls/fullchain.pem \
  -subj "/CN=rag.example.com" \
  -addext "subjectAltName=DNS:rag.example.com,DNS:localhost,IP:127.0.0.1"
```

스스로 서명한 인증서는 MCP 클라이언트가 믿지 않아 접속에 실패하거나 경고가 뜹니다. 클라이언트가 그 인증서를 믿게 하는 방법은 클라이언트마다 달라 이 안내가 적지 않습니다. 공개하기 전에는 실제 인증서로 바꾸십시오.

어느 쪽이든 키 파일의 소유와 권한을 아래처럼 맞춥니다. 프록시는 uid 101로 돌기 때문에 `root`만 읽는 키(`root:root`, 0600)는 읽지 못해 프록시가 시작하지 못합니다. 키의 주인은 root로 두고 그룹 101에 읽기만 엽니다(0640).

```bash
sudo chown root:101 tls/privkey.pem
sudo chmod 640 tls/privkey.pem
```

인증서는 시간이 지나면 만료됩니다. 갱신은 운영자가 합니다. 새 파일을 같은 이름으로 `tls/`에 둔 뒤, 새 키 파일에도 위의 `chown`과 `chmod`를 다시 치고 10절의 두 명령으로 프록시가 새 파일을 읽게 하십시오.

### 3-3. 모델 폴더

임베딩 서버는 첫 시작에 모델을 내려받아 `models/embedding/`에 둡니다. 묶음에는 이 폴더가 없으므로 띄우기 전에 만들어 uid 10001에게 줍니다.

```bash
mkdir -p models/embedding
sudo chown -R 10001:10001 models
```

임베딩 서버는 uid 10001로 돕니다. 폴더를 미리 만들지 않으면 Docker가 root의 폴더로 만들고, 그러면 임베딩 서버가 모델을 쓰지 못해 `Permission denied`로 끝납니다. 폴더가 있어도 root의 것이면 같은 일이 납니다.

모델의 리비전(모델 저장소의 커밋 해시)은 고정하지 않습니다. 첫 시작이 그때의 최신을 받으므로 같은 모델 이름이라도 파일이 다를 수 있습니다. 시험한 리비전은 `BAAI/bge-m3`의 `5617a9f61b028005a4858fdac845db406aefb181`입니다. 내가 받은 리비전은 띄운 뒤에 읽습니다.

```bash
cat models/embedding/models--BAAI--bge-m3/refs/main
```

## 4. 띄우기와 확인

```bash
docker compose up -d --wait --wait-timeout 1800
```

처음에는 이미지를 받고, 임베딩 서버가 모델(약 2.2GiB)을 내려받으므로 몇 분이 걸립니다. 개발 PC에서 내려받기는 409초였고 느린 네트워크에서는 더 걸립니다. 모델이 이미 든 두 번째 시작부터는 건강해지는 대로 명령이 돌아옵니다.

첫 시작이 1800초를 넘기면 명령이 오류로 끝나고, 작업자는 임베딩 서버를 기다리며 뜨지 않은 채 남습니다. 임베딩 서버가 모델을 다 받아 건강해진 뒤(`docker compose logs embedding`으로 봅니다) 같은 명령을 다시 치십시오.

띄운 뒤에 상태를 봅니다.

```bash
docker compose ps
```

`postgres`, `embedding`, `server`, `proxy`가 `healthy`이고 `worker`가 `Up`이면 떴습니다. 작업자는 상태 확인이 없어서 `healthy`가 아니라 `Up`으로만 보입니다. 마이그레이션(`migrate`)은 한 번 돌고 끝나는 컨테이너라 이 목록에 나오지 않습니다. 끝난 컨테이너까지 보려면 `docker compose ps -a`를 치십시오. `migrate`가 `Exited (0)`이면 정상입니다. 프록시는 서버가 건강해진 뒤에 뜨고 TLS로 답해야 건강해지므로, 명령이 돌아온 직후 프록시가 바로 답합니다.

서버 이름으로 접속되는지 봅니다. 응답은 200이어야 합니다. 스스로 서명한 인증서를 시험 삼아 쓸 때만 `-k`를 붙여 인증서 검사를 끕니다.

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://rag.example.com/health
```

## 5. 첫 인증 토큰

이 서버는 인증 없는 요청을 거절합니다. 첫 관리용 토큰은 서버 컨테이너에서 냅니다.

```bash
docker compose exec server rag-engine bootstrap-token
```

출력에 토큰이 한 번 나옵니다. 따로 보관하십시오. 이 토큰으로 수집 API와 관리 API를 부릅니다.

## 6. 문서 넣기

서버의 폴더를 읽어 색인합니다. `<폴더>`는 서버 위의 문서 폴더의 절대 경로입니다.

```bash
docker compose run --rm -v <폴더>:/import:ro worker rag-engine ingest /import --wait
```

폴더는 읽기 전용으로 붙고, `--wait`는 색인이 끝날 때까지 기다립니다.

## 7. MCP 클라이언트로 접속하기

MCP 클라이언트의 접속 주소는 `https://<RAG_ALLOWED_HOSTS의 이름>/mcp`이고, 요청 머리에 `Authorization: Bearer <토큰>`을 싣습니다. 클라이언트마다 설정하는 방법이 다르므로 이 안내는 그 설정을 적지 않습니다.

서버가 여는 MCP 도구는 읽기만 합니다: `list_knowledge_bases`, `search`, `get_document`.

클라이언트를 설정하기 전에, 토큰이 통하는지 도구 목록을 불러 확인할 수 있습니다. 5절에서 받은 토큰을 `<토큰>` 자리에 넣습니다. 스스로 서명한 인증서를 시험 삼아 쓸 때만 `-k`를 붙입니다.

```bash
curl -sS https://rag.example.com/mcp \
  -H "Authorization: Bearer <토큰>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

세 도구의 이름과 설명이 담긴 응답이 오면 됩니다. `Authorization` 줄을 빼고 보내면 401로 거절됩니다.

## 8. 서비스와 이미지의 대응표

`compose.yaml`의 서비스 이름과 이미지의 이름은 다릅니다. 이미지를 직접 받거나 옮길 때는 아래 표로 찾으십시오. `<이름공간>`은 `.env`의 `RAG_ENGINE_NAMESPACE`이고, 태그는 `.env`의 `RAG_ENGINE_VERSION`입니다.

| 서비스 이름 | 하는 일 | 이미지 |
|---|---|---|
| `proxy` | TLS를 끝내고 요청을 서버로 넘깁니다 | `nginx` |
| `postgres` | 데이터베이스 | `pgvector/pgvector` |
| `embedding` | 임베딩 서버 | `ghcr.io/huggingface/text-embeddings-inference` |
| `reranker` | 리랭커(켜는 설치만, 9절) | `ghcr.io/huggingface/text-embeddings-inference` |
| `migrate` | 서버 앞에서 한 번 도는 마이그레이션 | `<이름공간>/rag-engine-server` |
| `server` | 검색 서버 | `<이름공간>/rag-engine-server` |
| `worker` | 문서를 색인하는 작업자 | `<이름공간>/rag-engine-worker` |

바깥 이미지 셋(`nginx`, `pgvector/pgvector`, 임베딩 서버)은 `compose.yaml`이 digest(`@sha256:`)로 고정했습니다.

### 고치지 말 것

`compose.yaml`은 고치지 않습니다. 고치면 업그레이드가 새 묶음의 `compose.yaml`로 바꿀 때 그 고침이 사라집니다. 바꿔야 하는 값은 `.env`가 받습니다. 특히 아래 셋은 바꾸지 않습니다.

- `ports`: 밖에 열리는 것은 프록시의 443 하나입니다. 서버나 PostgreSQL을 호스트에 발행하면 인증 앞의 면이 넓어집니다.
- `user:`: 서비스마다 정한 사용자로 돕니다(프록시 101, 임베딩 서버와 리랭커 10001, 우리 이미지는 이미지가 정한 사용자). 우리 이미지에는 `user:`를 더하지 않습니다.
- 안쪽 네트워크의 IPv6: 켜지 않습니다. 프록시가 뒷단의 이름을 풀 때 IPv4 주소만 받게 하려는 것입니다.

## 9. 리랭커 켜기

리랭커는 검색 결과를 다시 정렬하는 모델 서버입니다. 기본 설치는 켜지 않습니다. 켜면 검색 정확도가 올라가지만 검색이 느려집니다. 켜는 설치는 아래 넷을 합니다.

모델 폴더를 만들어 uid 10001에게 줍니다.

```bash
mkdir -p models/reranker
sudo chown -R 10001:10001 models
```

`.env`에 리랭커의 주소를 적습니다.

```bash
RAG_DEFAULT_RERANKER_URL=http://reranker:80
```

프로필로 띄웁니다. 리랭커도 첫 시작에 모델(`BAAI/bge-reranker-v2-m3`)을 내려받으므로 같은 기다림 시간을 씁니다.

```bash
docker compose --profile reranker up -d --wait --wait-timeout 1800
```

마이그레이션이 다시 돌아야 합니다. 기본 지식베이스의 리랭커 주소는 데이터베이스의 레코드에 들어 있어서 마이그레이션이 돌아야 바뀝니다. `.env`가 바뀌면 위 명령이 마이그레이션과 서버와 작업자를 새로 만들면서 마이그레이션을 함께 돌립니다. 그래도 아래 명령으로 한 번 더 돌려 두십시오. 개발 PC에서 두 번 돌려도 오류 없이 끝났습니다.

```bash
docker compose run --rm migrate
```

이후에도 리랭커를 띄우려면 `docker compose`를 칠 때마다 `--profile reranker`를 붙입니다. 업그레이드(14절)와 폐쇄망 설치(12절)의 명령에도 마찬가지입니다. 빼고 쳐도 이미 떠 있는 리랭커는 지워지지 않고 그대로 남습니다(`--remove-orphans`를 붙여도 같았습니다). 다만 그 명령은 리랭커를 다시 만들지 않으므로, 새 묶음이 리랭커 설정을 바꿨어도 반영되지 않습니다.

메모리: 리랭커는 임베딩 서버와 같은 `--max-batch-tokens 4096`으로 뜹니다. 개발 PC(Docker가 쓸 수 있는 메모리 15.6GiB)에서 질의 하나를 처리한 뒤 `docker stats`로 본 값은 리랭커 5.8GiB, 임베딩 서버 5.2GiB로 둘이 합쳐 11GiB 안팎입니다(손으로 본 값입니다). 다시 쟀을 때는 임베딩 서버 6.2GiB, 리랭커 4.9GiB로 나뉘었고 합은 같았습니다. 둘의 비율은 재 볼 때마다 달랐으므로 합으로 잡으십시오.

검색 시간: 리랭커는 CPU에서 느립니다. 개발 PC에서 후보 5개를 리랭크하는 데 15.3~17.0초(두 번 잰 값), 후보 50개에 130초(한 번 잰 값)가 걸렸고, 동시에 네 건을 보내면 후보 5개도 p95가 281초였습니다. 기본 검색 시간 제한은 20초(`RAG_SEARCH_TIMEOUT_SECONDS`)이고 후보 수는 50(`RAG_SEARCH_CANDIDATES`)입니다. 리랭커를 켠 설치는 서버의 사양에 맞춰 이 두 값을 `.env`에서 정하십시오. 후보를 줄여도 품질이 크게 떨어지지는 않았습니다. 저장소의 평가(질문 155개짜리 목록 둘)에서 후보 20·50·100개의 순위 지표(MRR)는 0.004 안으로 같았고, 사람이 쓴 질문 목록의 재현율은 후보 20개가 0.955, 50개가 0.974였습니다. 검색 시간 제한을 60초보다 크게 올리면 프록시가 뒷단의 답을 기다리는 시간(`proxy_read_timeout`, 기본 60초)도 함께 올려야 합니다(10절). 그때 무엇이 먼저 끊기는지는 재지 않았습니다.

## 10. 프록시 설정을 고칠 때

프록시 설정은 `proxy/` 폴더째 컨테이너에 읽기 전용으로 얹혀 있어서, 호스트에서 파일을 고치면(편집기의 저장이나 `sed -i`도 같습니다) 컨테이너에 보입니다. 고친 뒤에는 먼저 문법을 보고, 이상이 없을 때만 다시 읽힙니다. 주 설정의 경로를 `-c`로 꼭 줍니다. `-c`가 없으면 두 명령은 이미지의 기본 설정을 읽다 실패합니다.

```bash
docker compose exec proxy nginx -t -c /etc/rag-engine/proxy/nginx.conf
docker compose exec proxy nginx -s reload -c /etc/rag-engine/proxy/nginx.conf
```

설정이 깨져 있으면 첫 명령이 종료 1로 끝나고, 둘째 명령을 쳐도 옛 설정이 계속 답합니다. 인증서나 키 파일을 바꾼 뒤에도 같은 두 명령을 칩니다.

검색의 시간 제한을 60초보다 크게 올렸다면 `proxy/site.conf`의 `server` 블록에 `proxy_read_timeout 120s;` 같은 줄을 더하고(검색 시간 제한보다 크게), 위 두 명령을 칩니다.

### 서버를 다시 시작하는 동안

서버를 다시 시작하는 동안에는 약 10초 동안 요청이 오류(502)로 끝납니다. 프록시와 서버를 함께 다시 시작하면 9.3초, 멈춘 서버를 다시 켜면 6.2초였습니다. 프록시를 다시 시작할 필요는 없습니다.

서버에 닿지 못한 요청은 프록시 로그에 502나 504 상태 코드로만 남고 까닭은 없습니다(연결 거부 같은 것은 적지 않습니다). 까닭은 서버의 로그와 컨테이너 상태에서 찾으십시오.

```bash
docker compose logs server
docker compose ps
```

## 11. 볼륨과 지우면 안 되는 것

- `rag-engine_postgres`: 데이터베이스입니다.
- `rag-engine_data`: 서버, 작업자, 관리 명령이 함께 쓰는 파일 저장소입니다. 문서의 원본이 들어 있습니다.
- `models/` 폴더: 지우면 다음 시작이 모델을 다시 내려받습니다. 폐쇄망이면 받을 수 없으므로 지우지 마십시오.

`docker compose down`은 컨테이너만 지우고 볼륨은 남깁니다. `docker compose down -v`는 위 두 볼륨을 지우므로 치지 마십시오. 볼륨 이름이 폴더 이름과 상관없이 `rag-engine_`으로 시작하는 것은 `compose.yaml`이 프로젝트 이름을 `rag-engine`으로 정했기 때문입니다.

## 12. 폐쇄망 설치

바깥으로 나가는 길이 없는 서버에는 인터넷이 되는 기계에서 이미지와 모델을 받아 옮깁니다. 아래에서 인터넷이 되는 기계를 "받는 기계", 폐쇄망 서버를 "싣는 기계"라고 부릅니다. 옮길 것은 이미지 파일 하나, 모델 폴더, 그리고 묶음(`rag-engine-<번호>.tar.gz`)과 채운 `.env`와 `tls/`의 두 파일입니다.

### 왜 이름을 다시 붙이는가

`docker load`로 이미지를 실으면 digest(`@sha256:`)로 고정한 바깥 이미지 셋은 이름 없이 올라옵니다. 개발 PC에서 `nginx`로 보았습니다. 실은 뒤 `docker image inspect`의 `RepoDigests`와 `RepoTags`가 모두 비어 있었습니다. 이름이 없으면 `compose.yaml`의 이름으로 찾지 못해 compose가 이미지를 받으러 나가고, 폐쇄망에서는 거기서 멈춥니다. 그래서 받는 기계에서 바깥 이미지 셋에 로컬 이름을 붙여 담고, 싣는 기계에서는 `compose.override.yaml`이 그 이름을 쓰게 합니다. `compose.yaml`은 고치지 않습니다.

로컬 이름의 태그는 `compose.yaml`이 고정한 digest의 앞 12자입니다. 새 묶음이 바깥 이미지의 digest를 바꾸면 태그도 달라지므로, 옛 `compose.override.yaml`이 옛 이미지를 가리키는 일을 이름에서 알아볼 수 있습니다.

### 받는 기계에서: 받고 담기

묶음을 풀고 3-1대로 `.env`를 채웁니다. 이 `.env`를 싣는 기계에도 가져갑니다. 모델을 받으려면 아래 "모델 폴더"에서 4절의 띄우기를 성공시켜야 하는데, 프록시가 인증서와 키 없이는 건강해지지 못해 `up --wait`가 실패합니다. 그래서 3-2(인증서)와 3-3(모델 폴더)도 이 기계에서 먼저 합니다. 인증서와 키 두 파일은 싣는 기계에 그대로 가져갑니다. 이미지를 받고, 바깥 이미지 셋에 로컬 이름을 붙이고, 이미지 다섯을 파일 하나에 담습니다.

```bash
docker compose --profile reranker pull
docker tag nginx@sha256:583b7f2fce1cdb8da5ad5c39ebd3c33b98b87d493190e548bdee1fa8c619c311 rag-engine-offline/nginx:583b7f2fce1c
docker tag pgvector/pgvector:0.8.7-pg18-trixie@sha256:5895949dfcdf308eb0cd31c950c93c14895c77f33fbedfecf1fa511ab1d4bcd2 rag-engine-offline/pgvector:5895949dfcdf
docker tag ghcr.io/huggingface/text-embeddings-inference:cpu-1.9.4@sha256:2538ea1c9640d3763b15af668039d24172d063b42337b0c27796fc2be180c78d rag-engine-offline/tei:2538ea1c9640
```

우리 이미지 둘(`<이름공간>/rag-engine-server`, `<이름공간>/rag-engine-worker`)의 이름은 `.env`의 값으로 정해집니다. 아래 명령이 `compose.yaml`에서 그 이름을 읽어 목록에 더합니다. `-f compose.yaml`은 같은 폴더에 `compose.override.yaml`이 있어도 읽지 않게 하는 것입니다.

```bash
IMAGES="rag-engine-offline/nginx:583b7f2fce1c rag-engine-offline/pgvector:5895949dfcdf rag-engine-offline/tei:2538ea1c9640 $(docker compose -f compose.yaml config --images | grep -v @sha256: | sort -u)"
docker save -o rag-engine-images.tar $IMAGES
sha256sum rag-engine-images.tar > rag-engine-images.tar.sha256
for image in $IMAGES; do echo "$(docker image inspect --format '{{.Id}}' "$image") $image"; done > rag-engine-images.ids
```

`sha256sum`은 파일이 옮기는 동안 상하지 않았는지 보는 값입니다. 마지막 줄은 이미지의 ID(`docker image inspect`가 보이는 `sha256:...`)와 이름을 한 줄씩 적은 목록입니다. 싣는 기계에서 같은 ID가 나오는지 견줍니다. 개발 PC에서 이미지 다섯을 담는 데 48초, 파일은 약 1.6GiB였습니다.

### 모델 폴더

받는 기계에서 4절의 띄우는 명령을 한 번 성공으로 끝내 모델을 받아 둔 뒤(임베딩 서버가 건강해진 뒤), 모델 폴더를 소유까지 담아 묶습니다. 리랭커를 켜는 설치는 `models/reranker`도 받아 둡니다. 내려받다 끊긴 폴더를 옮기면 폐쇄망의 임베딩 서버가 빠진 파일을 받으러 나가다 이름을 풀지 못해 멈출 수 있고, 그러면 네트워크 문제처럼 보입니다(재지 않은 어림입니다).

```bash
sudo tar cf rag-engine-models.tar models
```

`tar`에 압축(`z`)을 더하면 파일은 줄지만 오래 걸립니다. 개발 PC에서 두 모델의 폴더(각각 4.3GiB, 합 8.6GiB)를 묶는 데 압축 없이는 57초에 파일 8.5GiB, `z`를 더하면 29분 26초에 5.0GiB였습니다. 받는 기계와 싣는 기계에 이 크기만큼의 디스크 자리가 있어야 합니다. 리눅스에서는 폴더 크기를 재지 않았습니다. 옮길 길이 좁을 때만 `z`를 더하십시오.

### 싣는 기계에서

묶음을 풉니다(2절). 옮겨 온 `.env`와 `tls/`의 두 파일, 이미지 파일 셋(`rag-engine-images.tar`, `.sha256`, `.ids`), `rag-engine-models.tar`를 그 폴더 안에 둡니다. 키 파일의 소유와 권한은 3-2대로 맞춥니다.

모델 폴더는 root로 풀어야 소유(10001:10001)가 그대로 살아납니다.

```bash
sudo tar xf rag-engine-models.tar
```

이미지를 싣고 ID를 견줍니다.

```bash
sha256sum -c rag-engine-images.tar.sha256
docker load -i rag-engine-images.tar
for image in $(cut -d' ' -f2 rag-engine-images.ids); do echo "$(docker image inspect --format '{{.Id}}' "$image") $image"; done | diff - rag-engine-images.ids && echo 같다
```

마지막 줄이 `같다`를 찍어야 합니다. 다르면 받는 기계와 다른 이미지를 실은 것이므로 띄우지 마십시오.

`compose.override.yaml`을 묶음 폴더에 만들어 로컬 이름을 쓰게 합니다. compose는 이 파일을 `compose.yaml` 위에 자동으로 얹습니다.

```yaml
services:
  proxy:
    image: rag-engine-offline/nginx:583b7f2fce1c
  postgres:
    image: rag-engine-offline/pgvector:5895949dfcdf
  embedding:
    image: rag-engine-offline/tei:2538ea1c9640
  reranker:
    image: rag-engine-offline/tei:2538ea1c9640
```

띄웁니다. `--pull never`는 이미지가 없을 때 받으러 나가지 않고 바로 오류로 끝나게 합니다.

```bash
docker compose up -d --wait --wait-timeout 1800 --pull never
```

리랭커를 켜는 설치는 `docker compose --profile reranker up -d --wait --wait-timeout 1800 --pull never`로 띄웁니다.

### 개발 PC에서 어디까지 쳐 보았나

개발 PC 한 대에서 위 순서를 쳤습니다. 받는 기계의 일(이미지 다섯을 담는 데 48초, 모델을 묶는 데 57초)을 한 뒤, 시험 설치를 볼륨째 내리고 이미지의 이름을 지웠습니다. 그리고 새 폴더에 묶음을 풀어 모델 풀기(45초), 체크섬 확인, 이미지 싣기, ID 견주기(`같다`가 찍혔습니다), `compose.override.yaml`, `--pull never`로 띄우기(74초)를 차례로 치고, 첫 토큰을 내어 문서를 넣고 MCP로 검색했습니다.

이 PC는 인터넷이 열려 있어서 `--pull never`로 받기를 막았을 뿐 바깥으로 나가는 길이 정말 없는 것은 아닙니다. 이 PC의 Docker는 이미지를 기본 저장소(`overlay2`)에 둡니다. 실은 이미지의 이름이 사라지는 현상(위 "왜 이름을 다시 붙이는가")은 이 저장소에서 본 것이고, Docker가 이미지 저장소로 containerd를 쓰는 설정에서도 같은지는 재지 않았습니다. 이름을 다시 붙이는 방식은 이름이 사라지든 남든 같은 로컬 이름으로 싣기 때문에 어느 쪽에서도 같은 명령이 듭니다. 리눅스의 파일 소유(`sudo tar`와 키 권한)와 Engine 28.3.3도 재지 않았습니다.

## 13. Docker Hub에서 받는 횟수 제한

이미지는 Docker Hub와 ghcr.io에서 받습니다. Docker Hub는 받는 횟수를 제한합니다. Docker 문서(<https://docs.docker.com/docker-hub/usage/pulls/>)의 표에서 읽은 값은, 로그인하지 않으면 6시간에 IPv4 주소나 IPv6 /64마다 100회이고, 무료 개인 계정은 6시간에 200회입니다. 이 수치는 Docker가 바꿀 수 있으므로 Docker의 현재 문서를 보십시오. 제한에 걸리면 잠시 뒤에 다시 받거나, `docker login`으로 로그인한 뒤 받으십시오. 여러 서버에 받다가 막히면 12절처럼 한 기계에서 받아 옮기십시오.

## 14. 업그레이드

업그레이드는 `.env`의 번호를 새 번호로 바꾸고 새 묶음의 `compose.yaml`과 `proxy/`로 바꾼 뒤 다시 띄우는 일입니다.

먼저 새 릴리스 노트의 "업그레이드할 때 할 일"을 읽으십시오. 백업이나 설정 변경이 필요한지 거기에 적혀 있습니다. 마이그레이션(데이터베이스의 모양을 바꾸는 단계)이 든 릴리스의 노트는 PostgreSQL 볼륨(`rag-engine_postgres`)을 백업하라고 적습니다. 백업과 복원의 절차는 따로 정해 둘 일이라 이 안내에는 아직 없습니다.

리랭커를 켠 설치는 아래 `docker compose` 명령마다 `--profile reranker`를 붙입니다(9절).

### 바꾸기

현재 설치 폴더 옆에 새 묶음을 풉니다. 아래에서 `<새 번호>`는 새 묶음의 번호입니다. 모든 명령은 현재 설치 폴더 안에서 칩니다. 먼저 옛 `compose.yaml`과 `proxy/`를 다른 이름으로 복사해 둡니다. 되돌릴 때 씁니다.

```bash
tar xzf <받은 위치>/rag-engine-<새 번호>.tar.gz -C ..
cp compose.yaml compose.yaml.old
cp -r proxy proxy.old
```

새 `compose.yaml`로 바꾸고, `proxy/` 폴더는 두고 그 안을 비운 뒤 새 묶음의 `proxy/` 안 파일을 같은 폴더로 복사합니다.

```bash
cp ../rag-engine-<새 번호>/compose.yaml compose.yaml
find proxy -mindepth 1 -delete
cp -r ../rag-engine-<새 번호>/proxy/. proxy/
```

`proxy/` 안을 비우지 않고 덮어쓰기만 하면 새 릴리스가 지웠거나 이름을 바꾼 옛 파일이 남습니다(개발 PC에서 옛 묶음에만 있던 파일을 두고 쳐 보았고, 비운 뒤에는 그 파일이 사라졌습니다). 폴더째 지우고 새로 만들거나 다른 이름으로 바꿔 놓지 마십시오. 도는 프록시는 처음 얹은 폴더를 계속 읽기 때문에 새 폴더의 파일을 보지 못합니다.

`.env`, `tls/`, `models/`, 12절이 만든 `compose.override.yaml`은 그대로 둡니다. 설치 폴더의 `README.md`와 `.env.example`은 옛 묶음의 것으로 남습니다. 새 안내는 `../rag-engine-<새 번호>/README.md`에서 읽으십시오. `proxy/`의 파일을 고쳐 쓰고 있었다면 옛 것과 새 것을 견주어 고친 값을 새 파일에 다시 넣습니다.

```bash
diff -r proxy.old proxy
```

`.env`의 번호를 새 번호로 바꿉니다. 새 묶음의 `.env.example`에 칸이 늘었는지도 견주어, 필요한 줄을 `.env`에 더합니다.

```bash
sed -i 's/^RAG_ENGINE_VERSION=.*/RAG_ENGINE_VERSION=<새 번호>/' .env
diff .env.example ../rag-engine-<새 번호>/.env.example
```

폐쇄망 서버라면 새 이미지가 먼저 있어야 합니다. 받는 기계에서 새 묶음으로 12절의 "받고 담기"를 하고, 싣는 기계에서 이미지를 실은 뒤, `compose.override.yaml`의 이름(태그)을 새 `compose.yaml`이 고정한 digest의 앞 12자에 맞춥니다(`grep @sha256 compose.yaml`로 봅니다). 바깥 이미지가 그대로이면 이름도 그대로입니다. 띄우는 명령에는 `--pull never`를 더합니다.

### 띄우기

옛 서버와 작업자를 먼저 멈춥니다. 새 마이그레이션이 도는 동안, 그리고 그 뒤 서버를 다시 만들 때까지 옛 코드가 새 데이터베이스 모양에 닿는 틈을 없애려는 것입니다. 그다음 띄웁니다.

```bash
docker compose stop server worker
docker compose up -d --wait --wait-timeout 1800
```

`up`은 `.env`와 `compose.yaml`이 바뀐 서비스를 다시 만들지만, 프록시는 다시 만들지 않습니다. 개발 PC에서 `proxy/`의 파일만 바뀌었을 때 프록시 컨테이너는 그대로였고(컨테이너 번호도, 시작 시각도 같았습니다), 옛 설정으로 계속 답했습니다. 그래서 문법을 보고 다시 읽게 합니다. 이 두 명령은 10절과 같습니다.

```bash
docker compose exec proxy nginx -t -c /etc/rag-engine/proxy/nginx.conf
docker compose exec proxy nginx -s reload -c /etc/rag-engine/proxy/nginx.conf
```

`docker compose ps`로 상태를 보고(4절), `curl`로 서버 이름의 `/health`가 200인지 봅니다. 개발 PC에서 다시 읽은 뒤 프록시는 새 설정으로 답했습니다(`site.conf`에 둔 표시 머리글이 옛 값에서 새 값으로 바뀌었습니다).

### 되돌리기

마이그레이션이 실패했을 때만 이 길로 되돌릴 수 있습니다. 스키마를 바꾸는 단계는 모든 리비전이 한 트랜잭션 안에서 돌기 때문에(마이그레이션 코드를 읽어 확인했습니다. 일부러 실패시켜 보지는 않았습니다) 실패하면 스키마가 그대로 남습니다. 마이그레이션이 끝난 뒤의 실패는 이 길로 되돌리지 못할 수 있으니, 업그레이드 전의 백업에서 복원해야 합니다.

옛 `compose.yaml`과 옛 `proxy/`의 파일을 같은 길로 돌리고, 번호를 옛 번호로 되돌린 뒤 다시 띄웁니다.

```bash
cp compose.yaml.old compose.yaml
find proxy -mindepth 1 -delete
cp -r proxy.old/. proxy/
sed -i 's/^RAG_ENGINE_VERSION=.*/RAG_ENGINE_VERSION=<옛 번호>/' .env
docker compose stop server worker
docker compose up -d --wait --wait-timeout 1800 --remove-orphans
docker compose exec proxy nginx -s reload -c /etc/rag-engine/proxy/nginx.conf
```

`--remove-orphans`는 새 `compose.yaml`에만 있던 서비스를 걷어 냅니다. 새 compose 파일은 옛 이미지가 모르는 설정이나 서비스를 담을 수 있어서, 번호만 되돌리면 옛 이미지가 새 배치로 뜹니다. 개발 PC에서 이 순서로 되돌려 서버와 작업자가 옛 번호로 뜨고 프록시가 옛 설정으로 답하는 것을 보았습니다.
