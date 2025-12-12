# 使用 Python 3.11 作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装 uv
RUN pip install --no-cache-dir uv

# 复制项目文件
COPY pyproject.toml uv.lock ./
COPY . .

# 使用 uv 安装依赖
RUN uv sync --frozen --no-dev

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 暴露端口（如果需要）
# EXPOSE 8000

# 运行主程序
CMD ["uv", "run", "python", "main.py"]
