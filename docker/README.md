# Docker

容器工作目录为 `/app`，布局与仓库根目录一致。完整部署、单容器命令、停止和更新统一见 [安装与运行](../docs/installation.md#docker)。

## 镜像选择

| 镜像 | 标签 | Dockerfile | Compose 文件 | 适用场景 |
|:--|:--|:--|:--|:--|
| 精简镜像 | `fengyu666/webmoniter:latest` | `docker/Dockerfile` | `docker/docker-compose.yml` | 监控、推送和大多数 HTTP 签到 |
| 完整镜像 | `fengyu666/webmoniter:full` | `docker/Dockerfile.full` | `docker/docker-compose.full.yml` | 微博 Cookie 刷新、iKuuu、雨云等浏览器任务 |

完整镜像包含浏览器及浏览器签到依赖：amd64 使用 Google Chrome 稳定版和同版本 Chrome for Testing chromedriver；arm64 使用 Debian Chromium。浏览器路径为 `/usr/bin/chromium`（amd64 为符号链接），驱动为 `/usr/bin/chromedriver`。两个 Compose 文件默认容器名均为 `webmoniter`，二选一运行。

## 本地构建

在仓库根目录执行，构建上下文保持为 `.`：

```bash
docker build -t webmoniter:local -f docker/Dockerfile .
docker build -t webmoniter:local-full -f docker/Dockerfile.full .
```

依赖按 `uv.lock` 安装。依赖安装失败会终止构建，后续体积裁剪步骤允许忽略清理错误。

## 挂载与运行

- 启动前从 `config/config.yml.sample` 复制出 `config.yml`，避免把不存在的文件路径挂载成目录。
- Compose 文件在 `docker/`，配置、`data/` 和 `logs/` 挂载到仓库根目录对应路径。持久化 `data/` 可保留数据库、认证和会话。
- `docker compose ... down` 或 `docker rm` 不会删除宿主机上的这些绑定挂载文件。
- 默认访问 `http://localhost:8866`，默认账号 `admin` / `123`，首次登录后修改密码。
- Windows PowerShell 如遇挂载路径问题，使用绝对路径，例如 `D:/code/WebMoniter/config.yml:/app/config.yml`。
