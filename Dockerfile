# rag-engine 이미지. 판 태그, 단독 compose, SBOM과 CVE 스캔은 release-image 가 정한다(docs/constitution/tech.md).
# CI 의 image 잡이 PR 마다 짓고 띄워 /health 를 본다.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.10.8 /uv /usr/local/bin/uv

# 이미지의 파이썬(3.12)을 쓰고 내려받지 않는다. requires-python 이 ==3.12.* 라 맞지 않으면 sync 가 실패한다.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# 의존성 층을 소스 층과 나눠, 소스만 바뀐 짓기가 의존성 설치를 다시 하지 않게 한다.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

# 컨테이너는 root 가 아닌 사용자로 돈다(tech.md).
RUN useradd --system --uid 10001 --no-create-home rag
USER rag

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["rag-engine", "serve", "--host", "0.0.0.0", "--port", "8000"]
