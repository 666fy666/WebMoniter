# 多平台监控工具（虎牙直播、微博等）

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Docker](https://img.shields.io/badge/docker-multi--platform-blue.svg)

一个支持多平台监控工具（虎牙直播、微博等），使用 APScheduler 进行任务调度，支持多渠道推送。

[快速开始](#-快速开始) • [Docker 部署](#-docker-部署推荐) • [配置说明](#-配置说明) • [Web管理界面](#-web管理界面) • [开发指南](#-开发指南)

</div>

---

## 📋 目录

- [支持的平台和推送通道](#-支持的平台和推送通道)
- [快速开始](#-快速开始)
- [Docker 部署（推荐）](#-docker-部署推荐)
- [配置说明](#-配置说明)
- [Web管理界面](#-web管理界面)
- [开发指南](#-开发指南)
- [常见问题](#-常见问题)
- [参考与致谢](#-参考与致谢)

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
| WxPusher           | wxpusher          | ✅           | 📱推荐,微信消息实时推送服务，可通过API实时给个人微信推送消息👉[官网](https://wxpusher.zjiecode.com/)              |
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

# 4. 复制并编辑配置文件
cp config.yml.sample config.yml
# 编辑 config.yml，配置监控任务和推送通道

# 5. 启动系统
uv run python main.py  # 前台运行
# 或
nohup uv run python main.py > /dev/null 2>&1 &  # 后台运行
```

**启动后访问**：
- Web管理界面：`http://localhost:8866`
- 默认登录账号：`admin` / `123`

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

#### 2. 启动服务

```bash
# 启动服务（后台运行）
docker compose up -d

# 查看服务状态
docker compose ps

# 查看实时日志
docker compose logs -f
```

#### 3. 验证部署

访问 `http://localhost:8866` 或 `http://your-server-ip:8866`，使用默认账号 `admin` / `123` 登录。

### Docker 常用操作

```bash
# 查看状态
docker compose ps

# 查看日志
docker compose logs -f                    # 实时日志
docker compose logs --tail=100            # 最近100行

# 停止/重启/更新
docker compose stop                        # 停止服务
docker compose restart                     # 重启服务
docker compose pull && docker compose up -d  # 更新到最新版本

# 完全卸载
docker compose down                        # 停止并删除容器
# 注意：数据文件（data/、logs/、config.yml）会保留在本地
```

### 配置文件热重载

**重要**：系统支持配置文件热重载功能，修改 `config.yml` 后**无需重启容器**，配置会在 5 秒内自动生效。

系统会自动检测以下配置的变化并立即应用：
- ✅ 监控平台配置（微博 Cookie、UID、并发数；虎牙 Cookie、User-Agent、房间号、并发数）
- ✅ 调度器配置（监控间隔时间、日志清理时间）
- ✅ 推送通道配置（新增、删除、修改推送通道）
- ✅ 免打扰时段配置

### 数据持久化

所有重要数据都会保存在本地：

- **配置文件**: `./config.yml` - 监控和推送配置
- **数据库**: `./data/` - SQLite 数据库文件
- **日志文件**: `./logs/` - 应用日志（按日期分割）

删除容器不会丢失数据，重新启动容器后数据会自动恢复。

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

#### 调度器配置

```yaml
scheduler:
  huya_monitor_interval_seconds: 65      # 虎牙监控间隔（秒），默认65秒
  weibo_monitor_interval_seconds: 300    # 微博监控间隔（秒），默认300秒（5分钟）
  cleanup_logs_hour: 2                   # 日志清理时间（小时），默认2点
  cleanup_logs_minute: 0                 # 日志清理时间（分钟），默认0分
  retention_days: 3                      # 日志保留天数，默认3天
```

#### 免打扰时段配置

```yaml
quiet_hours:
  enable: false  # 是否启用免打扰时段，默认false
  start: "22:00"  # 免打扰时段开始时间（24小时制，格式：HH:MM）
  end: "08:00"    # 免打扰时段结束时间（24小时制，格式：HH:MM）
```

**功能说明**：
- 启用免打扰时段后，系统会在指定时间段内**静默运行**
- 监控任务会**正常执行**，继续检测变化并更新数据库
- 在免打扰时段内检测到的变化**不会推送通知**，但会在日志中记录
- 支持跨天设置（例如：22:00 到 08:00）

### 推送通道配置

推送通道配置在 `push_channel` 部分，支持配置多个推送通道。每个通道需要设置：

- `name`: 通道名称（唯一标识）
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
  
  # WxPusher
  - name: WxPusher
    enable: true
    type: wxpusher
    app_token: your_app_token
    uids: uid1,uid2  # 用户ID列表，逗号分隔
```

详细配置示例请参考 `config.yml.sample` 文件。

---

## 🌐 Web管理界面

系统提供了美观易用的Web管理界面，支持PC端和移动端访问，方便用户进行配置管理和数据查看。

### 访问地址

启动系统后，访问 `http://localhost:8866` 即可打开Web管理界面。

**Docker部署**：如果使用Docker部署，请确保已映射端口 `8866:8866`，然后访问 `http://your-server-ip:8866`

### 登录信息

- **用户名**: `admin`
- **密码**: `123`

> ⚠️ **安全提示**：默认账号密码仅用于开发测试，生产环境建议修改登录凭据。

---

## 💻 开发指南

### 代码检测

项目使用 `black` 和 `ruff` 进行代码格式化和检查。

#### 安装开发依赖

```bash
uv sync --extra dev
```

#### 代码格式化

使用 `black` 格式化代码：

```bash
# 格式化所有代码
uv run black .

# 检查代码格式（不修改文件）
uv run black --check .
```

#### 代码检查

使用 `ruff` 检查代码：

```bash
# 检查代码并自动修复
uv run ruff check --fix .

# 仅检查代码（不修复）
uv run ruff check .
```

#### 运行测试

```bash
uv run pytest
```

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
- **本地部署**：数据库 `data.db` 在项目根目录，日志在 `logs/` 目录

**Q: Web界面无法访问怎么办？**  
A: 
1. 确认系统已正常启动（检查日志）
2. 确认端口8866未被占用
3. Docker部署时确认端口映射正确（`8866:8866`）
4. 检查防火墙设置，确保8866端口开放

**Q: 免打扰时段内会遗漏消息吗？**  
A: 免打扰时段内，监控任务会**正常执行**并更新数据库，但**不会推送通知**。如果您担心遗漏重要消息，可以查看日志文件或数据库了解监控记录，或关闭免打扰时段功能。

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

## 📄 许可证

本项目采用 MIT 许可证,仅供个人学习使用。

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐ Star！**

Made with ❤️ by [FY]

</div>
