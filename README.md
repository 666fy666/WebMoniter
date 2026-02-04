<div align="center">

# <img src="web/static/favicon.svg" width="48" height="48" alt="Logo"/> WebMoniter

**多平台监控签到 · 开播提醒 · 多渠道推送**

<sub>监控 · 签到 · 开播提醒 · 推送 · 定时任务 · 配置热重载</sub>

<br/>

[![GitHub Stars](https://img.shields.io/github/stars/666fy666/WebMoniter?style=flat-square&logo=github)](https://github.com/666fy666/WebMoniter)
[![GitHub Forks](https://img.shields.io/github/forks/666fy666/WebMoniter?style=flat-square&logo=github)](https://github.com/666fy666/WebMoniter)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](./LICENSE)
[![Docker](https://img.shields.io/badge/docker-multi--arch-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![APScheduler](https://img.shields.io/badge/scheduler-APScheduler-red?style=flat-square)](https://apscheduler.readthedocs.io/)

[![Docker Image Version (latest semver)](https://img.shields.io/docker/v/fengyu666/webmoniter/latest?style=flat-square&logo=docker&sort=semver)](https://hub.docker.com/r/fengyu666/webmoniter)
[![Docker Pulls](https://img.shields.io/docker/pulls/fengyu666/webmoniter?style=flat-square)](https://hub.docker.com/r/fengyu666/webmoniter)
[![Docker Image Size (latest)](https://img.shields.io/docker/image-size/fengyu666/webmoniter/latest?style=flat-square)](https://hub.docker.com/r/fengyu666/webmoniter)
[![Docker Hub](https://img.shields.io/badge/docker%20hub-fengyu666%2Fwebmoniter-2496ED?style=flat-square&logo=docker)](https://hub.docker.com/r/fengyu666/webmoniter)

**代码仓库**: [GitHub](https://github.com/666fy666/WebMoniter) · [GitCode](https://gitcode.com/qq_35720175/WebMoniter)

</div>

<div align="center">

一个支持 **虎牙直播、微博(超话)、ikuuu、百度贴吧** 等多平台的监控与签到工具。  
使用 **APScheduler** 做任务调度，支持 **10+ 推送通道**（企业微信、钉钉、Telegram、Bark、邮件等），**配置热重载**，开箱即用。

</div>

<br/>

<div align="center">

| [🚀 快速开始](#-快速开始) | [🐳 Docker 部署](#-docker-部署推荐) | [🌐 Web 管理](#-web-管理界面) | [⚙️ 配置说明](#-配置说明) | [📡 API](docs/API.md) | [🏗️ 项目架构](docs/ARCHITECTURE.md) | [🛠 二次开发](docs/SECONDARY_DEVELOPMENT.md) |

</div>

---

## 📋 目录

- [支持的平台和推送通道](#-支持的平台和推送通道)
  - [定时任务支持](#定时任务支持)
- [快速开始](#-快速开始)
  - [Docker 部署](#-docker-部署推荐)
  - [Web 管理界面](#-web-管理界面)
  - [本地安装](#-本地安装)
  - [更新](#-更新)
- [配置说明](#-配置说明)
- [API 调用](docs/API.md)
- [项目架构](docs/ARCHITECTURE.md)
- [二次开发](docs/SECONDARY_DEVELOPMENT.md)
- [常见问题](#-常见问题)
- [参考与致谢](#-参考与致谢)

---

## 📊 支持的平台和推送通道

### 监控平台支持

| 平台类型 | type     | 动态检测 | 开播检测 |
| -------- | -------- | -------- | -------- |
| 虎牙     | huya     | ❌       | ✅       |
| 微博     | weibo    | ✅       | ❌       |

### 定时任务支持

| 任务名称       | 配置节点 / 任务 ID   | 默认执行时间 | 启动时执行 | 说明 |
| -------------- | -------------------- | ------------ | ---------- | ---- |
| 日志清理       | `scheduler`          | 02:00        | ✅         | 按 `cleanup_logs_hour`、`cleanup_logs_minute` 执行，保留天数由 `retention_days` 控制 |
| iKuuu 签到     | `checkin`            | 08:00        | ✅         | `enable: true` 且配置完整时，每日定时签到并在启动时执行一次；支持多账号 `accounts` |
| 百度贴吧签到   | `tieba`              | 08:10        | ✅         | `enable: true` 且配置 Cookie（须含 BDUSS）时执行；支持多 Cookie |
| 微博超话签到   | `weibo_chaohua`      | 23:45        | ✅         | `enable: true` 且配置 Cookie（须含 XSRF-TOKEN）时执行；支持多 Cookie |
| Demo 示例任务  | `plugins.demo_task`  | 08:30        | ✅         | 二次开发示例，不需要可在 `job_registry.TASK_MODULES` 中移除 |

**说明**：所有定时任务在**项目启动时都会立即执行一次**；各签到类任务内部会根据 `enable` 与配置完整性决定是否真正执行，日志清理任务每次都会执行。

### 推送通道支持

| 通道类型           | type              | 推送附带图片 | 说明                                                                                                         |
| ----------------- | ----------------- | ------------ | ------------------------------------------------------------------------------------------------------------ |
| Server酱_Turbo    | serverChan_turbo  | ✅           | 🙅‍♀️不推荐，不用安装app，但免费用户5次/天👉[官网](https://sct.ftqq.com)                                         |
| Server酱_3        | serverChan_3      | ✅           | 🤔需要安装app👉[官网](https://sc3.ft07.com/)                                                                 |
| 企业微信自建应用   | wecom_apps        | ✅           | 😢新用户不再推荐，2022年6月20日之后新创建的应用，需要配置可信IP👉[官网](https://work.weixin.qq.com/wework_admin/frame#apps/createApiApp) |
| 企业微信群聊机器人 | wecom_bot         | ✅           | 🥳推荐，新建群聊添加自定义机器人即可👉[文档](https://developer.work.weixin.qq.com/document/path/99110)        |
| 钉钉群聊机器人     | dingtalk_bot      | ✅           | 🥳推荐，新建群聊添加自定义机器人即可，自定义关键词使用"【"👉[文档](https://open.dingtalk.com/document/robots/custom-robot-access) |
| 飞书自建应用       | feishu_apps       | ✅           | 🤔可以使用个人版，创建应用，授予其机器人权限👉[官网](https://open.feishu.cn/app?lang=zh-CN)                   |
| 飞书群聊机器人     | feishu_bot        | ❌(暂不支持) | 🤩推荐，新建群聊添加自定义机器人即可，自定义关键词使用"【"👉[文档](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot) |
| Telegram机器人    | telegram_bot      | ✅           | 🪜需要自备网络环境👉[文档](https://core.telegram.org/bots)                                                   |
| QQ频道机器人       | qq_bot            | ✅           | 😢需要自行创建机器人，并启用机器人在频道内发言的权限👉[官网](https://q.qq.com/#/app/create-bot)               |
| NapCatQQ          | napcat_qq         | ✅           | 🐧好用，但需要自行部署 NapCatQQ👉[项目地址](https://github.com/NapNeko/NapCatQQ)                            |
| Bark               | bark              | ❌           | 🍎适合苹果系用户，十分轻量，但没法推送图片👉[App Store](https://apps.apple.com/cn/app/id1403753865)         |
| Gotify             | gotify            | ❌           | 🖥️适合自建服务器👉[官网](https://gotify.net)                                                                 |
| Webhook            | webhook           | ✅(POST)     | ⚡️通用的方式，请求格式详见[附录](#webhook-支持的请求格式)                                                   |
| PushPlus           | pushplus          | ✅           | 📱支持多种推送渠道（微信、邮件、Webhook等）👉[官网](https://www.pushplus.plus/)                              |
| WxPusher           | wxpusher          | ✅           | 📱推荐,微信消息实时推送服务，可通过API实时给个人微信推送消息👉[官网](https://wxpusher.zjiecode.com/)              |
| 电子邮件           | email             | ✅           | 📧通用的方式                                                                                                  |

---

## 🚀 快速开始

### 🐳 Docker 部署（推荐）

要求：Docker >= 20.10、Docker Compose >= 2.0，支持 amd64 / arm64。

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
cp config.yml.sample config.yml
# 编辑 config.yml，配置监控任务和推送通道

docker compose up -d
```

访问 `http://localhost:8866`，默认账号 `admin` / `123`。

> 💡 **提示**：`config.yml` 支持热重载（约 5 秒生效），无需重启。数据持久化：`config.yml`、`data/`、`logs/` 已挂载，`docker compose down` 不会丢失。

### 🌐 Web 管理界面

<img src="web/static/web首页.png" alt="首页截图" width="600">

> ⚠️ 默认账号仅用于测试，生产环境请修改登录凭据。

### 📦 本地安装

要求：Python >= 3.10、[uv](https://docs.astral.sh/uv/getting-started/installation/)。

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
uv sync --locked
cp config.yml.sample config.yml
uv run python main.py

# 后台启动（推荐用于长期运行，终端关闭进程不受影响）
uv run python main.py &

// 可选：将日志输出重定向到文件
# uv run python main.py > webmoniter.log 2>&1 &
```

### 🆙 更新

| 部署方式 | 命令 |
|---------|------|
| Docker | `docker compose pull && docker compose up -d` |
| 本地 | `git pull` → `uv sync --locked` → 重启应用 |

配置支持热重载，多数更新无需重启。更新前建议备份 `config.yml`、`data/`。

## ⚙️ 配置说明

- **应用配置**：所有配置项（微博/虎牙监控、iKuuu/贴吧/微博超话签到、调度器、免打扰、推送通道等）的说明与示例均在 **[`config.yml.sample`](config.yml.sample)** 中，以注释形式写在对应字段旁。复制为 `config.yml` 后按需修改即可；修改后**无需重启**，系统支持配置热重载（约 5 秒内生效）。
- **Docker 编排**：Docker 部署时的编排与运行参数（镜像、端口、卷挂载、资源限制、健康检查等）见 **[`docker-compose.yml`](docker-compose.yml)**；可按需修改端口、时区、内存限制等，修改后执行 `docker compose up -d` 使变更生效。

- 监控与推送类型一览见上文 [支持的平台和推送通道](#-支持的平台和推送通道)
- 定时任务一览见 [定时任务支持](#定时任务支持)

---

## 🔌 API 调用

系统提供 RESTful API，便于与其他系统集成或自动化操作，接口基于 FastAPI 实现。

**详细说明**（认证、配置、数据查询、监控状态、日志及 Python/cURL 示例）请参阅 **[API 调用指南](docs/API.md)**。

---

## ❓ 常见问题

**Q: 如何更新 Cookie？**  
A: 直接修改 `config.yml` 中的 Cookie 值，**无需重启容器或程序**。系统支持配置热重载，会在 5 秒内自动检测并应用新的配置。

**Q: 监控任务没有执行怎么办？**  
A: 
1. 检查日志文件 `logs/main_*.log` 或使用 `docker compose logs`
2. 确认配置文件格式正确（YAML 语法）
3. 检查网络连接是否正常
4. 验证 Cookie 是否有效
5. 确认监控任务已启用（`enable: true`）

**Q: 如何调整监控频率？**  
A: 在 `config.yml` 的 `scheduler` 部分修改对应的间隔时间（秒）。**无需重启服务**，系统支持热重载，会在 5 秒内自动检测并更新任务间隔时间。

**Q: 数据库和日志文件在哪里？**  
A: 
- **Docker 部署**：数据库在 `./data/` 目录，日志在 `./logs/` 目录
- **本地部署**：数据库在 `./data/` 目录，日志在 `./logs/` 目录

**Q: Web界面无法访问怎么办？**  
A: 
1. 确认系统已正常启动（检查日志）
2. 确认端口8866未被占用
3. Docker部署时确认端口映射正确（`8866:8866`）
4. 检查防火墙设置，确保8866端口开放

**Q: 免打扰时段内会遗漏消息吗？**  
A: 免打扰时段内，监控任务会**正常执行**并更新数据库，但**不会推送通知**。如果您担心遗漏重要消息，可以查看日志文件或数据库了解监控记录，或关闭免打扰时段功能。

---

## 📄 参考与致谢

本项目参考了 [aio-dynamic-push](https://github.com/nfe-w/aio-dynamic-push) 项目的设计思路和推送通道实现，特此表示感谢！

---

## 📄 许可证

本项目采用 [MIT License](./LICENSE) 许可，允许用于学习、研究和非商业用途。有关详细条款，请查阅 LICENSE 文件。

---

## Contributors

<a href="https://github.com/666fy666/WebMoniter/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=666fy666/WebMoniter" />
</a>

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=666fy666/WebMoniter&type=Date)](https://star-history.com/#666fy666/WebMoniter&Date)

---

<div align="center">

**最后，如果这个项目对你有帮助**  
**请给个 ⭐ Star 呀！**  
**Made with ❤️ by [FY]**
</div>
