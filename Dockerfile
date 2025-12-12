# 使用 Python 3.11 作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装 uv
RUN pip install --no-cache-dir uv

# 1. 先只复制依赖定义文件
# 这样做的好处是：只要这两个文件没变，Docker 会使用缓存，跳过下面的安装步骤
COPY pyproject.toml uv.lock ./

# 2. 使用 uv 安装依赖
# --frozen: 严格按照 uv.lock 安装
# --no-dev: 不安装开发环境依赖
# --no-install-project: 【关键修改】不将当前项目作为包安装，解决找不到 README.md 的问题
RUN uv sync --frozen --no-dev --no-install-project

# 3. 依赖安装完成后，再复制项目的其余源代码
COPY . .

# 设置环境变量
# PYTHONPATH=/app 确保 python 能直接导入当前目录下的模块，
# 因为我们使用了 --no-install-project，项目本身没有被安装到 site-packages 里
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 暴露端口（如果需要）
# EXPOSE 8000

# 运行主程序
# 依然使用 uv run，它会自动使用刚才创建的虚拟环境
CMD ["uv", "run", "python", "main.py"]