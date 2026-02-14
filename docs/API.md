# API 调用指南

系统提供了 RESTful API 接口，方便与其他系统集成或进行自动化操作。所有 API 接口均基于 FastAPI 框架实现。

## 基础信息

- **Base URL**: `http://localhost:8866`（本地部署）或 `http://your-server-ip:8866`（服务器部署）
- **Content-Type**: `application/json`
- **认证方式**: 基于 Session 的认证（部分接口需要登录）

---

## API 端点列表

### 1. 认证相关

#### 登录

```http
POST /api/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=123
```

#### 登出

```http
POST /api/logout
```

#### 检查认证状态

```http
GET /api/check-auth
```

#### 修改密码（需登录）

```http
POST /api/change-password
Content-Type: application/x-www-form-urlencoded

old_password=xxx&new_password=xxx&confirm_password=xxx
```

#### 获取版本信息（无需登录）

```http
GET /api/version
```

返回示例：

```json
{
  "version": "2.1.3",
  "github_api_url": "https://api.github.com/repos/666fy666/WebMoniter/tags",
  "tags_url": "https://github.com/666fy666/WebMoniter/tags"
}
```

> 用于 Web 界面自动检测新版本。前端会调用 `github_api_url` 获取最新 tag 信息并与当前版本比较。

---

### 2. 配置管理（需登录）

#### 获取配置

```http
GET /api/config?format=json
GET /api/config?format=yaml
```

#### 保存配置

```http
POST /api/config
Content-Type: application/json

{
  "content": "yaml配置内容..."
}
```

或使用 JSON 格式：

```http
POST /api/config
Content-Type: application/json

{
  "config": {
    "weibo": {...},
    "huya": {...},
    ...
  }
}
```

---

### 3. 数据查询（需登录）

数据查询采用 REST 风格，支持按平台、按主键 ID 查询，以及分页与过滤。

#### 平台与主键说明

| 平台             | `platform`          | 主键 ID 含义        | 示例                         |
|------------------|---------------------|---------------------|------------------------------|
| 微博             | `weibo`             | 用户 UID            | `1234567890`                 |
| 虎牙             | `huya`              | 房间号 room         | `123456`                     |
| 哔哩哔哩直播     | `bilibili_live`     | UP 主 UID           | `1795147802`                 |
| 哔哩哔哩动态     | `bilibili_dynamic`  | UP 主 UID           | `1795147802`                 |
| 抖音直播         | `douyin`            | 抖音号（字符串）    | `ASOULjiaran`                |
| 斗鱼直播         | `douyu`             | 房间号 room         | `307876`                     |
| 小红书动态       | `xhs`               | 用户 profile_id     | `52d8c541b4c4d60e6c867480`   |

#### 列表：分页 + 可选过滤

```http
GET /api/data/{platform}?page=1&page_size=100
GET /api/data/weibo?uid=1234567890&page=1&page_size=20
GET /api/data/huya?room=123456&page=1&page_size=20
GET /api/data/bilibili_live?uid=1795147802&page=1&page_size=20
GET /api/data/douyin?id=ASOULjiaran&page=1&page_size=20
```

- `platform`：见上表中 `platform` 列
- `page`：页码，从 1 开始（默认 1）
- `page_size`：每页条数（默认 100）
- `uid`：当 `platform` 为 `weibo`、`bilibili_live`、`bilibili_dynamic` 时按 UID 过滤
- `room`：当 `platform` 为 `huya`、`douyu` 时按房间号过滤
- `id`：当 `platform` 为 `douyin`、`xhs` 时按抖音号 / profile_id 过滤
- `include_media`：当 `platform` 为 `huya` 时有效；设为 `false` 则不返回 `room_pic`、`avatar_url`，前端可再调用 `/api/data/huya/images` 异步获取

#### 虎牙封面/头像 URL（异步加载）

```http
GET /api/data/huya/images?rooms=123,456,789
```

用于数据展示页异步加载虎牙封面图和头像，减少首屏请求体积。返回 `{"data": {"123": {"room_pic": "...", "avatar_url": "..."}, ...}}`。

返回示例：

```json
{
  "data": [...],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5
}
```

#### 单条：按平台 + 主键 ID

```http
GET /api/data/weibo/{uid}
GET /api/data/huya/{room}
```

示例：`GET /api/data/weibo/1234567890`、`GET /api/data/huya/123456`  
未找到时返回 `404`，成功时返回 `{"data": {...}}`。

---

### 4. 监控状态（无需登录）

监控状态接口与数据查询对应，同样支持「全部 / 按平台 / 按 ID」三种粒度，**无需登录**。  
支持的监控平台与上文数据查询一致：

| 平台             | `platform`          | 主键 ID 含义        |
|------------------|---------------------|---------------------|
| 微博             | `weibo`             | 用户 UID            |
| 虎牙             | `huya`              | 房间号 room         |
| 哔哩哔哩直播     | `bilibili_live`     | UP 主 UID           |
| 哔哩哔哩动态     | `bilibili_dynamic`  | UP 主 UID           |
| 抖音直播         | `douyin`            | 抖音号（字符串）    |
| 斗鱼直播         | `douyu`             | 房间号 room         |
| 小红书动态       | `xhs`               | 用户 profile_id     |

#### 全部监控状态

```http
GET /api/monitor-status
```

返回结构：

- `success`: 是否成功  
- `data`: 一个对象，key 为平台名（如 `weibo`、`huya`、`bilibili_live` 等），value 为该平台下所有监控对象的数组（字段与 `/api/data/{platform}` 中 `data` 元素一致）  
- `timestamp`: ISO 格式时间戳

#### 按平台

```http
GET /api/monitor-status/weibo
GET /api/monitor-status/huya
GET /api/monitor-status/bilibili_live
GET /api/monitor-status/bilibili_dynamic
GET /api/monitor-status/douyin
GET /api/monitor-status/douyu
GET /api/monitor-status/xhs
```

返回该平台下所有监控项的数组，字段与对应 `/api/data/{platform}` 的单条 `data` 一致，例如：

- `weibo`：`UID`、`用户名`、`认证信息`、`简介`、`粉丝数`、`微博数`、`文本`、`mid`、`url`  
- `huya`：`room`、`name`、`is_live`、`url`  
- `bilibili_live`：`uid`、`uname`、`room_id`、`is_live`、`url`  
- `bilibili_dynamic`：`uid`、`uname`、`dynamic_id`、`dynamic_text`、`url`  
- `douyin`：`douyin_id`、`name`、`is_live`、`url`  
- `douyu`：`room`、`name`、`is_live`、`url`  
- `xhs`：`profile_id`、`user_name`、`latest_note_title`、`url`

#### 按平台 + 主键 ID（单条）

```http
GET /api/monitor-status/weibo/{uid}
GET /api/monitor-status/huya/{room}
GET /api/monitor-status/bilibili_live/{uid}
GET /api/monitor-status/bilibili_dynamic/{uid}
GET /api/monitor-status/douyin/{id}
GET /api/monitor-status/douyu/{room}
GET /api/monitor-status/xhs/{id}
```

示例：

- `GET /api/monitor-status/weibo/1234567890`
- `GET /api/monitor-status/huya/123456`
- `GET /api/monitor-status/bilibili_live/1795147802`
- `GET /api/monitor-status/douyin/ASOULjiaran`

成功时 `data` 为单条对象；未找到时返回 `404`。

---

### 5. 日志查询

#### 获取日志

```http
GET /api/logs?lines=100
GET /api/logs?lines=100&task=ikuuu_checkin
```

参数：
- `lines`：返回最近 N 行日志，默认 100
- `task`：（可选）指定任务 ID 时，返回该任务的今日专属日志；不传则返回今日总日志

不传 `task` 时读取 `main_YYYYMMDD.log`；传 `task` 时读取 `task_{job_id}_YYYYMMDD.log`。

#### 获取任务日志列表

```http
GET /api/logs/tasks
```

返回今日有日志文件的任务 ID 列表，以及全部任务列表（用于前端下拉选择）：

```json
{
  "all_tasks": [
    {"job_id": "ikuuu_checkin", "has_log_today": true},
    {"job_id": "huya_monitor", "has_log_today": false}
  ],
  "tasks_with_logs": ["ikuuu_checkin", "log_cleanup"]
}
```

---

### 6. 任务管理（需登录）

#### 获取任务列表

```http
GET /api/tasks
```

返回所有注册的监控任务和定时任务列表：

```json
{
  "success": true,
  "tasks": [
    {
      "job_id": "huya_monitor",
      "trigger": "interval",
      "type": "monitor",
      "type_label": "监控任务",
      "description": "虎牙直播状态监控"
    },
    {
      "job_id": "ikuuu_checkin",
      "trigger": "cron",
      "type": "task",
      "type_label": "定时任务",
      "description": "ikuuu 每日签到"
    }
  ]
}
```

#### 手动触发任务

```http
POST /api/tasks/{task_id}/run
```

- `task_id`：任务 ID，如 `huya_monitor`、`ikuuu_checkin` 等

成功返回：

```json
{
  "success": true,
  "message": "任务 huya_monitor 执行成功"
}
```

失败返回：

```json
{
  "success": false,
  "message": "任务执行失败: 具体错误信息"
}
```

**注意**：手动触发执行时会绕过"当天已运行则跳过"检查，确保任务被强制执行。

---

### 7. AI 助手（需登录，需在 config.yml 启用 `ai_assistant.enable`）

AI 助手提供智能对话、配置生成、日志诊断、数据洞察及可执行操作能力，需在 `config.yml` 中配置 `ai_assistant` 并安装 AI 依赖。

#### 获取 AI 助手状态

```http
GET /api/assistant/status
```

返回 AI 助手是否可用（依赖是否安装、配置是否启用），无需 AI 依赖也可调用：

```json
{
  "enabled": true
}
```

或 `{"enabled": false, "reason": "未安装 ai 依赖"}` 等。

#### 会话管理

```http
GET /api/assistant/conversations
```

返回当前用户的会话列表。

```http
POST /api/assistant/conversations
Content-Type: application/json

{"title": "新对话"}
```

新建会话，返回 `{"conversation_id": "xxx"}`。

```http
GET /api/assistant/conversations/{conv_id}/messages
```

获取指定会话的消息列表。

```http
DELETE /api/assistant/conversations/{conv_id}
```

删除指定会话。

#### 对话

```http
POST /api/assistant/chat
Content-Type: application/json

{
  "message": "虎牙谁在直播？",
  "conversation_id": "xxx",
  "context": "all"
}
```

- `message`：用户输入（必填）
- `conversation_id`：会话 ID，空则自动创建新会话
- `context`：检索范围，`"all"` 表示文档+配置+日志

返回：

```json
{
  "reply": "AI 回复内容",
  "conversation_id": "xxx",
  "suggested_action": null
}
```

当识别到可执行操作（如开关监控、增删配置）时，`suggested_action` 包含 `type: "confirm_execute"`、`action`、`platform_key` 等，前端可弹出确认弹窗，确认后调用 `POST /api/assistant/apply-action`。

当返回配置片段（YAML）时，`suggested_action` 可为 `{"type": "config_diff", "diff": "yaml内容", "description": "..."}`，前端展示「复制配置」按钮。

#### 流式对话

```http
POST /api/assistant/chat/stream
Content-Type: application/json

{
  "message": "虎牙谁在直播？",
  "conversation_id": "xxx",
  "context": "all"
}
```

参数与 `POST /api/assistant/chat` 一致。响应为 **Server-Sent Events (SSE)**，`Content-Type: text/event-stream`。

事件格式（每行一条 `data:` JSON）：

- `{"chunk": "文本块"}`：逐块返回 AI 回复
- `{"done": true, "reply": "完整回复", "suggested_action": {...}, "conversation_id": "xxx"}`：结束事件
- `{"error": "错误信息"}`：流式调用出错时返回

#### 执行可确认操作

```http
POST /api/assistant/apply-action
Content-Type: application/json

{
  "action": "toggle_monitor",
  "platform_key": "huya",
  "enable": false
}
```

开关监控。支持的 `platform_key`：`weibo`、`huya`、`bilibili`、`douyin`、`douyu`、`xhs`。

```http
POST /api/assistant/apply-action
Content-Type: application/json

{
  "action": "config_patch",
  "platform_key": "huya",
  "list_key": "rooms",
  "operation": "add",
  "value": "123456"
}
```

增删配置列表项。`operation` 为 `add` 或 `remove`。支持的 `platform_key` 及对应 `list_key`：

| platform_key | list_key      |
|--------------|---------------|
| weibo        | uids          |
| huya         | rooms         |
| bilibili     | uids          |
| douyin       | douyin_ids    |
| douyu        | rooms         |
| xhs          | profile_ids   |

成功返回 `{"success": true, "message": "..."}`；失败返回 `{"error": "..."}`，HTTP 状态码 400/500。

#### 重建 RAG 索引

```http
POST /api/assistant/reindex
```

手动重建向量库索引。成功返回 `{"status": "ok", "message": "索引已重建"}`。

---

### 8. Webhook 回调（AI 助手入口）

在企业微信、Telegram 等推送通道中配置回调 URL 后，用户可在对应平台内直接与 AI 助手对话。**无需登录 Web 管理界面**，由各平台将用户消息转发到以下接口。

#### 企业微信自建应用

```http
GET /api/webhooks/wecom
POST /api/webhooks/wecom
```

- **GET**：企业微信后台验证 URL 时使用（校验 `msg_signature`、`timestamp`、`nonce`、`echostr`）
- **POST**：接收成员发送的消息，解密后交给 AI 助手回复，再通过企业微信接口发回

需在 `config.yml` 的 `push_channel` 中为 **wecom_apps** 类型通道配置 `callback_token`、`encoding_aes_key`，并在企业微信后台将「接收消息」URL 设为本接口（如 `https://你的域名/api/webhooks/wecom`）。支持多应用：请求会依次尝试各已配置回调的通道解密，第一个成功的即为目标应用。

#### Telegram 机器人

```http
POST /api/webhooks/telegram/{channel_name}
```

- `channel_name`：推送通道名称（与 `push_channel` 中该 Telegram 通道的 `name` 一致）

需在 `push_channel` 的 **telegram_bot** 中配置 `api_token`，并调用 Telegram 的 `setWebhook` 将 URL 设为 `https://你的域名/api/webhooks/telegram/{channel_name}`。用户向机器人发送文字后，由本接口接收并交给 AI 助手，回复通过 Telegram API 异步发回。

---

## 调用示例

### Python 示例

```python
import requests

# 基础URL
BASE_URL = "http://localhost:8866"

# 创建会话以保持登录状态
session = requests.Session()

# 登录
login_response = session.post(
    f"{BASE_URL}/api/login",
    data={"username": "admin", "password": "123"}
)
print(login_response.json())

# 获取配置（需登录）
config_response = session.get(f"{BASE_URL}/api/config")
print(config_response.json())

# 获取版本信息（无需登录）
version_response = requests.get(f"{BASE_URL}/api/version")
print(version_response.json())

# 获取监控状态（无需登录）
status_response = requests.get(f"{BASE_URL}/api/monitor-status")
print(status_response.json())

# 获取微博数据列表（分页）
weibo_response = session.get(
    f"{BASE_URL}/api/data/weibo",
    params={"page": 1, "page_size": 10}
)
print(weibo_response.json())

# 按 UID 查询单个微博用户（需登录）
weibo_one = session.get(f"{BASE_URL}/api/data/weibo/1234567890")
print(weibo_one.json())

# 按房间号查询单个虎牙直播间（需登录）
huya_one = session.get(f"{BASE_URL}/api/data/huya/123456")
print(huya_one.json())

# 监控状态：按平台、按 ID（无需登录）
status_weibo = requests.get(f"{BASE_URL}/api/monitor-status/weibo")
status_one_user = requests.get(f"{BASE_URL}/api/monitor-status/weibo/1234567890")
print(status_weibo.json(), status_one_user.json())

# 获取任务列表
tasks_response = session.get(f"{BASE_URL}/api/tasks")
print(tasks_response.json())

# 手动触发任务执行（绕过"当天已运行则跳过"检查）
run_response = session.post(f"{BASE_URL}/api/tasks/huya_monitor/run")
print(run_response.json())
```

### cURL 示例

```bash
# 登录
curl -X POST http://localhost:8866/api/login \
  -d "username=admin&password=123" \
  -c cookies.txt

# 获取配置（需登录，使用保存的 Cookie）
curl -X GET http://localhost:8866/api/config \
  -b cookies.txt

# 获取版本信息（无需登录）
curl -X GET http://localhost:8866/api/version

# 获取监控状态（无需登录）
curl -X GET http://localhost:8866/api/monitor-status

# 按平台 / 按 ID 获取监控状态
curl -X GET http://localhost:8866/api/monitor-status/weibo
curl -X GET http://localhost:8866/api/monitor-status/weibo/1234567890

# 获取单条数据（需 Cookie）
curl -X GET "http://localhost:8866/api/data/weibo/1234567890" -b cookies.txt
curl -X GET "http://localhost:8866/api/data/huya/123456" -b cookies.txt

# 获取日志
curl -X GET "http://localhost:8866/api/logs?lines=50" \
  -b cookies.txt

# 获取任务列表
curl -X GET http://localhost:8866/api/tasks \
  -b cookies.txt

# 手动触发任务执行（绕过"当天已运行则跳过"检查）
curl -X POST http://localhost:8866/api/tasks/huya_monitor/run \
  -b cookies.txt
```

---

## 错误处理

API 返回的错误格式：

```json
{
  "error": "错误描述信息"
}
```

常见 HTTP 状态码：

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 401 | 未授权（需要登录） |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 相关文档

- [文档首页](index.md) - 项目概览与快速开始
- [AI 助手使用指南](guides/ai-assistant.md) - RAG + LLM 智能问答
- [二次开发指南](SECONDARY_DEVELOPMENT.md) - 代码规范、black/ruff、测试等
