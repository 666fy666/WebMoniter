# ============================================
# 构建阶段：安装依赖
# ============================================
FROM python:3.11-slim AS builder

# 设置工作目录
WORKDIR /app

# 安装 uv（合并命令减少层数，清理缓存）
RUN pip install --no-cache-dir uv && \
    rm -rf /root/.cache/pip

# 先只复制依赖定义文件（利用 Docker 缓存）
COPY pyproject.toml uv.lock ./

# 使用 uv 安装依赖到虚拟环境
# --frozen: 严格按照 uv.lock 安装
# --no-dev: 不安装开发环境依赖
# --no-install-project: 不将当前项目作为包安装
RUN uv sync --frozen --no-dev --no-install-project && \
    # 清理 uv 缓存和临时文件
    rm -rf /root/.cache/uv && \
    find /app/.venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "examples" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type f -name "*.pyc" -delete && \
    find /app/.venv -type f -name "*.pyo" -delete

# ============================================
# 运行阶段：最小化镜像（不内置 Chromium，雨云签到需挂载宿主机浏览器）
# ============================================
FROM python:3.11-slim

# 设置时区 + 安装 Chromium 运行依赖（仅库文件，不安装 chromium/chromium-driver 以减小体积）
# 使用雨云签到时需在宿主机安装 Chromium 并挂载进容器，见文档 docs/guides/docker-rainyun.md
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo Asia/Shanghai > /etc/timezone && \
    apt-get update && apt-get install -y --no-install-recommends --no-install-suggests \
    ca-certificates \
    libglib2.0-0 \
    libnss3 \
    libfontconfig1 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    libgl1 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man /usr/share/info

# 设置工作目录
WORKDIR /app

# 从构建阶段复制虚拟环境（只复制必要的文件）
COPY --from=builder /app/.venv /app/.venv

# 复制项目源代码（只复制运行时需要的文件）
# pyproject.toml 用于版本号读取
# docs/、README.md、config.yml.sample 供 AI 助手 RAG 检索
COPY pyproject.toml main.py config.yml.sample ./
COPY monitors/ ./monitors/
COPY src/ ./src/
COPY tasks/ ./tasks/
COPY web/ ./web/
COPY docs/ ./docs/
COPY README.md ./

# 设置环境变量（雨云签到用的 CHROME_BIN、CHROMEDRIVER_PATH 由 docker-compose 挂载宿主机时设置）
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH"

# 运行主程序（直接使用 venv 中的 python，避免 uv run 的开销）
CMD ["python", "main.py"]