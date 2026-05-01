# 精简镜像（Docker Hub 默认标签 latest、semver 主标签）：无 Chromium，无雨云 optional 依赖
# 雨云签到见 docker/Dockerfile.full；从仓库根目录构建：docker build -f docker/Dockerfile .
FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir uv && \
    rm -rf /root/.cache/pip

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project && \
    rm -rf /root/.cache/uv && \
    find /app/.venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "examples" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type f -name "*.pyc" -delete && \
    find /app/.venv -type f -name "*.pyo" -delete

FROM python:3.11-slim

ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo Asia/Shanghai > /etc/timezone && \
    apt-get update && apt-get install -y --no-install-recommends --no-install-suggests \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man /usr/share/info

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY pyproject.toml main.py ./
COPY config/config.yml.sample ./config.yml.sample
COPY monitors/ ./monitors/
COPY src/ ./src/
COPY tasks/ ./tasks/
COPY web/ ./web/
COPY docs/ ./docs/
COPY README.md ./
COPY docker/docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH"

CMD ["/app/docker-entrypoint.sh"]
