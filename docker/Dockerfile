# 精简镜像（Docker Hub 默认标签 latest、semver 主标签）：无 Chromium，无雨云 optional 依赖
# 雨云签到见 docker/Dockerfile.full；从仓库根目录构建：docker build -f docker/Dockerfile .
FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir uv && \
    rm -rf /root/.cache/pip && \
    apt-get update && apt-get install -y --no-install-recommends binutils && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

# 安装依赖并裁剪体积（本阶段产物会被丢弃，仅最终拷贝裁剪后的 .venv）：
# 1) 删除缓存、测试/示例目录、字节码
# 2) 删除运行时无用文件：类型存根 .pyi、C 头文件 .h、静态库 .a、语言包 .mo
# 3) strip 共享库调试符号（--strip-unneeded 对 .so 安全，不影响运行）
RUN uv sync --frozen --no-dev --no-install-project && \
    rm -rf /root/.cache/uv && \
    find /app/.venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d \( -name tests -o -name test -o -name examples \) -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.pyi" -o -name "*.h" -o -name "*.a" \) -delete 2>/dev/null || true && \
    find /app/.venv -path "*/locale/*" -name "*.mo" -delete 2>/dev/null || true && \
    find /app/.venv -name "*.so" -exec strip --strip-unneeded {} + 2>/dev/null || true

FROM python:3.11-slim

ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo Asia/Shanghai > /etc/timezone && \
    apt-get update && apt-get install -y --no-install-recommends --no-install-suggests \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man /usr/share/info

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY pyproject.toml main.py ./
COPY config/ ./config/
COPY src/ ./src/
COPY docs/ ./docs/
COPY README.md ./
COPY docker/docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH"

EXPOSE 8866

CMD ["/app/docker-entrypoint.sh"]
