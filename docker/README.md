# Docker

容器内工作目录为 **`/app`**，与仓库根目录布局一致（`main.py`、`web/`、`config.yml` 等）。

构建上下文必须为**仓库根目录**：

```bash
docker build -f docker/Dockerfile .
docker build -f docker/Dockerfile.full .
```

Compose 文件的挂载路径相对于 `docker/` 目录解析，`config.yml` / `data/` / `logs/` 仍在**仓库根目录**。请在克隆后的项目根目录执行：

```bash
cp config/config.yml.sample config.yml
# 编辑 config.yml 后：
docker compose -f docker/docker-compose.yml pull
docker compose -f docker/docker-compose.yml up -d
```

雨云签到使用完整镜像：

```bash
docker compose -f docker/docker-compose.full.yml pull
docker compose -f docker/docker-compose.full.yml up -d
```
