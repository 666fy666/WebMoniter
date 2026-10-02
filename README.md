<div align="center">

# WebMoniter

**多平台监控签到 · 开播提醒 · 多渠道推送**

<sub>监控 · 签到 · 开播提醒 · 推送 · 定时任务 · 配置热重载</sub>

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-Web%20UI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-multi--arch-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/r/fengyu666/webmoniter)
[![APScheduler](https://img.shields.io/badge/APScheduler-scheduler-blueviolet?style=flat-square)](https://apscheduler.readthedocs.io/)
[![uv](https://img.shields.io/badge/uv-package%20manager-DE5FE9?style=flat-square)](https://docs.astral.sh/uv/)
[![docs](https://img.shields.io/badge/docs-online-1997B5?style=flat-square&logo=readme&logoColor=white)](https://666fy666.github.io/WebMoniter/)
[![GitHub Stars](https://img.shields.io/github/stars/666fy666/WebMoniter?style=flat-square&logo=github)](https://github.com/666fy666/WebMoniter/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/666fy666/WebMoniter?style=flat-square&logo=github)](https://github.com/666fy666/WebMoniter/forks)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/666fy666/WebMoniter?style=flat-square&logo=github)](https://github.com/666fy666/WebMoniter/commits/main)
[![Docker Pulls](https://img.shields.io/docker/pulls/fengyu666/webmoniter?style=flat-square&logo=docker)](https://hub.docker.com/r/fengyu666/webmoniter)
[![Docker Image Version](https://img.shields.io/docker/v/fengyu666/webmoniter/latest?style=flat-square&logo=docker&label=latest)](https://hub.docker.com/r/fengyu666/webmoniter/tags)
[![Docker Image Size (latest)](https://img.shields.io/docker/image-size/fengyu666/webmoniter/latest?style=flat-square&logo=docker&label=latest%20size)](https://hub.docker.com/r/fengyu666/webmoniter/tags)
[![Docker Image Size (full)](https://img.shields.io/docker/image-size/fengyu666/webmoniter/full?style=flat-square&logo=docker&label=full%20size)](https://hub.docker.com/r/fengyu666/webmoniter/tags)
[![GitHub Release](https://img.shields.io/github/v/release/666fy666/WebMoniter?style=flat-square&logo=github&label=EXE)](https://github.com/666fy666/WebMoniter/releases/latest)

**中文** · [English](docs/README.en-US.md) · [Español](docs/README.es-ES.md) · [日本語](docs/README.ja-JP.md) · [한국어](docs/README.ko-KR.md)

[文档站](https://666fy666.github.io/WebMoniter/) ·
[安装](docs/installation.md) ·
[配置](docs/guides/config.md) ·
[API](docs/API.md) ·
[二次开发](docs/SECONDARY_DEVELOPMENT.md) ·
[Releases](https://github.com/666fy666/WebMoniter/releases/latest)

**代码仓库**：[GitHub](https://github.com/666fy666/WebMoniter) · [GitCode](https://gitcode.com/qq_35720175/WebMoniter)

</div>

---

## 简介

WebMoniter 是一个基于 Python、FastAPI 和 APScheduler 的任务系统，用于统一管理：

- 平台监控：虎牙、微博、哔哩哔哩、抖音、斗鱼、小红书。
- 定时任务：微博 Cookie 刷新、iKuuu、贴吧、微博超话、雨云、阿里云盘、Freenom、天气推送等 **30 个**签到/提醒任务（另含 `demo_task` 示例；清单见 `src/jobs/metadata.py` 的 `TASK_SPECS`）。
- 多渠道推送：企业微信、钉钉、飞书、Telegram、Bark、WxPusher、邮件等 **18 种** type。
- Web 管理：配置编辑、任务管理、数据展示、日志查看、密码管理；桌面端无顶栏，用侧边栏拉手收起/展开导航，手机端底部导航含账户入口。导航、工具栏、弹窗与交互控件采用 iOS 液态玻璃风格，内容区域保持清晰易读；PC 与移动端共用统一设计规范，支持键盘标签切换、可见焦点、44px 触控目标及减少动效/透明度偏好。细节见 [Web 管理界面](docs/guides/web-ui.md)。

配置支持热重载，修改 `config.yml` 后通常约 5 秒内生效。

---

## 功能一览

界面与功能说明见 [文档首页](docs/index.md) 和 [Web 管理界面](docs/guides/web-ui.md)。

<details>
<summary><strong>展开更多项目展示</strong></summary>

### 支持平台

| 平台 | type | 动态 | 开播/下播 |
|:--:|:--:|:--:|:--:|
| 虎牙 | `huya` | 否 | 是 |
| 微博 | `weibo` | 是 | 否 |
| 哔哩哔哩 | `bilibili` | 是 | 是 |
| 抖音 | `douyin` | 否 | 是 |
| 快手（待实测） | `kuaishou` | 否 | 是 |
| 斗鱼 | `douyu` | 否 | 是 |
| 小红书 | `xhs` | 是 | 否 |

### 定时任务节选

| 任务 | 配置节点 | 默认时间 |
|:--:|:--:|:--:|
| 日志清理 | `log_cleanup` | 02:10 |
| 微博 Cookie 刷新 | `weibo` | 21:00 |
| iKuuu 签到 | `checkin` | 08:00 |
| 雨云签到 | `rainyun` | 08:30 |
| 贴吧签到 | `tieba` | 08:10 |
| 微博超话 | `weibo_chaohua` | 23:45 |
| 阿里云盘 | `aliyun` | 05:30 |
| 天气推送 | `weather` | 07:30 |

### 推送通道节选

| 通道 | type | 图文 |
|:--:|:--:|:--:|
| 企业微信群机器人 | `wecom_bot` | 是 |
| 钉钉机器人 | `dingtalk_bot` | 是 |
| 飞书机器人 | `feishu_bot` | 否 |
| Telegram | `telegram_bot` | 是 |
| WxPusher | `wxpusher` | 是 |
| Bark | `bark` | 否 |
| PushPlus | `pushplus` | 是 |

</details>

---

## 快速开始

[首次部署](#docker-first-deploy) · [打开与使用](#docker-first-use) · [更新版本](#docker-update) · [停止与恢复](#docker-stop) · [删除与卸载](#docker-uninstall) · [备份恢复](docs/DEPLOYMENT.md#backup-restore)

### Docker（推荐）

默认使用 **full 镜像**，包含浏览器、驱动与 OCR，适用于 iKuuu、雨云等浏览器任务；`latest` 为精简镜像，不包含这些依赖。只需 HTTP 任务时可按 [镜像选择说明](docker/README.md#image-selection)切换。

#### 首次部署

<a id="docker-first-deploy"></a>

在准备运行服务的电脑或服务器上执行，需要 Git 和 Bash：

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh docker
```

脚本会拉取镜像、后台启动并等待健康检查通过。Ubuntu 22.04/24.04/26.04 缺少 Docker 时会自动安装官方 Docker Engine 与 Compose，需要 root 或 sudo；其他系统先安装 Docker 与 Compose 插件。首次拉取 full 镜像可能较慢。

**已有 Docker Compose 时**，进入项目根目录后，也可用下面的命令代替安装脚本：

```bash
docker compose up -d --pull always --wait --wait-timeout 180
docker compose ps
```

后续 Docker 命令均在项目根目录（含 `compose.yaml`）执行。若提示无权访问 Docker，请给命令加 `sudo`，例如 `sudo docker compose ps`。有自定义 `-f`、`-p`、`--env-file` 参数时，所有维护命令都要沿用相同参数。安装脚本固定使用根目录 `compose.yaml`，自定义部署请直接使用 Compose。

镜像内容以已发布版本为准，`git pull` 不会把源码打进远程镜像。需要运行尚未发布的源码时，使用 [本地构建](docker/README.md#local-build)。旧部署的目录挂载、账户与数据库不会自动迁移，请先备份并参考 [部署指南](docs/DEPLOYMENT.md)。

#### 打开界面并开始使用

<a id="docker-first-use"></a>

本机部署直接打开 **<http://127.0.0.1:8866>**；服务器部署打开 **`http://服务器IP:8866`**。当前 Compose 映射为 `0.0.0.0:8866:8866`，可通过宿主机各网络接口访问；远程访问需在服务器防火墙和云安全组中允许所需来源访问 TCP 8866。对外开放前先修改默认密码，长期访问建议配置 [HTTPS 反向代理](docs/DEPLOYMENT.md#https)。

如果只希望通过 SSH 隧道或宿主机反代访问，将 `compose.yaml` 的端口映射改为 `127.0.0.1:8866:8866` 后执行 `docker compose up -d --wait --wait-timeout 180`。使用 SSH 隧道时，在**自己的电脑**另开终端执行以下命令（替换用户名与服务器地址，并保持终端打开）：

```bash
ssh -N -L 8866:127.0.0.1:8866 用户名@服务器地址
```

再用自己电脑的浏览器打开 **<http://127.0.0.1:8866>**。

1. 首次使用默认账号 **`admin`**、密码 **`123`** 登录，在账户页修改密码。已有账户使用当前密码，环境变量不会覆盖它。
2. 在「配置管理」填写推送渠道、平台账号或 Cookie、监控目标和执行时间，然后启用需要的任务并保存。首次生成的配置关闭业务任务，仅开启日志清理。
3. 在「任务管理」确认任务状态；需要验证时点击「立即运行」（会实际执行任务），在「日志查看」检查结果，在「数据展示」查看监控记录。
4. 配置修改通常约 5 秒内热重载，无需重启。详细操作见 [Web 管理界面](docs/guides/web-ui.md)和 [配置说明](docs/guides/config.md)。

```bash
# 查看运行状态
docker compose ps
# 查看最近 100 行并持续跟踪日志；Ctrl+C 只退出日志查看
docker compose logs --tail=100 -f web-monitor
# 在部署机器上检查服务是否就绪
curl -fsS http://127.0.0.1:8866/health/ready
```

#### 更新到已发布的新版本

<a id="docker-update"></a>

先按 [备份步骤](docs/DEPLOYMENT.md#backup-restore)备份配置和数据，再在原项目目录运行：

```bash
# 同步安装脚本与 Compose 配置；遇到本地修改冲突时先处理，不要强制覆盖
git pull --ff-only
# 拉取镜像；镜像或配置有变化时重建容器，保留数据卷
docker compose up -d --pull always --wait --wait-timeout 180
# 检查结果
docker compose ps
docker compose logs --tail=100 web-monitor
```

每条命令成功后再执行下一条。安装脚本用户也可在 `git pull --ff-only` 后重新运行 `bash install.sh docker`。更新会短暂中断服务；无需先删除容器。若固定了 `WEBMONITER_IMAGE` 版本或 digest，先改为目标版本，并保留原部署的 Compose 参数。

`git pull` 只更新仓库文件；`docker compose pull` 只下载镜像；`docker compose restart` 只重启原容器。**切换到新镜像需要执行上面的 `up` 命令**。失败时先查看日志，按 [回退说明](docs/DEPLOYMENT.md#rollback)恢复旧镜像与配套备份。

#### 停止使用与恢复

<a id="docker-stop"></a>

以下命令按需要单独选择执行，均保留配置、账号、历史数据和日志：

| 目的 | 命令 | 结果 |
|---|---|---|
| 暂时停止 | `docker compose stop` | 停止 Web 与所有定时任务，保留容器 |
| 恢复已停止的容器 | `docker compose start` | 使用原容器继续运行 |
| 重启当前版本 | `docker compose restart` | 不拉取或应用新镜像 |
| 停用并删除容器 | `docker compose down` | 删除容器和项目网络，保留命名卷 |
| 删除容器后重新启用 | `docker compose up -d --wait --wait-timeout 180` | 重新创建容器并使用原数据卷 |

`start` 只适用于容器还在的情况；执行过 `down` 后应使用 `up`。默认重启策略为 `unless-stopped`，手动停止后不会因 Docker 重启而自行恢复，详见 [Docker 重启策略](https://docs.docker.com/engine/containers/start-containers-automatically/)。

#### 删除与卸载

<a id="docker-uninstall"></a>

**方案一：卸载服务，保留数据，便于以后继续使用。**

```bash
docker compose down
```

**方案二：彻底删除此部署的数据。此操作不可撤销；需要留存时先备份。**

```bash
# 删除容器、项目网络以及配置、数据、日志三个命名卷
docker compose down --volumes
```

默认会删除 `webmoniter_config`、`webmoniter_data`、`webmoniter_logs`，包括账号、Cookie、任务记录和日志；再次部署会重新初始化。若自定义了项目名，卷名前缀也会不同。**日常更新不要使用 `--volumes` 或 `-v`。**

可选：容器删除后，移除不再使用的本项目镜像以释放空间：

```bash
docker image rm fengyu666/webmoniter:full
```

精简镜像改为 `fengyu666/webmoniter:latest`；自定义镜像用实际标签。若仍被其他容器使用，先确认用途，不要强制删除。上述命令不会删除源码目录、备份、`.env`、自定义 bind mount 目录，也不会卸载 Docker；不再需要时再单独清理，并移除本项目的反向代理配置。不要使用全局 `docker system prune --volumes` 代替本项目卸载。

#### 数据存放在哪里

| 内容 | 默认命名卷 | 容器内路径 |
|---|---|---|
| 配置 | `webmoniter_config` | `/app/config/config.yml` |
| 数据库、账户、Cookie 与会话 | `webmoniter_data` | `/app/data` |
| 日志 | `webmoniter_logs` | `/app/logs` |

Docker 默认不会读取源码根目录的 `config.yml`，也不会把数据写入仓库的 `./data`、`./logs`。直接在 Web 配置页编辑即可；更新与重建容器保留这些命名卷。备份、恢复、权限和资源限制见 [完整部署指南](docs/DEPLOYMENT.md)。

### 源码运行（Linux）

首次运行先克隆仓库并进入目录（已经完成则跳过）：

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh source
```

自动准备 uv、Python 3.11、Node 24、项目依赖、前端、浏览器/驱动和模型，首次生成配置，随后前台启动。默认账号同样为 `admin / 123`。业务任务默认关闭，登录后按需配置；再次运行会保留配置与数据。浏览器自动安装支持 Linux x64，缺少系统库时使用 sudo 安装；只需要 HTTP 任务可运行 `bash install.sh source --no-browser`。Windows 与其他架构见 [安装说明](docs/installation.md)。

按 `Ctrl+C` 停止。更新前停止程序并备份 `config.yml`、`data/`，然后依次运行：

```bash
git pull --ff-only
bash install.sh source
```

脚本不注册后台服务；停止后即可停用。源码环境清理和彻底删除见 [源码维护说明](docs/installation.md#source-maintenance)。

### 青龙面板

青龙用户可通过环境变量配置，使用 `python -m src.ql <task_id>` 运行定时任务。详见 [青龙面板兼容指南](docs/QINGLONG.md)。

---

## 配置

源码安装脚本会自动创建根目录的 `config.yml`；Docker 存放于配置卷。已有配置不会覆盖，直接在 Web 配置页编辑即可。

配置项说明见：

- [配置说明](docs/guides/config.md)
- [监控与定时任务](docs/guides/tasks.md)
- [推送通道](docs/guides/push-channels.md)

---

## 功能入口

| 功能 | 文档 |
|---|---|
| 安装部署 | [docs/installation.md](docs/installation.md) |
| Web 管理界面 | [docs/guides/web-ui.md](docs/guides/web-ui.md) |
| 任务配置 | [docs/guides/tasks.md](docs/guides/tasks.md) |
| 监控任务 | [docs/guides/tasks/monitors.md](docs/guides/tasks/monitors.md) |
| 签到任务 | [docs/guides/tasks/checkin.md](docs/guides/tasks/checkin.md) |
| 推送通道 | [docs/guides/push-channels.md](docs/guides/push-channels.md) |
| REST API | [docs/API.md](docs/API.md) |
| 架构说明 | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| 二次开发 | [docs/SECONDARY_DEVELOPMENT.md](docs/SECONDARY_DEVELOPMENT.md) |
| 常见问题 | [docs/faq.md](docs/faq.md) |

---

<details>
<summary><strong>开发说明</strong></summary>

```bash
uv sync --locked --extra dev --extra rainyun
uv run ruff check .
uv run pytest -q
npm ci --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
npm run test:e2e --prefix frontend
```

Black 检查修改的 Python 文件，例如 `uv run black --check src/web/routers/data.py`。Node 用于前端构建与测试，生产运行无需 Node 服务。

新增监控、定时任务或推送通道见 [二次开发指南](docs/SECONDARY_DEVELOPMENT.md)，模块边界、数据流和存储恢复见 [架构说明](docs/ARCHITECTURE.md)。任务、通道和配置节以 `src/jobs/metadata.py` 及运行时代码为准，关键测试检查注册完整性、配置映射及执行行为。

</details>

---

## 致谢

部分签到与推送思路参考了以下项目：

- [aio-dynamic-push](https://github.com/nfe-w/aio-dynamic-push)
- [only_for_happly](https://github.com/wd210010/only_for_happly)
- [RainyunCheckIn](https://github.com/FalseHappiness/RainyunCheckIn)
- [Rainyun-Qiandao](https://github.com/Jielumoon/Rainyun-Qiandao)

---

## Contributors

<a href="https://github.com/666fy666/WebMoniter/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=666fy666/WebMoniter" alt="Contributors" />
</a>

---

## 许可证

[MIT License](LICENSE)

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐ Star！**

Made with ❤️ by [FY](https://github.com/666fy666)

</div>
