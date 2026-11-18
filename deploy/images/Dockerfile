# syntax=docker/dockerfile:1
# 검색 서버와 작업자의 이미지(ADR 0020, .scratch/release-image/spec.md "이미지의 구성"). 두 이미지는 내용물이 같고
# 시작 명령만 다르다. 빌드 컨텍스트는 저장소 루트이고 들일 파일은 같은 폴더의 Dockerfile.dockerignore 가 고른다.
# 보통은 같은 폴더의 docker-bake.hcl 이 두 이미지를 한 번에 짓는다(VERSION 변수가 APP_VERSION 으로 넘어간다).
# 한 이미지만 손으로 지을 때:
#
#   docker build -f deploy/images/Dockerfile --target server \
#     --build-arg APP_VERSION=0.1.0-rc.1 --build-arg REVISION=<커밋 해시> \
#     --build-arg SOURCE=<저장소 주소> -t rag-engine-server:0.1.0-rc.1 .
#
# 릴리스 번호(APP_VERSION)는 필수다. 주지 않으면 빌드가 실패한다. 저장소의 번호(0.0.0)로 조용히 지어
# 라벨과 태그가 거짓이 되는 것보다 낫기 때문이다. 번호는 X.Y.Z 나 X.Y.Z-rc.N 꼴이다. 저장소 파일은 고치지
# 않고 빌드 단계 안의 pyproject.toml 사본만 고친다.
#
# 바탕 이미지는 2026-11-19 에 받은 태그의 digest 다(docker buildx imagetools inspect <태그> --format
# '{{json .Manifest.Digest}}'). 차례로 python:3.12-slim, ghcr.io/astral-sh/uv:0.10.8. 올릴 때는 digest 를
# 새로 받아 바꾼다.
ARG PYTHON_IMAGE=python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.10.8@sha256:88234bc9e09c2b2f6d176a3daf411419eb0370d450a08129257410de9cfafd2a

FROM ${UV_IMAGE} AS uv

# ------------------------------ 가상 환경 ------------------------------
FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
# 이미지의 파이썬(3.12)을 쓰고 내려받지 않는다. requires-python 이 ==3.12.* 라 맞지 않으면 sync 가 실패한다.
ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_CACHE=1
WORKDIR /build
# 의존성은 고치지 않은 pyproject.toml 과 잠금 파일로, 잠금 검사를 켠 채 깐다.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY README.md ./
COPY src ./src
# 릴리스 번호는 여기서만 넣는다. 고친 뒤에는 잠금 검사가 지나지 않으므로(잠금 파일이 프로젝트의 번호 0.0.0 도
# 적는다) 프로젝트만 --frozen 으로 깐다. sed 가 줄을 바꾸지 못해도 오류 없이 끝날 수 있으므로, 깐 뒤 설치된
# 패키지의 번호를 넘긴 번호와 대 보고 다르면 빌드를 실패시킨다.
ARG APP_VERSION
RUN test -n "${APP_VERSION}" || { echo "APP_VERSION 빌드 인자가 필요하다(예: 0.1.0-rc.1)" >&2; exit 1; }; \
    printf '%s' "${APP_VERSION}" | grep -Eq '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-rc\.[1-9][0-9]*)?$' \
      || { echo "APP_VERSION 은 X.Y.Z 나 X.Y.Z-rc.N 꼴이어야 한다: ${APP_VERSION}" >&2; exit 1; }; \
    sed -i "0,/^version = \"[^\"]*\"\$/s//version = \"${APP_VERSION}\"/" pyproject.toml \
 && grep -n '^version = ' pyproject.toml \
 && uv sync --frozen --no-dev --no-editable \
 && installed="$(/app/.venv/bin/python -c 'import importlib.metadata as m; print(m.version("rag-engine"))')" \
 && { [ "${installed}" = "${APP_VERSION}" ] \
      || { echo "설치된 rag-engine 의 번호 ${installed} 이 넘긴 번호 ${APP_VERSION} 와 다르다" >&2; exit 1; }; }

# ------------------------------ 두 이미지가 함께 쓰는 바탕 ------------------------------
FROM ${PYTHON_IMAGE} AS runtime
# tini 는 컨테이너의 1번 프로세스로 돌며 종료 신호를 앱에 넘기고 끝난 자식 프로세스를 거둔다. 판은 짓는 날 Debian
# 저장소에서 받으므로 digest 처럼 고정되지 않는다. 그 판은 이미지의 소프트웨어 목록이 적는다.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/*
# 컨테이너는 root 가 아닌 사용자로 돈다(tech.md). uid·gid 10001 의 rag 사용자이고 쓰는 자리는 파일 저장소(/data)
# 하나다.
RUN groupadd --gid 10001 rag \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin rag \
 && mkdir -p /data \
 && chown 10001:10001 /data
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1
WORKDIR /app
ARG APP_VERSION
ARG REVISION=unknown
ARG SOURCE=unknown
LABEL org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.source="${SOURCE}"
USER 10001:10001
ENTRYPOINT ["/usr/bin/tini", "--"]

# ------------------------------ 검색 서버 ------------------------------
# 헬스체크는 여기에 두지 않는다. 단독 compose 가 둔다(release-image 03).
FROM runtime AS server
EXPOSE 8000
CMD ["rag-engine", "serve", "--host", "0.0.0.0", "--port", "8000"]

# ------------------------------ 작업자 ------------------------------
FROM runtime AS worker
CMD ["rag-engine", "worker"]
