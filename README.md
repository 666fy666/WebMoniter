# Web监控系统

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)
![Docker](https://img.shields.io/badge/docker-multi--platform-blue.svg)

一个基于 Python 的异步 Web 监控系统，支持多平台监控任务（虎牙直播、微博等），使用 APScheduler 进行任务调度，支持多渠道推送和 SQLite 数据存储。

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [配置说明](#-配置说明) • [使用指南](#-使用指南) • [Docker 部署](#-docker-部署推荐) • [开发指南](#-开发指南)

</div>

---

## 📋 目录

- [功能特性](#-功能特性)
- [支持的平台和推送通道](#-支持的平台和推送通道)
- [快速开始](#-快速开始)
- [Docker 部署（推荐）](#-docker-部署推荐)
- [配置说明](#-配置说明)
- [使用指南](#-使用指南)
- [开发指南](#-开发指南)
- [常见问题](#-常见问题)
- [参考与致谢](#-参考与致谢)

---

## ✨ 功能特性

- 🎯 **多平台监控**：支持虎牙直播、微博等平台监控，可轻松扩展更多平台
- ⏰ **灵活调度**：基于 APScheduler 的任务调度系统，支持间隔任务和定时任务
- 📊 **数据持久化**：SQLite 本地数据库存储监控数据，自动管理表结构
- 📱 **多渠道推送**：支持 Server酱、企业微信、钉钉、飞书、Telegram、QQ、Bark、Gotify、Webhook、邮件等多种推送方式
- 📝 **智能日志**：完善的日志记录和自动清理机制，支持按日期分割
- 🚀 **高性能异步**：基于 asyncio 的异步架构，支持高并发监控任务
- ⚙️ **配置热重载**：基于 YAML 文件的配置管理，支持运行时热重载，修改配置文件后无需重启服务即可生效
- 🔄 **Cookie 管理**：智能 Cookie 缓存管理，自动处理失效和更新
- 🛡️ **错误处理**：完善的异常处理和重试机制，确保系统稳定运行
- 🐳 **多平台支持**：Docker 镜像支持 amd64 和 arm64 架构
- 🌙 **免打扰时段**：支持设置静默时间，避免深夜打扰，监控任务继续执行但不推送通知

## 🛠️ 技术栈

- **语言**: Python >= 3.10
- **异步框架**: asyncio, aiohttp
- **任务调度**: APScheduler
- **数据库**: SQLite (aiosqlite)
- **配置管理**: pydantic, pyyaml
- **依赖管理**: uv
- **代码质量**: black, ruff

---

## 📊 支持的平台和推送通道

### 监控平台支持

| 平台类型 | type     | 动态检测 | 开播检测 |
| -------- | -------- | -------- | -------- |
| 虎牙     | huya     | ❌       | ✅       |
| 微博     | weibo    | ✅       | ❌       |

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
| 电子邮件           | email             | ✅           | 📧通用的方式                                                                                                  |

---

## 🚀 快速开始

### 环境要求

- Python >= 3.10
- uv (Python 包管理器)

### 本地安装步骤

```bash
# 1. 克隆项目
git clone <repository-url>
cd WebMoniter

# 2. 安装 uv（如果尚未安装）
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 3. 安装项目依赖
uv sync --locked
# 或：使用 pip 安装依赖
pip3 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 复制并编辑配置文件
cp config.yml.sample config.yml
# 编辑 config.yml，配置监控任务和推送通道

# 5. 启动系统
uv run python main.py  # 前台运行
# 或
nohup uv run python main.py > /dev/null 2>&1 &  # 后台运行
```

系统会自动创建 `data.db` 数据库文件并初始化表结构。

---

## 🐳 Docker 部署（推荐）

本项目推荐使用 Docker Compose 进行部署，支持多平台架构（amd64、arm64），部署简单、管理方便。

### 前置要求

- Docker >= 20.10
- Docker Compose >= 2.0

### 部署步骤

#### 1. 准备配置文件

```bash
# 克隆项目（如果还没有）
git clone <repository-url>
cd WebMoniter

# 复制配置文件模板
cp config.yml.sample config.yml

# 编辑配置文件，填入监控配置和推送通道
vim config.yml  # 或使用其他编辑器
```

#### 2. 了解 docker-compose.yml

项目根目录下的 `docker-compose.yml` 文件内容如下：

```yaml
services:
  web-monitor:
    image: fengyu666/webmoniter:latest
    container_name: webmoniter
    restart: unless-stopped
    init: true
    shm_size: 64m
    deploy:
      resources:
        limits:
          memory: 1024M
        reservations:
          memory: 512M
    volumes:
      - ./config.yml:/app/config.yml:ro
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - TZ=Asia/Shanghai
      - PYTHONDONTWRITEBYTECODE=1
      - PYTHONNOUSERSITE=1
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

**配置说明：**

- `image`: Docker 镜像名称，支持多平台（amd64、arm64）
- `container_name`: 容器名称
- `restart`: 重启策略，`unless-stopped` 表示除非手动停止，否则自动重启
- `init`: 使用 init 进程处理僵尸进程，提升容器稳定性
- `shm_size`: 限制共享内存大小为 64MB，优化资源使用
- `deploy.resources`: 资源限制配置
  - `limits.memory`: 最大内存限制为 1024MB
  - `reservations.memory`: 预留内存为 512MB
- `volumes`: 数据卷挂载
  - `config.yml`: 配置文件挂载为只读，支持热重载（修改配置后无需重启容器）
  - `data`: 数据库文件存储目录，持久化数据
  - `logs`: 日志文件存储目录
- `environment`: 环境变量配置
  - `TZ`: 设置时区为上海时区
  - `PYTHONDONTWRITEBYTECODE=1`: 禁用字节码缓存写入，减少磁盘 I/O
  - `PYTHONNOUSERSITE=1`: 禁用用户站点目录，确保环境隔离
- `healthcheck`: 健康检查配置，用于监控容器运行状态

#### 3. 启动服务

```bash
# 启动服务（后台运行）
docker compose up -d

# 查看服务状态
docker compose ps

# 查看实时日志
docker compose logs -f

# 查看最近100行日志
docker compose logs --tail=100
```

#### 4. 验证部署

```bash
# 检查容器是否正常运行
docker compose ps

# 应该看到类似输出：
# NAME        IMAGE                          STATUS
# webmoniter  fengyu666/webmoniter:latest   Up X seconds

# 查看日志确认无错误
docker compose logs web-monitor
```

### Docker 常用操作

```bash
# 查看状态
docker compose ps

# 查看日志
docker compose logs -f                    # 实时日志
docker compose logs --tail=100            # 最近100行
docker compose logs web-monitor           # 指定服务日志

# 停止/重启/更新
docker compose stop                        # 停止服务
docker compose restart                     # 重启服务（修改配置后需要重启）
docker compose restart web-monitor        # 重启指定服务
docker compose pull && docker compose up -d  # 更新到最新版本

# 进入容器（调试用）
docker compose exec web-monitor sh

# 完全卸载
docker compose down                        # 停止并删除容器
docker rmi fengyu666/webmoniter:latest    # 删除镜像（可选）
# 注意：数据文件（data/、logs/、config.yml）会保留在本地
```

### 多平台支持

本项目 Docker 镜像支持以下平台：

- **linux/amd64** - Intel/AMD 64位处理器
- **linux/arm64** - ARM 64位处理器（如 Apple Silicon、树莓派 4+）

Docker 会自动根据您的系统架构拉取对应的镜像。如果您需要手动指定平台：

```yaml
services:
  web-monitor:
    platform: linux/amd64
```

### Docker 镜像优化

本项目 Docker 镜像经过优化，具有以下特点：

- **多阶段构建**：分离构建和运行阶段，减小镜像体积
- **最小化运行时**：运行阶段不包含构建工具，只保留必要的运行时文件
- **缓存优化**：清理构建缓存和临时文件，进一步减小镜像体积
- **启动优化**：使用优化的环境变量配置，提升容器启动速度
- **资源限制**：合理配置内存限制，防止资源浪费

优化后的镜像体积更小，启动速度更快，同时保持所有功能不变。

### 配置文件修改（支持热重载）

**重要**：系统支持配置文件热重载功能，修改 `config.yml` 后**无需重启容器**，配置会在 5 秒内自动生效。

系统会自动检测以下配置的变化并立即应用：
- ✅ 监控平台配置（微博 Cookie、UID、并发数；虎牙 Cookie、User-Agent、房间号、并发数）
- ✅ 调度器配置（监控间隔时间、日志清理时间）
- ✅ 推送通道配置（新增、删除、修改推送通道）

**热重载工作原理**：
- 系统每 5 秒检查一次配置文件的修改时间
- 检测到文件变化后，自动重新加载配置
- 自动更新调度器中的任务间隔时间
- 监控任务执行时会自动使用最新的配置（包括 Cookie、推送通道等）

**注意**：如果遇到配置未生效的情况，可以手动重启容器：

```bash
# 重启服务（可选，通常不需要）
docker compose restart web-monitor
```

### 数据持久化

所有重要数据都会保存在本地：

- **配置文件**: `./config.yml` - 监控和推送配置
- **数据库**: `./data/` - SQLite 数据库文件
- **日志文件**: `./logs/` - 应用日志（按日期分割）

删除容器不会丢失数据，重新启动容器后数据会自动恢复。

### 其他部署方式

**systemd 服务**：创建 `/etc/systemd/system/web-monitor.service`，参考示例配置。

**GitHub Actions CI/CD**：推送到 `main`/`master` 分支或创建 `v*` 标签时自动构建多平台 Docker 镜像。需要在 GitHub 仓库设置中添加 `DOCKER_USERNAME` 和 `DOCKER_PASSWORD` Secrets。

---

## ⚙️ 配置说明

### 配置文件结构

配置文件采用 YAML 格式，主要包含以下部分：

1. **监控平台配置** (`weibo`, `huya`)
2. **调度器配置** (`scheduler`)
3. **免打扰时段配置** (`quiet_hours`)
4. **推送通道配置** (`push_channel`)

### 监控任务配置

#### 微博监控

```yaml
weibo:
  cookie: your_weibo_cookie  # 从浏览器开发者工具获取
  uids: uid1,uid2,uid3       # 逗号分隔的UID列表
  concurrency: 2              # 并发数，建议 2-5（避免触发限流）
```

**获取 Cookie**：
1. 登录微博网页版
2. 打开浏览器开发者工具（F12）
3. 在 Network 标签中找到任意请求，复制 `Cookie` 请求头

**获取 UID**：
- 访问用户主页，URL 中的数字即为 UID
- 例如：`https://weibo.com/u/1234567890`，UID 为 `1234567890`

#### 虎牙监控

```yaml
huya:
  user_agent: your_user_agent           # User-Agent 字符串
  cookie: your_huya_cookie               # 可选，没有可不填
  rooms: room1,room2,room3              # 逗号分隔的房间号列表
  concurrency: 10                        # 并发数，建议 5-10
```

**获取房间号**：
- 从虎牙直播间 URL 获取
- 例如：`https://www.huya.com/123456`，房间号为 `123456`

**User-Agent 示例**：
```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
```

#### 调度器配置

```yaml
scheduler:
  huya_monitor_interval_seconds: 65      # 虎牙监控间隔（秒），默认65秒
  weibo_monitor_interval_seconds: 300    # 微博监控间隔（秒），默认300秒（5分钟）
  cleanup_logs_hour: 2                   # 日志清理时间（小时），默认2点
  cleanup_logs_minute: 0                 # 日志清理时间（分钟），默认0分
```

#### 免打扰时段配置

```yaml
# 免打扰时段配置
# ⚠️ 注意：开启此功能后，在免打扰时段内的监控任务将继续执行，但不会推送通知给用户
# 这可能会导致您在免打扰时段内遗漏重要消息，请谨慎使用
quiet_hours:
  enable: false  # 是否启用免打扰时段，默认false
  start: "22:00"  # 免打扰时段开始时间（24小时制，格式：HH:MM），例如：22:00 表示晚上10点
  end: "08:00"    # 免打扰时段结束时间（24小时制，格式：HH:MM），例如：08:00 表示早上8点
```

**功能说明**：
- 启用免打扰时段后，系统会在指定时间段内**静默运行**
- 监控任务会**正常执行**，继续检测变化并更新数据库
- 在免打扰时段内检测到的变化**不会推送通知**，但会在日志中记录
- 支持跨天设置（例如：22:00 到 08:00）
- 重要系统通知（如 Cookie 失效提醒）不受免打扰时段影响

**使用场景**：
- 避免深夜被推送通知打扰
- 在休息时间保持监控运行，但不接收通知
- 第二天可以查看日志了解夜间发生的变化

**注意事项**：
- ⚠️ 开启此功能可能会遗漏重要消息，请根据实际需求谨慎使用
- 免打扰时段内的监控数据会正常保存到数据库
- 可以通过日志文件查看免打扰时段内的监控记录

### 推送通道配置

推送通道配置在 `push_channel` 部分，支持配置多个推送通道。每个通道需要设置：

- `name`: 通道名称（唯一标识，对应任务配置中的推送通道名称）
- `enable`: 是否启用（`true`/`false`）
- `type`: 通道类型（见上表）
- 其他通道特定配置

**配置示例**：

```yaml
push_channel:
  # 企业微信机器人（推荐）
  - name: 企业微信机器人
    enable: true
    type: wecom_bot
    key: your_webhook_key
  
  # 钉钉机器人（推荐）
  - name: 钉钉机器人
    enable: true
    type: dingtalk_bot
    access_token: your_access_token
    secret: your_secret  # 可选：加签密钥
  
  # Server酱 Turbo
  - name: Server酱_Turbo
    enable: false
    type: serverChan_turbo
    send_key: your_send_key
```

详细配置示例请参考 `config.yml.sample` 文件。

---

## 📖 使用指南

### 工作流程

1. **配置监控任务**：在 `config.yml` 中配置要监控的平台和账号
2. **配置推送通道**：设置推送通道，用于接收监控通知
3. **启动系统**：使用 Docker Compose 或直接运行 Python 脚本
4. **查看日志**：通过日志文件或 Docker 日志查看运行状态
5. **接收通知**：当监控到新动态或开播时，会通过配置的推送通道发送通知
6. **修改配置**：修改 `config.yml` 后无需重启，系统会自动检测并应用新配置（热重载）

### 监控任务执行

- 系统会根据配置的间隔时间自动执行监控任务
- 微博监控：检测用户新发布的动态
- 虎牙监控：检测直播间开播状态

### 数据存储

- 所有监控数据存储在 SQLite 数据库中（`data.db`）
- 系统会自动去重，避免重复推送
- 数据库文件位于 `./data/` 目录（Docker 部署）或项目根目录（本地部署）

### 日志管理

- 日志文件按日期分割，存储在 `logs/` 目录
- 日志格式：`main_YYYY-MM-DD.log`
- 系统会在每天凌晨 2 点自动清理 3 天前的日志文件

---

## 🔧 添加新的监控任务

1. 在 `monitors/` 目录下创建监控类，继承 `BaseMonitor`
2. 在 `main.py` 中创建运行函数
3. 在 `register_monitors()` 中注册任务
4. 在 `config.py` 中添加配置项
5. 更新 `config.yml.sample` 添加配置示例

详细示例请参考现有监控任务实现（`monitors/huya_monitor.py`、`monitors/weibo_monitor.py`）。

---

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

### 项目结构

```
WebMoniter/
├── src/                    # 源代码目录
│   ├── config.py          # 配置管理
│   ├── database.py         # 数据库操作
│   ├── monitor.py          # 监控基类
│   ├── scheduler.py        # 任务调度
│   ├── push_channel/       # 推送通道实现
│   └── ...
├── monitors/               # 监控任务实现
│   ├── huya_monitor.py    # 虎牙监控
│   └── weibo_monitor.py   # 微博监控
├── main.py                 # 主程序入口
├── config.yml.sample       # 配置文件模板
├── docker-compose.yml      # Docker Compose 配置
├── Dockerfile              # Docker 镜像构建文件
└── pyproject.toml          # 项目配置和依赖
```

---

## ❓ 常见问题

**Q: 如何更新 Cookie？**  
A: 直接修改 `config.yml` 中的 Cookie 值，**无需重启容器或程序**。系统支持配置热重载，会在 5 秒内自动检测并应用新的配置。下次执行监控任务时会自动使用新的 Cookie。

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
- **本地部署**：数据库 `data.db` 在项目根目录，日志在 `logs/` 目录

**Q: 如何查看推送是否成功？**  
A: 查看日志文件，搜索 "推送" 关键字，会显示推送成功或失败的详细信息。

**Q: 支持哪些 Docker 平台？**  
A: 支持 `linux/amd64` 和 `linux/arm64` 平台，Docker 会自动根据您的系统架构拉取对应的镜像。

**Q: 如何备份数据？**  
A: 备份以下文件/目录：
- `config.yml` - 配置文件
- `./data/` - 数据库目录
- `./logs/` - 日志目录（可选）

**Q: 免打扰时段内会遗漏消息吗？**  
A: 免打扰时段内，监控任务会**正常执行**并更新数据库，但**不会推送通知**。如果您担心遗漏重要消息，可以：
1. 查看日志文件了解免打扰时段内的监控记录
2. 查看数据库了解监控到的变化
3. 根据实际需求调整免打扰时段设置
4. 如果担心遗漏重要消息，可以关闭免打扰时段功能

---

## ⚠️ 注意事项

- **并发控制**：微博监控建议并发数 2-5，虎牙监控可设置 5-10，过高可能导致限流或封禁
- **Cookie 管理**：定期更新 Cookie，失效时会记录错误日志。建议每月更新一次。修改 Cookie 后无需重启服务，系统会自动应用（热重载）
- **配置热重载**：系统每 5 秒检查一次配置文件变化，修改配置后无需重启即可生效。支持监控平台配置、调度器配置、推送通道配置、免打扰时段配置的热重载
- **免打扰时段**：启用免打扰时段后，监控任务会继续执行但不推送通知。请注意可能会遗漏重要消息，建议根据实际需求谨慎使用
- **数据备份**：建议定期备份 `data.db` 和 `config.yml`，避免数据丢失
- **日志清理**：系统自动清理 3 天前的日志文件，如需保留更长时间，请手动备份
- **网络环境**：确保服务器可以访问目标网站（虎牙、微博等），某些推送通道（如 Telegram）需要特殊网络环境
- **推送频率**：注意各推送通道的频率限制，避免触发限流

---

## 📚 附录

### Webhook 支持的请求格式

#### GET 请求

```
GET https://xxx.api.com?title={{title}}&content={{content}}
```

#### POST 请求

```
POST https://xxx.api.com
Content-Type: application/json

{
  "title": "通知标题",
  "content": "通知内容",
  "jump_url": "跳转链接（可选）",
  "pic_url": "图片链接（可选）"
}
```

支持的模板变量：
- `{{title}}` - 通知标题
- `{{content}}` - 通知内容
- `{{jump_url}}` - 跳转链接
- `{{pic_url}}` - 图片链接

---

## 📄 参考与致谢

本项目参考了 [aio-dynamic-push](https://github.com/nfe-w/aio-dynamic-push) 项目的设计思路和推送通道实现，特此表示感谢！

**aio-dynamic-push** 是一款优秀的整合多平台动态/直播开播提醒检测与推送的小工具，支持 B站、微博、小红书、抖音、斗鱼、虎牙等多个平台。本项目在推送通道实现和配置结构方面受到了该项目的启发。

---

## 🤝 贡献指南

欢迎贡献代码！提交 Pull Request 前请确保：
- ✅ 代码已通过 `black` 格式化和 `ruff` 检查
- ✅ 添加了必要的注释和文档
- ✅ 测试了新功能（如果适用）
- ✅ 更新了 `config.yml.sample`（如果添加了新配置项）

如果发现问题，请在 [Issues](../../issues) 中报告。

---

## 📄 许可证

本项目采用 MIT 许可证,仅供个人学习使用。

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐ Star！**

Made with ❤️ by [FY]

</div>
