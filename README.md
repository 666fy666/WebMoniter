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

### Docker

下载源码并进入项目目录后，一条命令安装并启动。Ubuntu 24.04 缺少 Docker 时会自动安装；默认 full 镜像，保留浏览器与 OCR。默认账号 `admin`、密码 `123`，无需提前设置密码。

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh docker
```

远程标签须在本次重构正式发布后使用，当前源码修改尚未发布。构建本地镜像、HTTPS、配置初始化、非 root 权限、备份恢复和版本回退见 [Docker 部署说明](docker/README.md)。新版本采用独立配置、数据和日志命名卷，不自动迁移旧部署。

已有 Docker Compose 时也可以直接运行 `docker compose up -d --pull always --wait`。默认只绑定 `127.0.0.1:8866`，远程访问方式见部署说明。

### 源码运行（Linux）

```bash
bash install.sh source
```

自动准备 uv、Python 3.11、Node 24、项目依赖、前端、浏览器/驱动和模型，首次生成配置，随后前台启动。默认账号同样为 `admin / 123`。业务任务默认关闭，登录后按需配置；再次运行会保留配置与数据。浏览器自动安装支持 Linux x64，缺少系统库时使用 sudo 安装；只需要 HTTP 任务可运行 `bash install.sh source --no-browser`。Windows 与其他架构见 [安装说明](docs/installation.md)。

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
