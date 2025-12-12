# Web监控系统

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)

一个基于 Python 的异步 Web 监控系统，支持多平台监控任务（虎牙直播、微博等），使用 APScheduler 进行任务调度，支持企业微信推送和 SQLite 数据存储。

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [配置说明](#-配置说明) • [使用指南](#-使用指南) • [开发指南](#-开发指南)

</div>

---

## 📋 目录

- [功能特性](#-功能特性)
- [技术栈](#-技术栈)
- [快速开始](#-快速开始)
  - [环境要求](#环境要求)
  - [安装步骤](#安装步骤)
  - [配置设置](#配置设置)
- [使用指南](#-使用指南)
  - [启动监控系统](#启动监控系统)
  - [使用 systemd 管理服务](#使用-systemd-管理服务)
  - [监控任务配置](#监控任务配置)
- [配置说明](#-配置说明)
  - [推送通道配置](#推送通道配置)
  - [微博监控配置](#微博监控配置)
  - [虎牙监控配置](#虎牙监控配置)
  - [调度器配置](#调度器配置)
- [项目结构](#-项目结构)
- [添加新的监控任务](#-添加新的监控任务)
- [开发指南](#-开发指南)
  - [开发环境设置](#开发环境设置)
  - [代码格式化](#代码格式化)
  - [运行测试](#运行测试)
- [常见问题](#-常见问题)
- [注意事项](#-注意事项)
- [贡献指南](#-贡献指南)
- [许可证](#-许可证)

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

#### 1. 克隆项目

```bash
git clone <repository-url>
cd WebMoniter
```

#### 2. 安装 uv（如果尚未安装）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 3. 安装项目依赖

```bash
uv sync
```

#### 4. 配置文件设置

复制示例配置文件并修改：

```bash
cp config.yml.sample config.yml
```

编辑 `config.yml` 文件，配置必要的参数（详见[配置说明](#-配置说明)）。

> **注意**：`config.yml` 文件不会被提交到 git，请妥善保管。

#### 5. 启动系统

```bash
# 前台运行
uv run python main.py

# 后台运行
nohup uv run python main.py > /dev/null 2>&1 &
```

系统会自动创建 `data.db` 数据库文件并初始化表结构，无需手动配置。

## 📖 使用指南

### 启动监控系统

#### 前台运行（推荐用于测试）

```bash
uv run python main.py
```

前台运行时，日志会同时输出到控制台和文件。

#### 后台运行（推荐用于生产环境）

```bash
nohup uv run python main.py > /dev/null 2>&1 &
```

后台运行时，日志仅输出到文件。

### 使用 systemd 管理服务

创建 `/etc/systemd/system/web-monitor.service`：

```ini
[Unit]
Description=Web Monitor Service
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/WebMoniter
ExecStart=/home/your_username/.local/bin/uv run python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

管理命令：

```bash
# 重新加载 systemd 配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start web-monitor

# 设置开机自启
sudo systemctl enable web-monitor

# 查看服务状态
sudo systemctl status web-monitor

# 查看日志
sudo journalctl -u web-monitor -f
```

### 监控任务配置

监控任务的执行频率在 `config.yml` 中配置：

```yaml
scheduler:
  huya_monitor_interval_seconds: 65      # 虎牙监控间隔（秒）
  weibo_monitor_interval_seconds: 300    # 微博监控间隔（秒）
  cleanup_logs_hour: 2                   # 日志清理时间（小时）
  cleanup_logs_minute: 0                 # 日志清理时间（分钟）
```

系统启动时会立即执行一次所有监控任务，之后按照配置的间隔时间定期执行。

## ⚙️ 配置说明

### 推送通道配置

系统支持多种推送通道，可以在 `push_channel` 配置项中配置多个推送通道。每个通道都有独立的配置，可以同时启用多个通道。

#### 基本配置格式

```yaml
push_channel:
  - name: 推送通道名称        # 通道名称，唯一，可自定义
    enable: true              # 是否启用
    type: 通道类型             # 通道类型，详见下方说明
    # ... 其他通道特定配置
```

#### 支持的推送通道类型

1. **Server酱 Turbo** (`serverChan_turbo`)
   ```yaml
   - name: 推送通道_Server酱_Turbo
     enable: true
     type: serverChan_turbo
     send_key: your_send_key  # 从 https://sct.ftqq.com 获取
   ```

2. **Server酱 3** (`serverChan_3`)
   ```yaml
   - name: 推送通道_Server酱_3
     enable: true
     type: serverChan_3
     send_key: your_send_key
     uid: your_uid
     tags: 标签1|标签2  # 可选，多个标签用竖线分隔
   ```

3. **企业微信应用** (`wecom_apps`)
   ```yaml
   - name: 推送通道_企业微信应用
     enable: true
     type: wecom_apps
     corp_id: your_corp_id
     agent_id: your_agent_id
     corp_secret: your_corp_secret
   ```

4. **企业微信机器人** (`wecom_bot`)
   ```yaml
   - name: 推送通道_企业微信机器人
     enable: true
     type: wecom_bot
     key: your_webhook_key
   ```

5. **钉钉机器人** (`dingtalk_bot`)
   ```yaml
   - name: 推送通道_钉钉机器人
     enable: true
     type: dingtalk_bot
     access_token: your_access_token
   ```

6. **飞书自建应用** (`feishu_apps`)
   ```yaml
   - name: 推送通道_飞书自建应用
     enable: true
     type: feishu_apps
     app_id: your_app_id
     app_secret: your_app_secret
     receive_id_type: open_id  # open_id/user_id/union_id/email/chat_id
     receive_id: your_receive_id
   ```

7. **飞书机器人** (`feishu_bot`)
   ```yaml
   - name: 推送通道_飞书机器人
     enable: true
     type: feishu_bot
     webhook_key: your_webhook_key
   ```

8. **Telegram 机器人** (`telegram_bot`)
   ```yaml
   - name: 推送通道_Telegram机器人
     enable: true
     type: telegram_bot
     api_token: your_api_token
     chat_id: your_chat_id
   ```

9. **QQ 机器人** (`qq_bot`)
   ```yaml
   - name: 推送通道_QQ机器人
     enable: true
     type: qq_bot
     base_url: https://api.sgroup.qq.com
     app_id: your_app_id
     token: your_token
     push_target_list:
       - guild_name: "频道1"
         channel_name_list:
           - "子频道11"
           - "子频道12"
   ```

10. **NapCatQQ** (`napcat_qq`)
    ```yaml
    - name: 推送通道_NapCatQQ
      enable: true
      type: napcat_qq
      api_url: http://localhost:3000
      token: your_token
      user_id: your_user_id  # 与 group_id 二选一
      group_id: your_group_id
      at_qq: "all"  # 需要 @ 的 QQ 号，"all" 表示@全体成员
    ```

11. **Bark** (`bark`)
    ```yaml
    - name: 推送通道_Bark
      enable: true
      type: bark
      server_url: https://api.day.app  # 可选，默认值
      key: your_bark_key
    ```

12. **Gotify** (`gotify`)
    ```yaml
    - name: 推送通道_Gotify
      enable: true
      type: gotify
      web_server_url: https://push.example.com/message?token=your_token
    ```

13. **Webhook** (`webhook`)
    ```yaml
    - name: 推送通道_Webhook
      enable: true
      type: webhook
      webhook_url: https://xxx.com?title={{title}}&content={{content}}
      request_method: GET  # GET 或 POST
    ```

14. **Email** (`email`)
    ```yaml
    - name: 推送通道_Email
      enable: true
      type: email
      smtp_host: smtp.example.com
      smtp_port: 465
      smtp_ssl: true   # 465端口使用SSL
      smtp_tls: false  # 587端口使用TLS
      sender_email: your_email@example.com
      sender_password: your_password
      receiver_email: recipient@example.com
    ```

#### 配置示例

完整的推送通道配置示例请参考 `config.yml.sample` 文件。

### 微博监控配置

```yaml
weibo:
  cookie: your_weibo_cookie                # 微博 Cookie（必需）
  uids: uid1,uid2,uid3                     # 逗号分隔的 UID 列表
  concurrency: 2                           # 并发数，建议 2-5，避免触发限流
```

**获取微博 Cookie**：
1. 登录微博网页版
2. 打开浏览器开发者工具（F12）
3. 在 Network 标签中找到任意请求
4. 复制请求头中的 `Cookie` 值

### 虎牙监控配置

```yaml
huya:
  user_agent: your_user_agent              # User-Agent（必需）
  cookie: your_huya_cookie                 # 虎牙 Cookie（可选）
  rooms: room1,room2,room3                # 逗号分隔的房间号列表
  concurrency: 10                          # 并发数，建议 5-10
```

**获取虎牙房间号**：
- 访问虎牙直播间，URL 中的数字即为房间号
- 例如：`https://www.huya.com/123456` 中的 `123456` 就是房间号

### 调度器配置

```yaml
scheduler:
  huya_monitor_interval_seconds: 65        # 虎牙监控间隔（秒），默认 65 秒
  weibo_monitor_interval_seconds: 300      # 微博监控间隔（秒），默认 300 秒（5 分钟）
  cleanup_logs_hour: 2                     # 日志清理时间（小时），默认 2 点
  cleanup_logs_minute: 0                   # 日志清理时间（分钟），默认 0 分
```

## 📁 项目结构

```
WebMoniter/
├── main.py                    # 主入口文件
├── pyproject.toml             # 项目配置和依赖
├── uv.lock                    # 依赖锁定文件
├── config.yml.sample          # 配置文件示例
├── src/                       # 核心模块
│   ├── __init__.py
│   ├── config.py              # 配置管理（支持热重载）
│   ├── database.py            # 数据库操作
│   ├── scheduler.py           # 任务调度器
│   ├── monitor.py             # 监控基类
│   ├── push_channel/          # 推送通道模块
│   │   ├── __init__.py
│   │   ├── _push_channel.py   # 推送通道基类
│   │   ├── manager.py         # 统一推送管理器
│   │   └── ...                # 各种推送通道实现
│   ├── log_manager.py         # 日志管理
│   ├── cookie_cache_manager.py # Cookie 缓存管理
│   └── cookie_cache.py        # Cookie 缓存实现
├── monitors/                  # 监控模块
│   ├── __init__.py
│   ├── huya_monitor.py        # 虎牙直播监控
│   └── weibo_monitor.py       # 微博监控
└── logs/                      # 日志目录（自动创建）
```

## 🔧 添加新的监控任务

添加新的监控任务非常简单，只需三步：

### 1. 创建监控类

在 `monitors/` 目录下创建新的监控类，继承 `BaseMonitor`：

```python
from src.monitor import BaseMonitor
from src.config import AppConfig

class NewPlatformMonitor(BaseMonitor):
    """新平台监控类"""
    
    def __init__(self, config: AppConfig):
        super().__init__(config)
        # 初始化你的监控逻辑
    
    async def monitor(self):
        """执行监控逻辑"""
        # 实现监控逻辑
        pass
```

### 2. 创建运行函数

在 `main.py` 中创建运行函数：

```python
async def run_new_monitor():
    """运行新监控任务（支持配置热重载）"""
    config = get_config(reload=True)
    async with NewPlatformMonitor(config) as monitor:
        await monitor.run()
```

### 3. 注册任务

在 `register_monitors()` 函数中注册任务：

```python
async def register_monitors(scheduler: TaskScheduler):
    # ... 其他任务 ...
    
    # 新监控任务
    scheduler.add_interval_job(
        func=run_new_monitor,
        minutes=5,
        job_id="new_monitor",
    )
```

## 💻 开发指南

### 开发环境设置

安装开发依赖：

```bash
uv sync --extra dev
```

### 代码格式化

项目使用 `black` 和 `ruff` 进行代码格式化和检查：

```bash
# 使用 black 格式化代码
uv run black .

# 使用 ruff 检查代码
uv run ruff check .

# 自动修复可修复的问题
uv run ruff check --fix .
```

### 运行测试

```bash
uv run pytest
```

## ❓ 常见问题

### Q: 如何更新 Cookie？

A: 直接修改 `config.yml` 文件中的 Cookie 值，系统会在下次执行监控任务时自动重新加载配置。

### Q: 监控任务没有执行怎么办？

A: 
1. 检查日志文件 `logs/main_*.log` 查看错误信息
2. 确认配置文件 `config.yml` 格式正确
3. 检查网络连接是否正常
4. 确认 Cookie 是否有效

### Q: 如何调整监控频率？

A: 在 `config.yml` 的 `scheduler` 部分修改对应的间隔时间（秒）。

### Q: 数据库文件在哪里？

A: 数据库文件 `data.db` 会自动创建在项目根目录。

### Q: 日志文件占用空间太大怎么办？

A: 系统会自动清理 3 天前的日志文件，也可以手动删除 `logs/` 目录下的旧日志文件。

### Q: 支持哪些推送方式？

A: 目前支持多种推送方式，包括：
- Server酱（Turbo 和 3）
- 企业微信（应用和机器人）
- 钉钉机器人
- 飞书（自建应用和机器人）
- Telegram 机器人
- QQ 机器人（官方和 NapCatQQ）
- Bark
- Gotify
- Webhook
- Email

可以在 `push_channel` 配置中启用多个推送通道，系统会同时向所有启用的通道发送消息。

## ⚠️ 注意事项

1. **并发控制**
   - 微博监控建议并发数设置为 2-5，避免触发限流
   - 虎牙监控可以设置更高（5-10）

2. **Cookie 管理**
   - 定期更新微博和虎牙的 Cookie，避免失效
   - Cookie 失效时系统会记录错误日志，请及时检查

3. **数据库存储**
   - 数据库文件 `data.db` 存储在项目根目录
   - 系统会自动创建和初始化表结构
   - 建议定期备份数据库文件

4. **日志管理**
   - 日志文件存储在 `logs/` 目录
   - 系统会自动清理 3 天前的日志文件
   - 定期检查日志目录大小，避免占用过多磁盘空间

5. **systemd 服务**
   - 修改配置文件后需执行 `sudo systemctl daemon-reload`
   - 确保 `ExecStart` 路径正确（使用 `which uv` 查看 uv 路径）
   - 检查服务用户权限，确保可以访问项目目录和写入日志

6. **网络环境**
   - 确保服务器可以访问目标网站（虎牙、微博等）
   - 如果使用代理，需要在代码中配置代理设置

## 🤝 贡献指南

欢迎贡献代码！在提交 Pull Request 之前，请确保：

1. ✅ 代码已通过 `black` 格式化
2. ✅ 代码已通过 `ruff` 检查
3. ✅ 添加了必要的注释和文档
4. ✅ 测试了新功能（如果适用）

### 贡献流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 报告问题

如果发现问题，请在 [Issues](../../issues) 中报告，并提供：
- 问题描述
- 复现步骤
- 预期行为
- 实际行为
- 环境信息（Python 版本、操作系统等）
- 相关日志（如果有）

## 📄 许可证

本项目采用 MIT 许可证。

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐ Star！**

Made with ❤️ by [FY]

</div>
