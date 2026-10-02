# Docker 部署与维护

完整操作入口见 [README](../README.md#docker-first-deploy)，备份恢复、HTTPS、权限与资源限制见 [部署指南](../docs/DEPLOYMENT.md)。以下命令均在仓库根目录运行，不是在 `docker/` 目录运行；需要权限时在 `docker` 前加 `sudo`。

## 首次部署与访问

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh docker
```

Ubuntu 22.04/24.04/26.04 缺少 Docker 时，脚本自动安装官方 Engine 与 Compose（需要 root 或 sudo）；其他系统请先准备 Docker 与 Compose。已有 Compose 时可用 `docker compose up -d --pull always --wait --wait-timeout 180` 代替脚本。默认后台运行 full 镜像，配置自动初始化，不需要手动复制 `config.yml`。

本机打开 <http://127.0.0.1:8866>，服务器部署打开 `http://服务器IP:8866`。当前映射 `0.0.0.0:8866:8866`，远程访问需放行防火墙和云安全组中的 TCP 8866。首次账号 `admin`、密码 `123`，对外开放前修改密码，并在配置页启用需要的任务。只通过 SSH 或宿主机反代访问时，将映射改为 `127.0.0.1:8866:8866` 并重新执行 `up`；SSH 访问在自己的电脑运行 `ssh -N -L 8866:127.0.0.1:8866 用户名@服务器地址` 后打开本机地址。长期访问见 [HTTPS](../docs/DEPLOYMENT.md#https)。

## 镜像选择

<a id="image-selection"></a>

| 入口 | 默认镜像 | 适用场景 |
|---|---|---|
| `compose.yaml` / `bash install.sh docker` | `fengyu666/webmoniter:full` | 包含浏览器、驱动与 OCR，默认推荐 |
| `docker/docker-compose.full.yml` | `fengyu666/webmoniter:full` | full 的兼容入口 |
| `docker/docker-compose.yml` | `fengyu666/webmoniter:latest` | 精简版，适合监控、推送与 HTTP 任务 |

这些入口默认共享项目名 `webmoniter` 和三个命名卷，是同一部署的不同入口，不能当作独立实例同时运行。`latest` 不包含浏览器与 OCR；微博 Cookie 刷新、iKuuu、雨云等浏览器任务使用 full。

如需切换精简版，在仓库根目录创建或编辑 `.env`，加入下面一行（已有文件只修改该项，不覆盖其他设置）：

```dotenv
WEBMONITER_IMAGE=fengyu666/webmoniter:latest
```

然后执行 `docker compose up -d --pull always --wait --wait-timeout 180`。切回 full 时将该项改为 `fengyu666/webmoniter:full`，再执行同一命令。切换到 slim 前先关闭依赖浏览器的任务。

`WEBMONITER_IMAGE` 会覆盖以上所有入口的默认镜像。需要固定版本时填写实际已发布标签：发布工作流的精简版格式为 `X.Y.Z`，完整版为 `X.Y.Z-full`，也可填写 `fengyu666/webmoniter@sha256:实际摘要`；不要原样使用占位符。`.env` 保留在本机并限制访问，环境中已导出的同名变量优先于 `.env`。

## 日常操作、更新与卸载

| 目的 | 命令 | 数据是否保留 |
|---|---|---|
| 查看状态 | `docker compose ps` | 是 |
| 跟踪日志 | `docker compose logs --tail=100 -f web-monitor` | 是；Ctrl+C 仅退出查看 |
| 拉取并应用新镜像 | `docker compose up -d --pull always --wait --wait-timeout 180` | 是；更新前备份 |
| 暂停服务和任务 | `docker compose stop` | 是，保留容器 |
| 恢复已停止的容器 | `docker compose start` | 是 |
| 重启当前容器 | `docker compose restart` | 是，不更新镜像 |
| 删除容器与项目网络 | `docker compose down` | 是，保留命名卷 |
| 删除容器后恢复 | `docker compose up -d --wait --wait-timeout 180` | 是，沿用原卷 |
| **彻底删除部署及数据** | `docker compose down --volumes` | **否，配置、账号、Cookie、历史与日志永久删除** |

更新前 [备份配置和数据](../docs/DEPLOYMENT.md#backup-restore)，在原目录执行 `git pull --ff-only` 更新仓库文件，再执行表中的更新命令。每步成功后再继续；`git pull` 不会构建镜像，远程标签必须已发布相应代码。停止和删除操作按需选择，不要把整张表当成连续步骤。

默认持久化卷为 `webmoniter_config`（`/app/config`）、`webmoniter_data`（`/app/data`）、`webmoniter_logs`（`/app/logs`）。根目录 `config.yml` 和 `./data` 不用于默认 Docker 部署。旧部署的 bind mount 数据不会自动迁移。

卸载后可选执行 `docker image rm fengyu666/webmoniter:full` 删除不再使用的镜像（slim 或自定义镜像替换为实际标签）。`down --volumes` 不删除源码、`.env`、宿主机备份或 bind mount 文件，也不卸载 Docker；详情见 [删除与卸载](../README.md#docker-uninstall)。

## 从当前源码构建

<a id="local-build"></a>

需要运行尚未发布的修改时，在开发机或构建服务器上执行。两个目标共用 `docker/Dockerfile`；未指定目标默认构建 slim。full 命令如下：

```bash
docker build --target full -f docker/Dockerfile -t webmoniter:local-full .
```

将仓库根目录 `.env` 中的镜像设置为本地标签，后续维护保持此设置：

```dotenv
WEBMONITER_IMAGE=webmoniter:local-full
```

```bash
docker compose up -d --pull never --wait --wait-timeout 180
docker compose ps
```

构建 slim 时使用 `docker build --target slim -f docker/Dockerfile -t webmoniter:local-slim .`，同时修改 `.env` 为对应标签。本地镜像更新流程为 `git pull --ff-only` → 重新 `docker build` → `up --pull never`；不要运行固定拉取远程镜像的安装脚本，也不要使用 `--pull always` 拉取仅存在本机的标签。构建机与运行机分离时需另行通过镜像仓库或镜像导出导入传递镜像。

## GitHub Actions 发布与服务器更新

`Build and Push Docker Image` 工作流在推送 `v*` 标签或手动触发时构建镜像，普通分支推送只运行质量检查，不会发布镜像。代码合并后，在 GitHub 的 **Actions → Build and Push Docker Image → Run workflow** 选择对应分支，等待完整工作流成功。仓库需要配置 `DOCKER_USERNAME` 和 `DOCKER_PASSWORD` Actions secrets。

镜像 `fengyu666/webmoniter:full` 是包含浏览器与识别依赖的完整版；`fengyu666/webmoniter:latest` 是精简版。使用 `docker/docker-compose.full.yml` 的服务器，在项目根目录运行：

```bash
# 拉取镜像、更新容器，并等待健康检查通过
docker compose -f docker/docker-compose.full.yml up -d --pull always --no-build --wait --wait-timeout 180 web-monitor

# 检查运行状态与最近日志
docker compose -f docker/docker-compose.full.yml ps
docker compose -f docker/docker-compose.full.yml logs --tail=100 web-monitor
```

若已进入项目的 `docker` 目录，将命令中的文件路径改为 `docker-compose.full.yml`。更新时沿用原部署的工作目录、`-p`、`--env-file` 和其他 Compose 覆盖文件参数，确保仍使用相同配置与数据卷。`WEBMONITER_IMAGE` 环境变量会覆盖默认镜像地址；若固定了版本标签，需要先改成要部署的新标签。

`up --pull always` 会拉取镜像，并在镜像变化时重建容器，保留挂载卷。单独执行 `docker pull` 只下载镜像，`restart` 也不会切换容器镜像。无需先执行 `down`，不要用会删除数据卷的 `down -v`。详见 [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/) 与 [pull](https://docs.docker.com/reference/cli/docker/compose/pull/)。

`down` 与 `down --volumes` 的清理范围见 [Docker Compose down](https://docs.docker.com/reference/cli/docker/compose/down/)。镜像测量和验收边界见 [审查报告](../docs/REFACTOR_AUDIT.md)；仓库中的代码是否已进入远程镜像，请以对应发布工作流和镜像 digest 为准。
