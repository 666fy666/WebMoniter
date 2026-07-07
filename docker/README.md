# Docker

容器内工作目录为 `/app`，与仓库根目录布局一致（`main.py`、`src/`（含 `webUI/`、任务与监控模块）、`config/`、`config.yml`、`data/`、`logs/` 等）。

## 镜像选择

| 镜像 | 标签 | Dockerfile | Compose 文件 | 适用场景 |
|:--|:--|:--|:--|:--|
| 精简镜像 | `fengyu666/webmoniter:latest` | `docker/Dockerfile` | `docker/docker-compose.yml` | 默认推荐，适合监控、推送和大多数 HTTP 类签到 |
| 完整镜像 | `fengyu666/webmoniter:full` | `docker/Dockerfile.full` | `docker/docker-compose.full.yml` | 需要 iKuuu、雨云等浏览器签到时使用 |

完整镜像包含浏览器和浏览器签到依赖，镜像体积更大。amd64 架构使用 Google Chrome 稳定版 + Chrome for Testing 同版本 chromedriver（Debian bookworm 的 chromium 150.0.7871.46 包在容器内启动即 SIGTRAP 崩溃，导致 "Chrome instance exited"，故弃用）；arm64 架构仍使用 Debian Chromium。容器内浏览器路径保持 `/usr/bin/chromium`（符号链接）与 `/usr/bin/chromedriver` 不变。两个 Compose 文件的默认容器名都是 `webmoniter`，请二选一运行。

## 初始化

请在仓库根目录执行：

```bash
cp config/config.yml.sample config.yml
mkdir -p data logs
```

## Docker Compose

精简镜像：

```bash
# 启动
docker compose -f docker/docker-compose.yml pull
docker compose -f docker/docker-compose.yml up -d

# 查看
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs -f

# 关闭、再次启动、重启
docker compose -f docker/docker-compose.yml stop
docker compose -f docker/docker-compose.yml start
docker compose -f docker/docker-compose.yml restart

# 删除容器和网络，保留 config.yml、data/、logs/
docker compose -f docker/docker-compose.yml down

# 删除本地镜像
docker image rm fengyu666/webmoniter:latest
```

完整镜像：

```bash
# 启动
docker compose -f docker/docker-compose.full.yml pull
docker compose -f docker/docker-compose.full.yml up -d

# 查看
docker compose -f docker/docker-compose.full.yml ps
docker compose -f docker/docker-compose.full.yml logs -f

# 关闭、再次启动、重启
docker compose -f docker/docker-compose.full.yml stop
docker compose -f docker/docker-compose.full.yml start
docker compose -f docker/docker-compose.full.yml restart

# 删除容器和网络，保留 config.yml、data/、logs/
docker compose -f docker/docker-compose.full.yml down

# 删除本地镜像
docker image rm fengyu666/webmoniter:full
```

## docker run

精简镜像：

```bash
docker pull fengyu666/webmoniter:latest
docker run -d --name webmoniter --restart unless-stopped \
  -p 8866:8866 --shm-size=128m \
  -e TZ=Asia/Shanghai \
  -v "$(pwd)/config.yml:/app/config.yml" \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/logs:/app/logs" \
  fengyu666/webmoniter:latest

docker logs -f webmoniter
docker stop webmoniter
docker start webmoniter
docker restart webmoniter
docker rm webmoniter
docker image rm fengyu666/webmoniter:latest
```

完整镜像：

```bash
docker pull fengyu666/webmoniter:full
docker run -d --name webmoniter-full --restart unless-stopped \
  -p 8866:8866 --shm-size=256m \
  -e TZ=Asia/Shanghai \
  -e CHROME_BIN=/usr/bin/chromium \
  -e CHROMEDRIVER_PATH=/usr/bin/chromedriver \
  -v "$(pwd)/config.yml:/app/config.yml" \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/logs:/app/logs" \
  fengyu666/webmoniter:full

docker logs -f webmoniter-full
docker stop webmoniter-full
docker start webmoniter-full
docker restart webmoniter-full
docker rm webmoniter-full
docker image rm fengyu666/webmoniter:full
```

如果容器仍在运行，可以用 `docker rm -f webmoniter` 或 `docker rm -f webmoniter-full` 强制删除容器。

## 本地构建

构建上下文必须为仓库根目录：

```bash
docker build -t webmoniter:local -f docker/Dockerfile .
docker build -t webmoniter:local-full -f docker/Dockerfile.full .
```

## 注意事项

- Compose 文件位于 `docker/`，但 `config.yml`、`data/`、`logs/` 挂载到仓库根目录对应路径。
- `docker compose ... down` 和 `docker rm` 不会删除宿主机上的 `config.yml`、`data/`、`logs/`。
- 默认访问地址为 `http://localhost:8866`，默认账号为 `admin` / `123`。
- Windows PowerShell 如遇 `$(pwd)` 挂载路径解析异常，可改用绝对路径，例如 `D:/code/WebMoniter/config.yml:/app/config.yml`。
