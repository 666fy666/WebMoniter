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

- [功能特性](#-功能特性)
- [技术栈](#-技术栈)
- [快速开始](#-快速开始)
  - [环境要求](#环境要求)
  - [安装步骤](#安装步骤)
  - [配置设置](#配置设置)
- [使用指南](#-使用指南)
  - [启动监控系统](#启动监控系统)
  - [使用 Docker 运行](#使用-docker-运行)
    - [前置要求](#前置要求)
    - [使用 Docker Compose（推荐）](#使用-docker compose推荐)
    - [Docker 常用操作](#docker-常用操作)
    - [Docker 数据说明](#docker-数据说明)
    - [Docker 常见问题](#docker-常见问题)
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

### 使用 Docker 运行

使用 Docker 运行可以避免环境配置问题，推荐使用 Docker Compose 方式。

#### 前置要求

- 已安装 Docker（[下载地址](https://www.docker.com/get-started)）
- 已安装 Docker Compose（Docker Desktop 已包含）

#### 使用 Docker Compose（推荐）

使用 Docker Compose 是最简单的部署方式，所有数据都会自动保存，即使删除容器也不会丢失。

**三步快速开始：**

**第一步：准备配置文件**

```bash
# 复制配置文件模板
cp config.yml.sample config.yml
```

然后编辑 `config.yml` 文件，填入你的配置：
- 微博 Cookie 和要监控的用户ID
- 虎牙房间号和 Cookie（可选）
- 推送通道配置（企业微信、钉钉、飞书等）

> 💡 **提示**：Windows 用户可以用记事本打开编辑，Mac/Linux 用户可以用任意文本编辑器。

**第二步：修改 Docker 镜像名称（如需要）**

`docker-compose.yml` 文件已配置好，默认使用 `fengyu666/web-monitor:latest` 镜像。

如果需要使用其他镜像，编辑 `docker-compose.yml` 文件，修改 `image` 字段：

```yaml
image: your-username/web-monitor:latest
```

将 `your-username` 替换为实际的 Docker Hub 用户名。

**docker-compose.yml 配置说明：**

`docker-compose.yml` 文件包含以下配置：

- **image**: Docker 镜像名称，默认使用 `fengyu666/web-monitor:latest`
- **container_name**: 容器名称，固定为 `web-monitor`
- **restart**: 自动重启策略，设置为 `unless-stopped`（除非手动停止，否则自动重启）
- **volumes**: 数据卷挂载配置
  - `./config.yml:/app/config.yml:ro` - 配置文件（只读挂载，必需）
  - `./data.db:/app/data.db` - 主数据库文件（自动创建）
  - `./data.db-journal:/app/data.db-journal` - SQLite 日志文件（自动创建）
  - `./data.db-wal:/app/data.db-wal` - SQLite WAL 文件（自动创建）
  - `./data.db-shm:/app/data.db-shm` - SQLite 共享内存文件（自动创建）
  - `./logs:/app/logs` - 日志目录（自动创建）
  - `./cookie_cache.json:/app/cookie_cache.json` - Cookie 缓存文件（自动创建）
- **environment**: 环境变量
  - `TZ=Asia/Shanghai` - 设置时区为上海时区

所有挂载的文件和目录都会自动创建，无需手动创建。配置文件挂载为只读（`:ro`），确保容器内不会意外修改配置文件。

**第三步：启动服务**

```bash
# 启动服务（后台运行）
docker compose up -d

# 查看运行日志，确认启动成功
docker compose logs -f
```

看到类似以下输出表示启动成功：

```
web-monitor  | Web监控系统启动
web-monitor  | 已注册的监控任务:
web-monitor  |   - huya_monitor: interval[0:01:05]
web-monitor  |   - weibo_monitor: interval[0:05:00]
```

按 `Ctrl+C` 退出日志查看，服务会继续在后台运行。

#### Docker 常用操作

**查看服务状态**

```bash
docker compose ps
```

正常运行时应该显示 `Up` 状态。

**查看日志**

```bash
# 查看实时日志
docker compose logs -f

# 查看最近100行日志
docker compose logs --tail=100

# 查看特定服务的日志
docker compose logs -f web-monitor
```

**停止服务**

```bash
# 停止服务（数据不会丢失）
docker compose stop

# 停止并删除容器（数据不会丢失，因为已持久化）
docker compose down
```

**重启服务**

```bash
# 重启服务
docker compose restart

# 修改配置文件后，需要重启才能生效
docker compose restart
```

**更新到最新版本**

```bash
# 拉取最新镜像
docker compose pull

# 重启服务使用新版本
docker compose up -d
```

#### Docker 数据说明

**哪些数据会被保存？**

以下数据会自动保存到您的电脑上，即使删除容器也不会丢失：

| 数据 | 保存位置 | 说明 |
|------|---------|------|
| 配置文件 | `config.yml` | 您的监控配置 |
| 数据库 | `data.db` | 监控的历史数据 |
| 日志文件 | `logs/` 目录 | 运行日志，方便排查问题 |
| Cookie缓存 | `cookie_cache.json` | Cookie 状态缓存 |

**备份数据**

如果需要备份，直接复制以下文件即可：

```bash
# 备份所有重要数据
cp config.yml config.yml.backup
cp data.db data.db.backup
cp -r logs logs_backup
```

**恢复数据**

如果需要恢复备份：

```bash
# 恢复配置文件
cp config.yml.backup config.yml

# 恢复数据库
cp data.db.backup data.db

# 重启服务使配置生效
docker compose restart
```

#### Docker 常见问题

**1. 容器启动失败**

**问题**：运行 `docker compose up -d` 后容器立即退出

**解决方法**：
1. 检查配置文件是否存在：`ls config.yml`
2. 查看错误日志：`docker compose logs`
3. 确认配置文件格式正确（参考 `config.yml.sample`）

**2. 找不到镜像**

**问题**：提示 `pull access denied` 或 `image not found`

**解决方法**：
1. 确认 `docker-compose.yml` 中的镜像名称是否正确
2. 确认该镜像在 Docker Hub 上存在
3. 如果镜像不存在，需要先构建并推送到 Docker Hub

**3. 修改配置后不生效**

**问题**：修改了 `config.yml` 但监控任务没有变化

**解决方法**：
```bash
# 重启服务使配置生效
docker compose restart

# 查看日志确认配置已加载
docker compose logs -f
```

**4. 如何查看监控是否正常工作？**

**方法1：查看日志**
```bash
docker compose logs -f
```

**方法2：检查数据库**
数据库文件 `data.db` 会记录监控到的数据，可以使用 SQLite 工具查看。

**方法3：查看推送消息**
如果配置了推送通道（企业微信、钉钉等），监控到变化时会收到推送消息。

**5. 如何完全卸载？**

```bash
# 停止并删除容器
docker compose down

# 删除镜像（可选）
docker rmi fengyu666/web-monitor:latest

# 删除数据文件（可选，会丢失所有数据）
rm -f data.db* config.yml cookie_cache.json
rm -rf logs
```

### 使用 GitHub Actions CI/CD 自动构建和推送

项目已配置 GitHub Actions，可以自动构建 Docker 镜像并推送到 Docker Hub。

#### 配置步骤

1. **设置 Docker Hub Secrets**

   在 GitHub 仓库设置中添加以下 Secrets：
   - `DOCKER_USERNAME`: 你的 Docker Hub 用户名
   - `DOCKER_PASSWORD`: 你的 Docker Hub 密码或访问令牌（推荐使用访问令牌）

   > **获取访问令牌**：登录 Docker Hub → Account Settings → Security → New Access Token

2. **触发构建**

   - **自动触发**：推送到 `main` 或 `master` 分支时自动构建
   - **标签触发**：创建以 `v` 开头的标签（如 `v1.0.0`）时自动构建
   - **手动触发**：在 GitHub Actions 页面点击 "Run workflow" 手动触发

3. **拉取镜像**

   构建完成后，可以从 Docker Hub 拉取镜像：

   ```bash
   docker pull <your-dockerhub-username>/web-monitor:latest
   ```

#### 工作流特性

- ✅ 自动构建多架构镜像（amd64, arm64）
- ✅ 使用构建缓存加速构建
- ✅ 自动打标签（latest、分支名、SHA、版本号）
- ✅ PR 时只构建不推送
- ✅ 支持手动触发

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
     access_token: your_access_token  # 机器人访问令牌
     secret: your_secret  # 可选：加签密钥（SEC开头的字符串），如果配置了secret则使用加签方式，否则使用普通方式
   ```
   
   注意：如果配置了 `secret` 字段，系统会自动使用加签方式发送消息，提高安全性。加签密钥可在钉钉机器人安全设置页面获取。

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
     app_id: your_app_id  # 机器人应用的App ID
     app_secret: your_app_secret  # 机器人应用的App Secret（用于获取AccessToken）
     # 注意：QQ开放平台已禁用固定Token，必须使用app_secret获取AccessToken
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
