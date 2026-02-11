# WebMoniter 文档

**多平台监控签到 · 开播提醒 · 多渠道推送**

Web 任务系统（WebMoniter）支持 **虎牙直播、微博** 等平台监控与开播/动态提醒，以及 **iKuuu、百度贴吧、微博超话、雨云、阿里云盘、什么值得买** 等 20+ 定时签到任务；使用 **APScheduler** 调度，支持 **10+ 推送通道**（企业微信、钉钉、飞书、Telegram、Bark、邮件等），**配置热重载**，开箱即用。

---

## 从这里开始

:material-rocket-launch: **快速开始**

使用 Docker 或 Windows 一键包，几分钟内完成部署并访问 Web 管理界面。若已使用青龙面板，可直接拉取 `ql/` 脚本，通过环境变量配置。

[安装与运行](installation.md) · [青龙面板部署](QINGLONG.md)

---

:material-cog: **使用指南**

配置监控与签到、了解 Web 管理界面、选择推送通道。

[配置说明](guides/config.md) · [Web 管理界面](guides/web-ui.md) · [监控与定时任务](guides/tasks.md) · [推送通道](guides/push-channels.md)

---

:material hammer-wrench: **二次开发**

了解项目架构、新增监控/定时任务、对接 API。

[架构概览](ARCHITECTURE.md) · [二次开发指南](SECONDARY_DEVELOPMENT.md) · [API 参考](API.md)

---

:material-help-circle: **常见问题**

Cookie 更新、任务不执行、监控频率、免打扰等。

[常见问题 →](faq.md)

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **多平台监控** | 虎牙开播、微博动态，可扩展更多平台 |
| **定时签到** | 20+ 平台签到（贴吧、微博超话、iKuuu、雨云、阿里云盘等） |
| **多渠道推送** | 企业微信、钉钉、飞书、Telegram、Bark、WxPusher、邮件等 |
| **配置热重载** | 修改 `config.yml` 约 5 秒内生效，无需重启 |
| **Web 管理** | 配置编辑、任务管理、数据查看、日志查看 |
| **RESTful API** | 便于集成与自动化操作 |

---

## 技术栈

- **运行环境**: Python 3.10+
- **调度**: APScheduler
- **Web**: FastAPI + Uvicorn
- **数据**: SQLite (aiosqlite)
- **配置**: YAML，支持热重载

---

## 链接

- **代码仓库**: [GitHub](https://github.com/666fy666/WebMoniter) · [GitCode](https://gitcode.com/qq_35720175/WebMoniter)
- **Docker**: [fengyu666/webmoniter](https://hub.docker.com/r/fengyu666/webmoniter)
- **Releases**: [GitHub Releases](https://github.com/666fy666/WebMoniter/releases)（含 Windows 一键包）
- **许可证**: [MIT License](https://github.com/666fy666/WebMoniter/blob/main/LICENSE)
