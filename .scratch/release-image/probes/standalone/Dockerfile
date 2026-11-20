# syntax=docker/dockerfile:1
# release-image 명세의 시제품 Dockerfile(프로브). 제품의 Dockerfile 이 아니다. 명세 "이미지의 구성"이 정한 꼴을
# 실제로 지어 본 것이고, 구현 티켓이 이 꼴을 루트의 Dockerfile 로 옮긴다. 빌드 컨텍스트는 저장소 루트다.
#
#   docker build -f .scratch/release-image/probes/standalone/Dockerfile \
#     --build-arg APP_VERSION=0.1.0-rc.1 --target server -t ri-probe/rag-engine-server:0.1.0-rc.1 .
#
# 판 번호(APP_VERSION)는 필수다. 저장소 파일은 고치지 않고 빌드 단계 안의 pyproject.toml 사본만 고친다
# (agent-os 의 serve.Dockerfile 과 같은 방법).
ARG PYTHON_IMAGE=python:3.12-slim
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.10.8

FROM ${UV_IMAGE} AS uv

# ------------------------------ 가상 환경 ------------------------------
FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
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
# 판 번호는 여기서만 넣는다. 고친 뒤에는 잠금 검사가 지나지 않으므로 프로젝트만 --frozen 으로 깐다.
ARG APP_VERSION
RUN test -n "${APP_VERSION}" || { echo "APP_VERSION 빌드 인자가 필요하다(예: 0.1.0-rc.1)" >&2; exit 1; }; \
    printf '%s' "${APP_VERSION}" | grep -Eq '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-rc\.[1-9][0-9]*)?$' \
      || { echo "APP_VERSION 은 X.Y.Z 나 X.Y.Z-rc.N 꼴이어야 한다: ${APP_VERSION}" >&2; exit 1; }; \
    sed -i "0,/^version = \"[^\"]*\"\$/s//version = \"${APP_VERSION}\"/" pyproject.toml \
 && grep -n '^version = ' pyproject.toml \
 && uv sync --frozen --no-dev --no-editable \
 && installed="$(/app/.venv/bin/python -c 'import importlib.metadata as m; print(m.version("rag-engine"))')" \
 && { [ "${installed}" = "${APP_VERSION}" ] \
      || { echo "설치된 rag-engine 의 판 ${installed} 이 넘긴 번호 ${APP_VERSION} 와 다르다" >&2; exit 1; }; }

# ------------------------------ 두 이미지가 함께 쓰는 바탕 ------------------------------
FROM ${PYTHON_IMAGE} AS runtime
RUN apt-get update \
 && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/*
# uid·gid 10001 의 rag 사용자. 쓰는 자리는 파일 저장소(/data) 하나다.
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
FROM runtime AS server
EXPOSE 8000
CMD ["rag-engine", "serve", "--host", "0.0.0.0", "--port", "8000"]

# ------------------------------ 작업자 ------------------------------
FROM runtime AS worker
CMD ["rag-engine", "worker"]
