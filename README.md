# Web监控系统

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)

一个基于 Python 的异步 Web 监控系统，支持多平台监控任务（虎牙直播、微博等），使用 APScheduler 进行任务调度，支持企业微信推送和 SQLite 数据存储。

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [配置说明](#-配置说明) • [使用指南](#-使用指南) • [Docker 部署](#-使用-docker-运行) • [开发指南](#-开发指南)

</div>

---

## 📋 目录

- [快速开始](#-快速开始)
- [使用指南](#-使用指南)
- [配置说明](#-配置说明)
- [开发指南](#-开发指南)
- [常见问题](#-常见问题)

---

## ✨ 功能特性

- 🎯 **多平台监控**：支持虎牙直播、微博等平台监控，可轻松扩展更多平台
- ⏰ **灵活调度**：基于 APScheduler 的任务调度系统，支持间隔任务和定时任务
- 📊 **数据持久化**：SQLite 本地数据库存储监控数据，自动管理表结构
- 📱 **多渠道推送**：支持 Server酱、企业微信、钉钉、飞书、Telegram、QQ、Bark、Gotify、Webhook、邮件等多种推送方式
- 📝 **智能日志**：完善的日志记录和自动清理机制，支持按日期分割
- 🚀 **高性能异步**：基于 asyncio 的异步架构，支持高并发监控任务
- ⚙️ **配置热重载**：基于 YAML 文件的配置管理，支持运行时热重载
- 🔄 **Cookie 管理**：智能 Cookie 缓存管理，自动处理失效和更新
- 🛡️ **错误处理**：完善的异常处理和重试机制，确保系统稳定运行

## 🛠️ 技术栈

- **语言**: Python >= 3.10
- **异步框架**: asyncio, aiohttp
- **任务调度**: APScheduler
- **数据库**: SQLite (aiosqlite)
- **配置管理**: pydantic, pyyaml
- **依赖管理**: uv
- **代码质量**: black, ruff

## 🚀 快速开始

### 环境要求

- Python >= 3.10
- uv (Python 包管理器)

### 安装步骤

```bash
# 1. 克隆项目
git clone <repository-url>
cd WebMoniter

# 2. 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. 安装项目依赖
uv sync

# 4. 复制并编辑配置文件
cp config.yml.sample config.yml
# 编辑 config.yml，配置监控任务和推送通道

# 5. 启动系统
uv run python main.py  # 前台运行
# 或
nohup uv run python main.py > /dev/null 2>&1 &  # 后台运行
```

系统会自动创建 `data.db` 数据库文件并初始化表结构。

## 📖 使用指南

### Docker 部署（推荐）

```bash
# 1. 准备配置文件
cp config.yml.sample config.yml
# 编辑 config.yml，填入监控配置和推送通道

# 2. 启动服务
docker compose up -d

# 3. 查看日志
docker compose logs -f
```

所有数据（配置文件、数据库、日志）会自动保存到本地，删除容器不会丢失数据。

#### Docker 常用操作

```bash
# 查看状态
docker compose ps

# 查看日志
docker compose logs -f

# 停止/重启/更新
docker compose stop      # 停止
docker compose restart   # 重启（修改配置后需要重启）
docker compose pull && docker compose up -d  # 更新到最新版本

# 完全卸载
docker compose down
docker rmi fengyu666/web-monitor:latest
rm -f data.db* config.yml cookie_cache.json && rm -rf logs data
```

### 其他部署方式

**systemd 服务**：创建 `/etc/systemd/system/web-monitor.service`，参考示例配置。

**GitHub Actions CI/CD**：推送到 `main`/`master` 分支或创建 `v*` 标签时自动构建 Docker 镜像。需要在 GitHub 仓库设置中添加 `DOCKER_USERNAME` 和 `DOCKER_PASSWORD` Secrets。

## ⚙️ 配置说明

### 推送通道配置

支持多种推送通道：`serverChan_turbo`、`serverChan_3`、`wecom_apps`、`wecom_bot`、`dingtalk_bot`、`feishu_apps`、`feishu_bot`、`telegram_bot`、`qq_bot`、`napcat_qq`、`bark`、`gotify`、`webhook`、`email`。

```yaml
push_channel:
  - name: 推送通道名称
    enable: true
    type: 通道类型
    # ... 其他通道特定配置
```

详细配置示例请参考 `config.yml.sample` 文件。

### 监控任务配置

**微博监控**：
```yaml
weibo:
  cookie: your_weibo_cookie  # 从浏览器开发者工具获取
  uids: uid1,uid2,uid3
  concurrency: 2  # 建议 2-5
```

**虎牙监控**：
```yaml
huya:
  user_agent: your_user_agent
  cookie: your_huya_cookie  # 可选
  rooms: room1,room2,room3  # 房间号从 URL 获取
  concurrency: 10  # 建议 5-10
```

**调度器配置**：
```yaml
scheduler:
  huya_monitor_interval_seconds: 65
  weibo_monitor_interval_seconds: 300
  cleanup_logs_hour: 2
  cleanup_logs_minute: 0
```

## 🔧 添加新的监控任务

1. 在 `monitors/` 目录下创建监控类，继承 `BaseMonitor`
2. 在 `main.py` 中创建运行函数
3. 在 `register_monitors()` 中注册任务

详细示例请参考现有监控任务实现。

## 💻 开发指南

```bash
# 安装开发依赖
uv sync --extra dev

# 代码格式化
uv run black .
uv run ruff check --fix .

# 运行测试
uv run pytest
```

## ❓ 常见问题

**Q: 如何更新 Cookie？**  
A: 直接修改 `config.yml` 中的 Cookie 值，系统会在下次执行监控任务时自动重新加载配置。

**Q: 监控任务没有执行怎么办？**  
A: 检查日志文件 `logs/main_*.log`，确认配置文件格式正确、网络连接正常、Cookie 有效。

**Q: 如何调整监控频率？**  
A: 在 `config.yml` 的 `scheduler` 部分修改对应的间隔时间（秒）。

**Q: 数据库和日志文件在哪里？**  
A: 数据库文件 `data.db` 在项目根目录，日志文件在 `logs/` 目录。系统会自动清理 3 天前的日志文件。

## ⚠️ 注意事项

- **并发控制**：微博监控建议并发数 2-5，虎牙监控可设置 5-10
- **Cookie 管理**：定期更新 Cookie，失效时会记录错误日志
- **数据备份**：建议定期备份 `data.db` 和 `config.yml`
- **日志清理**：系统自动清理 3 天前的日志文件
- **网络环境**：确保服务器可以访问目标网站（虎牙、微博等）

## 🤝 贡献指南

欢迎贡献代码！提交 Pull Request 前请确保：
- ✅ 代码已通过 `black` 格式化和 `ruff` 检查
- ✅ 添加了必要的注释和文档
- ✅ 测试了新功能（如果适用）

如果发现问题，请在 [Issues](../../issues) 中报告。

## 📄 许可证

本项目采用 MIT 许可证。

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐ Star！**

Made with ❤️ by [FY]

</div>
