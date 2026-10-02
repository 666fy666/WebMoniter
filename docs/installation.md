# 安装与运行

当前版本采用 Vue 前端与单进程 Python 后端。首次管理员默认账号 `admin`、密码 `123`，无需预先设置环境变量。重构版按全新部署设计，旧 API 和旧账户摘要不自动迁移；历史镜像需按对应版本文档使用。

## Docker（推荐）

目标服务器为 Ubuntu 24.04、2 vCPU、2 GB、5 Mbps，选择 full 镜像保留浏览器与 OCR。使用本地 SQLite，不同时部署 MySQL。镜像在 CI 构建，服务器只拉取并运行。

完整步骤、非 root 目录权限、HTTPS、资源限制、Swap、备份恢复与版本回退见 [Docker 部署说明](DEPLOYMENT.md)。当前 Compose 将 8866 绑定到所有宿主机接口，可通过服务器 IP 访问；也可改为仅本机访问并使用 SSH 隧道或 HTTPS 反代。默认 full 与精简镜像二选一运行。

下载源码并进入项目目录后运行（Ubuntu 缺少 Docker 时自动安装官方 Engine 与 Compose）：

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh docker
```

已有 Docker Compose 时可直接 `docker compose up -d --pull always --wait --wait-timeout 180`。默认 full 镜像，自动拉取、后台启动并等待就绪。远程镜像内容以发布版本为准；尚未发布的修改需按部署文档构建本地镜像。首次配置自动生成，无需复制样例；业务任务默认关闭，登录后修改默认密码，在配置页填写账号、推送渠道后启用。

本机浏览器打开 <http://127.0.0.1:8866>；远程服务器打开 `http://服务器IP:8866`，需要在防火墙和云安全组放行所需来源的 TCP 8866，对外开放前修改默认密码。若仅通过 SSH/宿主机反代访问，将端口映射改为 `127.0.0.1:8866:8866` 并重新执行 `up`。使用 SSH 时，在自己的电脑执行并保持连接：

```bash
ssh -N -L 8866:127.0.0.1:8866 用户名@服务器地址
```

再打开同一浏览器地址。长期访问使用 [HTTPS 反代](DEPLOYMENT.md#https)。

### Docker 更新、停止和删除

所有命令在原仓库根目录执行；如原部署带 `-f`、`-p`、`--env-file`，维护时沿用相同参数；Docker 权限不足时加 `sudo`。更新前先 [备份](DEPLOYMENT.md#backup-restore)，然后逐条执行：

```bash
git pull --ff-only
docker compose up -d --pull always --wait --wait-timeout 180
docker compose ps
docker compose logs --tail=100 web-monitor
```

任一步失败先处理错误。固定镜像版本时先更新 `WEBMONITER_IMAGE`；本地构建镜像需重新构建并改用 `--pull never`。`restart` 不更新镜像。

| 需要做什么 | 命令 | 数据影响 |
|---|---|---|
| 暂时停用 | `docker compose stop` | 保留容器、配置与数据 |
| 恢复使用 | `docker compose start` | 启动原容器 |
| 删除容器 | `docker compose down` | 保留全部命名卷 |
| 删除容器后再部署 | `docker compose up -d --wait --wait-timeout 180` | 使用原命名卷 |
| **彻底删除** | `docker compose down --volumes` | **永久删除配置、账户、历史和日志；先备份** |

Docker 默认数据位于 `webmoniter_config`、`webmoniter_data`、`webmoniter_logs` 命名卷中，与源码目录的 `config.yml`、`data/`、`logs/` 分开。卸载与镜像清理的完整说明见 [停止与卸载](DEPLOYMENT.md#stop-uninstall)。

## 源码安装与运行（Linux）

先克隆仓库，再在项目目录运行；已经下载代码则跳过前两行。无需先安装 Python、uv、Node 或手动复制配置：

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh source
```

脚本自动准备 uv、Python 3.11、锁定的 Python 依赖、Node 24、前端静态文件、匹配版本的 Chrome/驱动及全部已使用模型，随后前台启动。默认访问 `http://localhost:8866`，登录 `admin / 123`。首次配置的业务任务关闭，登录后再按需启用。按 Ctrl+C 停止；再次执行相同命令即可启动，并保留已有配置、账户和数据。

工具和浏览器放在项目的 `.runtime/`，Python 环境在 `.venv/`；不会修改 shell 配置。前端输入未改变时复用产物。首次下载浏览器和模型需要较多时间与空间；缺少系统库时，Ubuntu/Debian 会通过 sudo 安装。自动浏览器安装支持 Linux x64；其他架构可自行提供可执行的 `CHROME_BIN` 与 `CHROMEDRIVER_PATH`，或只使用 HTTP 任务。

可选参数：

```bash
bash install.sh source --prepare-only  # 安装完成后退出
bash install.sh source --no-browser    # 跳过浏览器/模型下载，运行 HTTP 任务
```

`--no-browser` 不会修改已有配置；如果已启用依赖浏览器的任务，需要先在配置中关闭它们或补齐浏览器。以后启用浏览器任务时重新运行不带该参数的命令即可。安装失败后修复网络或权限并重复命令，不需要删除配置或数据。

更新源码后仍运行相同命令，脚本会同步锁定依赖并按需重建前端。源码运行不带 Docker 的资源上限或自动重启；2 GB 生产服务器优先用 Docker，镜像在 CI 构建，避免在服务器编译前端。Node 只参与构建，不常驻。

前端开发可运行 `npm run dev --prefix frontend`，Vite 将 API 转发到本机 Python 服务；若 Node 由脚本安装，需要将 `.runtime/node-*/bin` 对应目录加入当前终端 PATH。使用 `WEBMONITER_CONFIG_FILE`、`WEBMONITER_DATA_DIR`、`WEBMONITER_LOG_DIR` 隔离实例；生产同一数据目录只运行一个 Web／调度进程。

### 源码更新、停止与清理

<a id="source-maintenance"></a>

1. 在运行终端按 `Ctrl+C`，等待进程退出。安装脚本不创建 systemd 服务；若自行配置了进程管理器，先通过该管理器停用。
2. 在仓库根目录备份配置与整个数据目录，日志可选。以下示例使用默认路径，并把备份放在仓库外：

```bash
(
set -eu
umask 077
backup_dir="../webmoniter-source-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
cp -a config.yml data "$backup_dir/"
chmod -R go-rwx "$backup_dir"
printf '备份位置：%s\n' "$backup_dir"
)
```

3. 备份成功后，逐条更新并重新运行：

```bash
git pull --ff-only
bash install.sh source
```

若原来只运行 HTTP 任务，继续使用 `bash install.sh source --no-browser`。`git pull` 遇到本地修改冲突时先处理，不要强制覆盖配置。设置了自定义路径变量时，备份实际目录，启动时继续提供原来的变量。

暂时停用只需保持程序停止。若只想清理可重建的环境、保留配置和数据，在已停止的仓库根目录执行：

```bash
rm -rf -- .venv .runtime frontend/node_modules frontend/dist
```

再次运行安装脚本会重新准备环境。**彻底删除源码部署**时，先确认外部备份可用、进程与自建启动服务已停用，再到上级目录交互式删除仓库（仅适用于克隆目录确实名为 `WebMoniter`）：

```bash
cd ..
rm -ri -- WebMoniter
```

这会删除仓库内的配置、数据库、日志及本地修改，不能撤销；自定义外部数据目录和外部备份需另行处理。源码删除不会清除 Docker 数据卷，也不会卸载系统级 Python、Node、浏览器或 Docker。

## Windows 发行包

发布工作流会先构建 Vue，再把静态产物打入 PyInstaller 目录。下载对应版本的发行包，复制样例配置并编辑。在 PowerShell 直接运行，默认账号 `admin`、密码 `123`：

```powershell
.\WebMoniter.exe
```

浏览器及模型依赖按该发行包实际包含内容配置；本轮未在真实 Windows 机器执行打包产物验证。

## 青龙

保留 `python -m src.ql <task_id>` 与环境变量配置，详见 [青龙指南](QINGLONG.md)。单次 CLI 不启动 Web，不要求 Web 管理员密码。不要将青龙和 Web 调度器同时配置为执行同一副作用任务。

## 验证与排障

- `/health/live` 失败：检查容器是否存活、端口和启动日志。
- `/health/ready` 失败：检查本地数据目录权限、SQLite 与任务执行服务；第三方平台下线不影响就绪检查。
- 首次登录使用 `admin / 123`；若已存在账户，请使用该账户当前密码，环境变量不会覆盖它。
- 浏览器失败：检查浏览器与驱动版本、模型校验和非 root 可读权限。
- 内存或延迟超标：用基准脚本复测，减少启用目标和轮询频率，不增加 Web worker 数量。

本轮实测、截图、镜像体积与仍待验证的真实手机、arm64 和 24 小时长测见 [审查报告](REFACTOR_AUDIT.md)。早期 iKuuu 模型验证数据仍保留于 `docs/assets/validation/ikuuu-*.json`；模型能加载不代表真实平台识别率或签到成功率。
