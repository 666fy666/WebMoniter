# Docker 与 Ubuntu 24.04 部署

本说明对应当前源码重构版，全新部署，不自动迁移旧 API 或账户数据。远程 `latest/full` 是否已包含修改取决于发布版本；当前开发结果未推送到镜像仓库。

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

下载源码并进入项目目录，执行：

```bash
bash install.sh docker
```

Ubuntu 22.04/24.04/26.04 缺少 Docker 时，脚本会按 [Docker Ubuntu 官方文档](https://docs.docker.com/engine/install/ubuntu/)配置官方软件源并安装 Engine 与 Compose；需要 root 或 sudo。已有 Docker 时直接使用，不替换冲突的系统软件包。默认拉取 full 镜像，后台启动并等待健康检查通过，无需输入初始密码。

已经安装 Docker Compose 时，也可只运行：

```bash
docker compose up -d --pull always --wait
```

根目录 `compose.yaml` 为统一配置，旧的 `docker/docker-compose.full.yml` 和 slim 入口仍可使用，项目名与命名卷保持一致。源码一键安装见 [安装说明](installation.md)。

Compose 只发布 `127.0.0.1:8866`。在远程服务器可先用 `ssh -L 8866:127.0.0.1:8866 用户@服务器` 从本机浏览器访问。首次自动生成配置：业务任务关闭、推送为空、日志清理开启。登录后在配置页填写所需账号并逐一启用。默认账号 `admin`、密码 `123`，直接登录即可。可选环境变量只初始化尚未创建的管理员，后续修改密码用账户页。

本地构建验证执行 `WEBMONITER_IMAGE=webmoniter:local-full docker compose up -d --pull never --wait`。生产发布后用确定的版本或 `image: 仓库@sha256:实际摘要`，不要把旧远程标签当成本次开发结果。

Compose 无需预先设置密码变量。需要自定义初始凭据时，可选用 `WEBMONITER_ADMIN_USERNAME` 和 `WEBMONITER_ADMIN_PASSWORD`；已创建的账户不会被环境变量覆盖。

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

建议宿主机 Caddy 反代 Docker 的本地端口。域名解析到服务器，开放 80/443；根据 [Caddy 安装说明](https://caddyserver.com/docs/install#debian-ubuntu-raspbian)安装。在 `/etc/caddy/Caddyfile` 将域名替换为自己的域名：

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
export WEBMONITER_SECURE_COOKIE=1
docker compose up -d
```

保持反代后的 Host 与浏览器 Origin 一致。不要直接开放 8866 到公网，不要启动多个副本共享调度配置。

## 目录权限

应用 UID/GID 为 `10001:10001`。默认命名卷首次创建时继承镜像中目录权限：`webmoniter_config`、`webmoniter_data`、`webmoniter_logs`。入口只检查并创建必要目录，不做递归 `chmod 777`。

如果改用 bind mount，创建专用空目录并只赋予该账户权限：

```bash
sudo install -d -o 10001 -g 10001 -m 700 /srv/webmoniter/config /srv/webmoniter/data /srv/webmoniter/logs
```

映射整个配置目录到 `/app/config` 时，空 bind mount 会隐藏样例；先将仓库 `config/config.yml.sample` 安装为 `/srv/webmoniter/config/config.yml.sample`，或自行准备禁用业务任务的 `config.yml`。不要挂载只读单文件再要求原子写入。模型和应用程序只需读权限，浏览器临时目录由非 root 用户创建。

## 备份、恢复与回退

备份必须包含配置与整个数据卷（业务 DB、runs.db、账户、Cookie 和会话），日志可选。SQLite 最稳妥的离线备份是在停止容器后复制，避免遗漏 WAL。以下命令在仓库根目录执行，备份含敏感数据，保存在受限目录：

```bash
umask 077
mkdir -p backup/config backup/data
docker compose stop
docker compose cp web-monitor:/app/config/. backup/config/
docker compose cp web-monitor:/app/data/. backup/data/
docker compose start
```

恢复到空卷：先 `create` 容器，再停止状态下 `compose cp backup/config/. web-monitor:/app/config/` 与 `compose cp backup/data/. web-monitor:/app/data/`。复制后使用一次性 `compose run --rm --no-deps --user root --entrypoint sh web-monitor -c 'chown -R 10001:10001 /app/config /app/data; chmod -R u+rwX,go-rwx /app/config /app/data'` 修复这两个专用卷的属主，随后正常启动。不要覆盖运行中的数据库。恢复后验证 `/health/ready`、登录和数据页。

升级前记录当前镜像 digest 并备份。升级失败时停止服务，将 Compose 镜像改回旧 digest；如果新版本改变了存储格式，同时恢复升级前的配套备份。`docker compose down` 保留命名卷，**不要用 `down -v` 回退**。

## 验证命令

```bash
.venv/bin/python scripts/container_benchmark.py --image webmoniter:local-full --seconds 60 --output /tmp/webmoniter-benchmark.json
.venv/bin/python scripts/container_benchmark.py --image webmoniter:local-full --seconds 86400 --output /tmp/webmoniter-soak.json
.venv/bin/python scripts/image_report.py 旧镜像 新镜像 --output /tmp/webmoniter-sizes.json
```

脚本使用独立临时容器、随机测试密码和本地模拟数据，不复用生产数据卷，不访问签到平台。24 小时命令是长测入口，不能将短测结果当作长测通过。体积与实测边界见 [重构审查报告](REFACTOR_AUDIT.md)。构建分层策略参考 [Docker 最佳实践](https://docs.docker.com/build/building/best-practices/)。
