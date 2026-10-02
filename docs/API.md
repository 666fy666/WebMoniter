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
  "version": "2.4.8",
  "github_api_url": "https://api.github.com/repos/666fy666/WebMoniter/tags",
  "tags_url": "https://github.com/666fy666/WebMoniter/tags"
}
```

> 用于 Web 界面自动检测新版本。前端会调用 `github_api_url` 获取最新 tag 信息并与当前版本比较。当前版本号以 `pyproject.toml` 为准。

---

### 2. 配置管理（需登录）

#### 获取配置元数据

```http
GET /api/config/metadata
```

返回配置页只读元数据：`sections`（配置节顺序）、`tasks`（监控与定时任务的 `TaskSpec` 字段）、`push_channel_types`（各推送 type 的名称与字段列表）。数据来自 `src/jobs/metadata.py`。

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

保存成功后会调用 `reconfigure_database`，响应中可能包含 `database` 状态字段。

`content` 保存完整 YAML 文本，会替换整份配置；`config` 可只包含需要更新的分区或字段，后端在配置锁内读取最新文件、递归合并、校验后保存，保留未提交字段及已有注释和引号。配置页的分区保存仅提交该分区。

列表通常按提交值替换；非空 `push_channel` 按 `name` 对应并整项替换通道，同时移除未提交的命名通道，空列表清空通道。空 `accounts`、`cookies` 用于移除已有的可选列表字段。

#### 数据库状态

```http
GET /api/database/status
```

返回脱敏后的数据库运行状态，例如：

```json
{
  "configured": false,
  "active_backend": "sqlite",
  "mysql_reachable": false,
  "sqlite_healthy": true,
  "sync_state": "sqlite_only",
  "pending_changes": 0,
  "last_sync_at": null,
  "message": "..."
}
```

数据库 `sync_state` 为 `sqlite_only`（仅 SQLite）、`in_sync`（已同步）、`fallback`（MySQL 故障回退）、`replaying`（恢复回放）或 `mirror_degraded`（SQLite 镜像降级）。同步关系见 [数据库设计](ARCHITECTURE.md#database-design)。

#### 测试 MySQL 连接（不写盘）

```http
POST /api/database/test
Content-Type: application/json

{
  "mysql": {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "webmoniter",
    "password": "xxx",
    "database": "webmoniter"
  }
}
```

用于测试尚未保存的 MySQL 配置，不会修改 `config.yml`。成功返回 `{"success": true, "message": "MySQL 连接测试成功"}`。

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
| 快手直播         | `kuaishou`          | 主播 principal_id | `KPL704668133` |
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
- `page_size`：每页条数（默认 100）；Web 微博页使用 25
- `uid`：当 `platform` 为 `weibo`、`bilibili_live`、`bilibili_dynamic` 时按 UID 过滤
- `room`：当 `platform` 为 `huya`、`douyu` 时按房间号过滤
- `id`：当 `platform` 为 `douyin`、`kuaishou`、`xhs` 时按抖音号 / principal_id / profile_id 过滤
- `include_media`：当 `platform` 为 `huya` 时有效；设为 `false` 时 `room_pic`、`avatar_url` 仍存在，但值为空字符串，前端可再调用 `/api/data/huya/images` 异步获取

`page`、`page_size` 必须为正整数，非正数返回 HTTP 400 和 `error` 字段；无法解析为整数时由 FastAPI 返回 HTTP 422。微博按正文中的发布时间稳定排序后分页，时间无法解析的记录排在最后。

返回示例：

```json
{
  "data": [
    {
      "room": "123456",
      "name": "示例主播",
      "is_live": 1,
      "url": "https://www.huya.com/123456",
      "room_pic": "",
      "avatar_url": ""
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

#### 虎牙封面/头像 URL（异步加载，需登录）

```http
GET /api/data/huya/images?rooms=123,456,789
```

用于数据展示页异步加载虎牙封面图和头像，减少首屏请求体积。返回 `{"data": {"123": {"room_pic": "...", "avatar_url": "..."}, ...}}`。

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
| 快手直播         | `kuaishou`          | 主播 principal_id |
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
- `kuaishou`：`principal_id`、`name`、`is_live`、`url`；状态值为字符串 `"1"`（直播中）或 `"0"`（未开播），获取失败时保留上次确认的状态。
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

### 5. 日志查询（需登录）

#### 获取日志

```http
GET /api/logs?lines=100
GET /api/logs?lines=100&task=ikuuu_checkin
```

参数：

- `lines`：返回最近 N 行日志，默认 100，必须为正整数；非正数返回 HTTP 400，无法解析为整数时返回 HTTP 422
- `task`：（可选）指定任务 ID 时，返回该任务的今日专属日志；不传则返回今日总日志

不传 `task` 时读取 `main_YYYYMMDD.log`；传 `task` 时读取 `task_{job_id}_YYYYMMDD.log`。

文件存在时返回 `logs` 与 `total_lines`。文件不足 N 行时返回已有行；大文件从尾部逐步扩大窗口，避免长行导致不足 N 行。`total_lines` 在小文件中为完整行数，在大文件中为读取窗口行数，不应当作全文件的精确计数。今日没有文件时返回空 `logs` 和 `message`；读取超时返回 HTTP 504。

Web 日志页通过定期 HTTP 轮询刷新，失败时重试并延长轮询间隔，不使用 WebSocket。

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
      "description": "虎牙直播监控"
    },
    {
      "job_id": "ikuuu_checkin",
      "trigger": "cron",
      "type": "task",
      "type_label": "定时任务",
      "description": "iKuuu 签到"
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

任务明确返回 `False`（失败或未执行）时仍返回 HTTP 200：

```json
{
  "success": false,
  "message": "任务 ikuuu_checkin 未成功完成，请查看任务日志"
}
```

业务返回 `True`、监控入口返回 `None` 时报告成功。调用方必须检查 `success`，不能只检查 HTTP 状态。未捕获异常返回 HTTP 500：

```json
{
  "success": false,
  "message": "任务执行失败: 具体错误信息"
}
```

任务不存在返回 HTTP 404，未登录返回 HTTP 401。手动触发使用原始函数，绕过"当天已有成功记录则跳过"检查；业务内部的禁用或缺参校验仍有效，也不会经过每日成功记录包装层。

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
- [二次开发指南](SECONDARY_DEVELOPMENT.md) - 代码规范、black/ruff、测试等
