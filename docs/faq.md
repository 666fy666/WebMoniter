# 常见问题

---

??? question "如何更新 Cookie？"
    在 Web「配置管理」修改 Cookie 并保存，**无需重启容器或程序**。系统通常约 5 秒内应用新配置。源码默认配置为仓库根目录的 `config.yml`，Docker 默认为配置卷中的 `/app/config/config.yml`；修改宿主机根目录的 `config.yml` 不会影响默认 Docker 部署。

---

??? question "监控任务没有执行怎么办？"
    1. 查看日志：`logs/main_*.log`（总日志）或 `logs/task_{job_id}_*.log`（任务专属日志），也可在 Web 日志页面切换查看
    2. 确认 `config.yml` 格式正确（YAML 语法）
    3. 检查网络与 Cookie 是否有效
    4. 确认监控任务已启用（如 `enable: true`，或对应监控块已配置）

---

??? question "如何调整监控频率？"
    在 `config.yml` 中修改对应间隔（秒）即可，无需重启：
    - 微博：`weibo.monitor_interval_seconds`（默认 300）；`weibo.concurrency`（默认 3）
    - 虎牙：`huya.monitor_interval_seconds`（默认 65）；`huya.concurrency`（默认 7）
    - 哔哩哔哩：`bilibili.monitor_interval_seconds`（默认 60）
    - 抖音：`douyin.monitor_interval_seconds`（默认 30）
    - 斗鱼：`douyu.monitor_interval_seconds`（默认 300）
    - 小红书：`xhs.monitor_interval_seconds`（默认 300）

---

??? question "数据库和日志文件在哪里？"
    | 部署方式 | 配置 | 数据 | 日志 |
    |---|---|---|---|
    | Docker 默认部署 | `webmoniter_config` 卷中的 `/app/config/config.yml` | `webmoniter_data` 卷，容器内 `/app/data` | `webmoniter_logs` 卷，容器内 `/app/logs` |
    | 源码默认部署 | 根目录 `config.yml` | `./data/` | `./logs/` |

    自定义 Compose 项目名会改变卷名前缀；自定义目录变量或 bind mount 时以实际配置为准。Docker 数据不在仓库目录中，复制方法见 [备份与恢复](DEPLOYMENT.md#backup-restore)。

    日志目录内含：
    - `main_YYYYMMDD.log`：当日总日志
    - `task_{任务ID}_YYYYMMDD.log`：各任务专属日志

---

??? question "Web 界面无法访问怎么办？"
    1. 在部署机器的项目根目录执行 `docker compose ps` 与 `docker compose logs --tail=100 web-monitor`，确认启动状态；源码运行查看终端日志。
    2. 在部署机器执行 `curl -fsS http://127.0.0.1:8866/health/ready`。失败时检查端口占用、目录权限和日志。
    3. 当前 Docker 映射为 `0.0.0.0:8866:8866`，远程访问 `http://服务器IP:8866` 时检查防火墙和云安全组是否允许所需来源的 TCP 8866。如果自行改成了 `127.0.0.1:8866:8866`，则仅允许本机访问；在自己的电脑运行 `ssh -N -L 8866:127.0.0.1:8866 用户名@服务器地址` 并保持连接，再打开 <http://127.0.0.1:8866>，或使用 [HTTPS 反代](DEPLOYMENT.md#https)。
    4. 自己电脑的 8866 被占用时，将隧道改为 `ssh -N -L 18866:127.0.0.1:8866 用户名@服务器地址`，浏览器改为 <http://127.0.0.1:18866>。无需修改服务器配置。

---

??? question "Docker 更新后为什么还是旧版本？"
    `git pull` 只更新仓库文件，不构建远程镜像；`docker compose pull` 只下载镜像，`restart` 只重启原容器。确认目标镜像已发布，在原部署目录执行 `docker compose up -d --pull always --wait --wait-timeout 180` 才会应用新镜像。若固定了 `WEBMONITER_IMAGE` 版本或 digest，先修改为目标版本；本地构建则重新构建并使用 `--pull never`。更新前先 [备份](DEPLOYMENT.md#backup-restore)，不要删除数据卷。

---

??? question "stop、down 和 down --volumes 有什么区别？"
    - `docker compose stop`：停止 Web 与任务，保留容器和数据；用 `docker compose start` 恢复。
    - `docker compose down`：删除容器和项目网络，保留命名卷；用 `docker compose up -d --wait --wait-timeout 180` 恢复。
    - **`docker compose down --volumes`（或 `down -v`）**：额外永久删除配置、数据和日志命名卷；仅用于彻底卸载或明确需要重新初始化时，执行前先备份。

    删除项目源码目录不会删除 Docker 命名卷。详细清理范围见 [停止与卸载](DEPLOYMENT.md#stop-uninstall)。

---

??? question "安装成功，但 Docker 命令提示权限不足或等待健康检查超时？"
    安装脚本会在需要时自动通过 sudo 调用 Docker；日常维护可能也需要 `sudo docker compose ps`、`sudo docker compose logs --tail=100 web-monitor`。若连 Docker 服务都无法连接，先确认服务已启动。

    `--wait-timeout 180` 超时不代表数据丢失，也不代表容器已自动删除。先看状态和日志，修复后重新执行启动命令，不要用 `down --volumes` 排障。Compose 不识别 `--wait` 时需更新 Compose 插件。

---

??? question "默认密码登录失败，改环境变量也没有生效？"
    `admin / 123` 只用于首次创建管理员。已有数据卷中的账户使用当前密码，`WEBMONITER_ADMIN_USERNAME`、`WEBMONITER_ADMIN_PASSWORD` 不会覆盖已有账户；登录后通过账户页改密码。若已配置 `WEBMONITER_SECURE_COOKIE=1`，请通过 HTTPS 登录，通过 HTTP/SSH 隧道访问则保持该项为 `0`，修改后用 `docker compose up -d --wait --wait-timeout 180` 应用。

---

??? question "本地运行时如何停止？Ctrl+C 卡住怎么办？"
    在运行 `bash install.sh source` 的终端按 `Ctrl+C` 即可停止。程序会停止调度器、关闭 Web 服务、配置监控器和数据库连接。再次执行安装命令可继续运行；更新和卸载见 [源码维护说明](installation.md#source-maintenance)。

    项目会对同步网络请求、浏览器任务等阻塞场景设置兜底：正常会在数秒内退出；如果关闭流程仍被任务阻塞，约 12 秒后会强制退出；再次按 `Ctrl+C` 会立即强制退出。

---

??? question "免打扰时段内会遗漏消息吗？"
    免打扰时段内，监控任务会**照常执行**并更新数据库，但**不会推送通知**。若担心遗漏，可查看日志或数据记录，或关闭免打扰配置。

---

??? question "青龙面板如何部署？"
    在青龙「环境变量」中添加 `WEBMONITER_*` 前缀的变量（如 `WEBMONITER_CHECKIN_ENABLE`、`WEBMONITER_CHECKIN_EMAIL`），拉取或克隆项目后，在「定时任务」中执行 `python -m src.ql ikuuu_checkin` 等命令。推送自动走青龙内置通知（QLAPI）。详见 [青龙面板兼容指南](QINGLONG.md)。

---

??? question "Docker 部署下雨云签到如何启用？"
    根目录 `compose.yaml` 和 `bash install.sh docker` 已默认使用 **full 镜像**，在配置页填写雨云账号并启用即可。若曾切换到 `latest` 精简版，它不包含 Chromium 与浏览器/OCR 依赖；请将根目录 `.env` 的 `WEBMONITER_IMAGE` 改为 `fengyu666/webmoniter:full`，再执行 `docker compose up -d --pull always --wait --wait-timeout 180`。微博 Cookie 刷新、iKuuu 等浏览器任务同样使用 full。完整镜像默认提供 `/usr/bin/chromium` 与 `/usr/bin/chromedriver`；自定义路径可用 `CHROME_BIN`、`CHROMEDRIVER_PATH`，雨云也可使用其配置字段。

---

??? question "定时任务为什么显示「当天已经运行过了，跳过该任务」？"
    定时任务默认会检查当天是否已运行过（通过 `task_run_history` 表记录），若已运行则跳过，避免重复执行。程序重启或定时触发时都会进行此检查。仅当任务返回 `TASK_SUCCESS` 时才会写入记录；返回 `TASK_FAILED` 或抛出未捕获异常都不会写入，允许后续重试。若需立即再执行一次，可通过 Web 管理界面「任务管理」页面的「立即运行」手动触发，会绕过该检查并强制执行。
