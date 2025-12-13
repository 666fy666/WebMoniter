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
    find /app/.venv -type f -name "*.pyc" -delete && \
    find /app/.venv -type f -name "*.pyo" -delete

# ============================================
# 运行阶段：最小化镜像
# ============================================
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 从构建阶段复制虚拟环境（只复制必要的文件）
COPY --from=builder /app/.venv /app/.venv

# 复制项目源代码（只复制运行时需要的文件）
COPY main.py ./
COPY monitors/ ./monitors/
COPY src/ ./src/

# 设置环境变量
# PYTHONPATH=/app 确保 python 能直接导入当前目录下的模块
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH"

# 运行主程序（直接使用 venv 中的 python，避免 uv run 的开销）
CMD ["python", "main.py"]