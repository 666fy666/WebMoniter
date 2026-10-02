# Docker 与 Ubuntu 24.04 部署

本说明对应仓库当前部署结构：单容器、full 镜像、本地 SQLite，以及独立的配置、数据和日志命名卷。首次部署不会自动迁移旧 API、旧账户或旧目录挂载中的数据；旧部署请先备份，按所用版本核对迁移方式。远程镜像内容以发布工作流与实际 digest 为准。

下面的命令在仓库根目录执行。需要 Docker 权限时在 `docker` 前加 `sudo`；若原部署指定了 `-f`、`-p`、`--env-file` 或覆盖文件，后续所有命令都沿用相同参数。根目录入口与 `docker/docker-compose.full.yml` 默认共享项目名和命名卷。

[首次启动](#first-start) · [更新版本](#update) · [停止与卸载](#stop-uninstall) · [备份恢复](#backup-restore) · [回退](#rollback)

## 镜像与构建

| 镜像 | 构建目标 | 包含能力 |
|---|---|---|
| slim | `--target slim` | 全部监控、推送与 HTTP 签到；不含浏览器/OCR |
| full | `--target full` | slim + Chrome/Chromium、匹配驱动、OCR 和全部已使用模型 |

两个目标共用 `docker/Dockerfile`；默认目标为 slim。前端独立 Node 构建阶段，Python/uv 依赖构建阶段，运行层无 Node、uv、测试、截图和构建工具。基础镜像 digest、uv、浏览器/驱动和 Python 锁文件固定。模型随 full 镜像交付并校验 SHA-256，运行时不从网络下载。

```bash
docker build --target slim -f docker/Dockerfile -t webmoniter:local-slim .
docker build --target full -f docker/Dockerfile -t webmoniter:local-full .
```

在 CI 或开发机构建，5 Mbps 服务器只拉取已发布版本。网络无法解析 Debian 源时排查 Docker DNS，不默认要求 host 构建网络。离线模型可通过 `--build-arg MODEL_SOURCE=已有模型镜像` 复用 `/app/models`，构建仍对所有模型验证相同摘要，不能省略模型。

## 首次启动

<a id="first-start"></a>

准备 Git 和 Bash，下载源码并进入项目目录，执行：

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh docker
```

Ubuntu 22.04/24.04/26.04 缺少 Docker 时，脚本会按 [Docker Ubuntu 官方文档](https://docs.docker.com/engine/install/ubuntu/)配置官方软件源并安装 Engine 与 Compose；需要 root 或 sudo。已有 Docker 时直接使用，不替换冲突的系统软件包。默认拉取 full 镜像，后台启动并等待健康检查通过，无需输入初始密码。

已经安装 Docker Compose 时，也可只运行：

```bash
docker compose up -d --pull always --wait --wait-timeout 180
docker compose ps
```

根目录 `compose.yaml` 为统一配置，旧的 `docker/docker-compose.full.yml` 和 slim 入口仍可使用，项目名与命名卷保持一致。源码一键安装见 [安装说明](installation.md)。

当前 Compose 映射为 `0.0.0.0:8866:8866`。本机部署打开 <http://127.0.0.1:8866>；服务器部署打开 `http://服务器IP:8866`，并在防火墙和云安全组放行所需来源的 TCP 8866。对外开放前修改默认密码。

只通过 SSH 隧道或宿主机反代访问时，将端口映射改为 `127.0.0.1:8866:8866` 并执行 `docker compose up -d --wait --wait-timeout 180`。随后可在自己的电脑运行 `ssh -N -L 8866:127.0.0.1:8866 用户@服务器`，保持终端打开，再从自己电脑的浏览器访问 <http://127.0.0.1:8866>。

首次自动生成配置：业务任务关闭、推送为空、日志清理开启。使用默认账号 `admin`、密码 `123` 登录并在账户页修改密码；在配置页填写推送渠道、平台账号、目标与执行时间后逐一启用。保存后通常约 5 秒生效。在任务页检查状态、按需手动执行，在日志页检查结果。

本地构建后，将根目录 `.env` 的 `WEBMONITER_IMAGE` 设为 `webmoniter:local-full`，执行 `docker compose up -d --pull never --wait --wait-timeout 180`。后续更新需重新构建，并始终使用本地标签与 `--pull never`。运行已发布镜像时可将该变量固定为实际版本或 digest；不要将未发布源码与远程标签等同。

Compose 无需预先设置密码变量。需要自定义初始凭据时，可选用 `WEBMONITER_ADMIN_USERNAME` 和 `WEBMONITER_ADMIN_PASSWORD`；已创建的账户不会被环境变量覆盖。

## 更新版本

<a id="update"></a>

1. 先完成下文的 [备份](#backup-restore)，并记录当前镜像，保留用于回退。
2. 在原仓库根目录依次执行以下命令，前一步失败时先处理错误，再继续。

```bash
git pull --ff-only
docker compose up -d --pull always --wait --wait-timeout 180
docker compose ps
docker compose logs --tail=100 web-monitor
curl -fsS http://127.0.0.1:8866/health/ready
```

3. 登录确认配置、任务、历史数据仍在。若固定了镜像版本或 digest，更新前先修改根目录 `.env` 中的 `WEBMONITER_IMAGE`。根目录默认部署也可用 `bash install.sh docker` 执行拉取和启动，自定义 Compose 参数的部署继续使用自己的 Compose 命令。

更新只替换容器，保留三个命名卷，期间会短暂中断。无需先 `down`，**不要使用 `down -v` 更新**。`git pull` 仅更新源码和部署文件，不发布镜像；`docker compose pull` 仅下载镜像，`restart` 仍运行原容器。`up --pull always` 才会拉取并应用镜像变化，见 [Compose up](https://docs.docker.com/reference/cli/docker/compose/up/)。旧 bind mount 部署不能直接依靠此流程完成数据迁移。

## 停止、恢复与卸载

<a id="stop-uninstall"></a>

按目的选择一条命令执行：

| 目的 | 命令 | 保留内容 |
|---|---|---|
| 暂时停止 Web 与调度任务 | `docker compose stop` | 容器与全部数据 |
| 恢复停止的容器 | `docker compose start` | 使用原容器与数据 |
| 重启当前版本 | `docker compose restart` | 不替换镜像 |
| 停用并删除容器和项目网络 | `docker compose down` | 配置、数据、日志卷 |
| 删除容器后重新启用 | `docker compose up -d --wait --wait-timeout 180` | 使用原命名卷 |

**彻底删除部署及数据**：仅在确定不再需要配置、账号、Cookie、会话、历史记录和日志，或已完成备份时执行：

```bash
docker compose down --volumes
```

默认删除 `webmoniter_config`、`webmoniter_data`、`webmoniter_logs`，再次部署将重新初始化；此操作不可撤销。自定义项目名会改变卷名前缀。bind mount、外部卷和宿主机备份不属于此命令的数据清理范围，见 [Compose down](https://docs.docker.com/reference/cli/docker/compose/down/)。

容器删除后可选执行 `docker image rm fengyu666/webmoniter:full` 回收镜像空间；slim 或固定标签部署替换为实际镜像。仍被其他容器使用时不要强制删除。最后按需移除本项目源码目录、`.env`、备份以及反向代理入口。Docker 本身可留给其他项目使用，不需要全局清理镜像或卷。

## 2 vCPU / 2 GB 资源配置

| 项目 | Compose 默认值 |
|---|---|
| Web／调度进程 | 1 |
| 数据库 | 本地 SQLite，不额外启动 MySQL |
| 普通任务／线程池 | 4 / 4 |
| 浏览器账号并发 | 1 |
| 容器 RAM 上限／软预留 | 1,536 MiB / 512 MiB |
| `/dev/shm` 容量 | 256 MiB，实际使用计入内存预算 |
| CPU／PID 上限 | 1.75 / 256 |
| RAM + Swap 合计 | 2,048 MiB，即最多额外 512 MiB Swap |
| 应用日志 | 默认 3 天；单文件 10 MiB；约 100 MiB 总量清理预算 |
| Docker 日志 | 10 MB × 3 |
| 停止宽限期 | 30 秒，启用 init 回收子进程 |

`memswap_limit` 是内存与 Swap 的合计，不是单独 Swap 大小；宿主机没有 Swap 时不能凭这个参数获得 Swap。要禁止容器 Swap，将它设为与 `mem_limit` 相同。`mem_reservation` 是软限制，不会预先分配 512 MiB。参考 [Docker 资源限制说明](https://docs.docker.com/engine/containers/resource_constraints/)。资源假设为服务器没有其他重型常驻服务。

可选 2 GB 应急 Swap：先用 `swapon --show` 检查现有配置；以下仅在 `/swapfile` 尚不存在时执行，不覆盖已有文件。

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
# 确认 /etc/fstab 尚无该项，再持久化
printf '/swapfile none swap sw 0 0\n' | sudo tee -a /etc/fstab
```

Swap 只应处理短时突发，不能作为正常流畅运行的保障。实测基准禁用容器 Swap。

## HTTPS

建议宿主机 Caddy 反代 Docker 的本地端口。先将 `compose.yaml` 的端口映射改为 `127.0.0.1:8866:8866`，防止绕过 HTTPS 直接访问应用。域名解析到服务器，开放 80/443；根据 [Caddy 安装说明](https://caddyserver.com/docs/install#debian-ubuntu-raspbian)安装。在 `/etc/caddy/Caddyfile` 将域名替换为自己的域名：

```caddyfile
monitor.example.com {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8866
}
```

仓库另提供支持环境变量 `WEBMONITER_DOMAIN` 的 `docker/Caddyfile`。Caddy 使用 systemd 时，该变量必须配置到 Caddy 服务环境，不会自动继承交互 shell。

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

在项目根目录 `.env` 中加入或修改 `WEBMONITER_SECURE_COOKIE=1`（保留其他已有项），然后执行 `docker compose up -d --wait --wait-timeout 180`，使后续更新也沿用此设置。只在使用 HTTPS 时开启；通过 HTTP/SSH 隧道访问时保持默认 `0`，否则浏览器不会通过 HTTP 发送安全 Cookie。

保持反代后的 Host 与浏览器 Origin 一致。不要直接开放 8866 到公网，不要启动多个副本共享调度配置。

## 目录权限

应用 UID/GID 为 `10001:10001`。默认命名卷首次创建时继承镜像中目录权限：`webmoniter_config`、`webmoniter_data`、`webmoniter_logs`。入口只检查并创建必要目录，不做递归 `chmod 777`。

如果改用 bind mount，创建专用空目录并只赋予该账户权限：

```bash
sudo install -d -o 10001 -g 10001 -m 700 /srv/webmoniter/config /srv/webmoniter/data /srv/webmoniter/logs
```

映射整个配置目录到 `/app/config` 时，空 bind mount 会隐藏样例；先复制样例并赋予应用读取权限：

```bash
sudo install -o 10001 -g 10001 -m 600 config/config.yml.sample /srv/webmoniter/config/config.yml.sample
```

再将三个宿主机目录分别挂载到 `/app/config`、`/app/data`、`/app/logs`。入口会从样例生成禁用业务任务的配置。不要挂载只读单文件再要求原子写入。模型和应用程序只需读权限，浏览器临时目录由非 root 用户创建。`down --volumes` 不会清理这些宿主机目录。

## 备份与恢复

<a id="backup-restore"></a>

### 备份

备份必须包含配置与整个数据卷（业务 DB、runs.db、账户、Cookie 和会话），日志可选。SQLite 使用停机复制以包含 WAL 等配套文件。下面在仓库外创建带时间戳的受限目录，避免提交备份；从正在运行的默认部署开始，在仓库根目录复制整段执行：

```bash
(
set -eu
umask 077
backup_dir="../webmoniter-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir/config" "$backup_dir/data"
container_id="$(docker compose ps -q web-monitor)"
test -n "$container_id"
image_id="$(docker inspect --format '{{.Image}}' "$container_id")"
printf '%s\n' "$image_id" > "$backup_dir/image-id.txt"
docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "$image_id" > "$backup_dir/image-digests.txt"
cp compose.yaml "$backup_dir/compose.yaml"
if [ -f .env ]; then cp .env "$backup_dir/.env"; fi
docker compose stop
docker compose cp web-monitor:/app/config/. "$backup_dir/config/"
docker compose cp web-monitor:/app/data/. "$backup_dir/data/"
docker compose start
printf '备份位置：%s\n' "$backup_dir"
)
```

复制失败时脚本会停止，服务可能保持停止状态；先检查错误和备份完整性，再执行 `docker compose start` 恢复服务。需要日志时，在重新启动前额外复制 `/app/logs/.`。自定义部署另存使用的 Compose 文件、环境文件和项目名；有外部 MySQL 时还需单独备份该数据库。备份含凭据，转存到受控位置，不要上传公共仓库或在日志中打印其内容。

### 恢复到空卷

使用与备份匹配的应用版本及 Compose 设置，并确保目标配置卷和数据卷为空、没有运行中的服务。以下 `backup_dir` 替换为真实备份路径；不要往运行中的数据库或已有数据上直接覆盖，以免混入旧文件。已有部署先额外备份，必要时使用隔离的新项目名和未占用端口验证恢复。

```bash
(
set -eu
backup_dir="../webmoniter-backup-实际时间戳"
test -f "$backup_dir/config/config.yml"
test -d "$backup_dir/data"
docker compose create
docker compose cp "$backup_dir/config/." web-monitor:/app/config/
docker compose cp "$backup_dir/data/." web-monitor:/app/data/
docker compose run --rm --no-deps --user root \
  --cap-add CHOWN --cap-add FOWNER --cap-add DAC_OVERRIDE \
  --entrypoint sh web-monitor \
  -c 'chown -R 10001:10001 /app/config /app/data; chmod -R u+rwX,go-rwx /app/config /app/data'
docker compose up -d --wait --wait-timeout 180
curl -fsS http://127.0.0.1:8866/health/ready
)
```

默认 Compose 删除了所有 Linux capabilities，因此一次性修复容器需显式添加更改属主、权限和访问目录所需的三个能力；仅切换 root 仍不足以完成修复。这些参数只作用于本次修复，正常服务仍以 UID/GID `10001:10001` 和原权限运行。恢复后使用备份中的账户密码登录，检查配置、任务和数据页。复制命令参考 [Compose cp](https://docs.docker.com/reference/cli/docker/compose/cp/)。

## 版本回退

<a id="rollback"></a>

升级失败时先查看日志，再停止服务：

```bash
docker compose logs --tail=100 web-monitor
docker compose stop
```

从备份的 `image-digests.txt` 选择原镜像摘要，将根目录 `.env` 的 `WEBMONITER_IMAGE` 改为该完整引用，并恢复与该版本兼容的 Compose 设置。然后执行：

```bash
docker compose up -d --pull always --wait --wait-timeout 180
docker compose ps
```

本地构建镜像可能没有仓库 digest，此时依据 `image-id.txt` 将仍在本机的旧镜像 ID 标记为一个本地标签，设置 `WEBMONITER_IMAGE` 为该标签，再以 `--pull never` 启动。确认新版本正常前不要删除旧镜像。

如果新版本改变了存储格式，启动旧镜像前必须按上节恢复升级前配套备份；仅回退镜像可能无法读取新数据。`docker compose down` 保留命名卷，**不要用 `down -v` 代替回退**。

## 验证命令

```bash
.venv/bin/python scripts/container_benchmark.py --image webmoniter:local-full --seconds 60 --output /tmp/webmoniter-benchmark.json
.venv/bin/python scripts/container_benchmark.py --image webmoniter:local-full --seconds 86400 --output /tmp/webmoniter-soak.json
.venv/bin/python scripts/image_report.py 旧镜像 新镜像 --output /tmp/webmoniter-sizes.json
```

脚本使用独立临时容器、随机测试密码和本地模拟数据，不复用生产数据卷，不访问签到平台。24 小时命令是长测入口，不能将短测结果当作长测通过。体积与实测边界见 [重构审查报告](REFACTOR_AUDIT.md)。构建分层策略参考 [Docker 最佳实践](https://docs.docker.com/build/building/best-practices/)。
