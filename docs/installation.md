# 安装与运行

当前版本采用 Vue 前端与单进程 Python 后端。首次管理员默认账号 `admin`、密码 `123`，无需预先设置环境变量。重构版按全新部署设计，旧 API 和旧账户摘要不自动迁移；历史镜像需按对应版本文档使用。

## Docker（推荐）

目标服务器为 Ubuntu 24.04、2 vCPU、2 GB、5 Mbps，选择 full 镜像保留浏览器与 OCR。使用本地 SQLite，不同时部署 MySQL。镜像在 CI 构建，服务器只拉取并运行。

完整步骤、非 root 目录权限、HTTPS、资源限制、Swap、备份恢复与版本回退见 [Docker 部署说明](DEPLOYMENT.md)。Compose 只将 8866 绑定到本机，需要通过 SSH 隧道或 HTTPS 反代访问。两种镜像二选一运行。

下载源码并进入项目目录后运行（Ubuntu 缺少 Docker 时自动安装官方 Engine 与 Compose）：

```bash
bash install.sh docker
```

已有 Docker Compose 时可直接 `docker compose up -d --pull always --wait`。默认 full 镜像，自动拉取、后台启动并等待就绪。以上远程标签须在本次修改正式发布后使用；未发布时按部署文档构建本地镜像。首次业务任务默认关闭，进入配置页填写账号、推送渠道后启用。

## 源码安装与运行（Linux）

同样在项目目录执行一条命令，无需先安装 Python、uv、Node 或手动复制配置：

```bash
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
