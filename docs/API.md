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

---

### 2. 配置管理

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

| 平台   | `platform` | 主键 ID 含义 | 示例 |
|--------|------------|--------------|------|
| 微博   | `weibo`    | 用户 UID     | `1234567890` |
| 虎牙   | `huya`     | 房间号 room  | `123456` |

#### 列表：分页 + 可选过滤

```http
GET /api/data/{platform}?page=1&page_size=100
GET /api/data/weibo?uid=1234567890&page=1&page_size=20
GET /api/data/huya?room=123456&page=1&page_size=20
```

- `platform`：`weibo` 或 `huya`
- `page`：页码，从 1 开始（默认 1）
- `page_size`：每页条数（默认 100）
- `uid`：仅当 `platform=weibo` 时有效，按用户 UID 过滤
- `room`：仅当 `platform=huya` 时有效，按房间号过滤

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

#### 全部监控状态

```http
GET /api/monitor-status
```

返回示例：

```json
{
  "success": true,
  "data": {
    "weibo": [
      {
        "UID": "1234567890",
        "用户名": "示例用户",
        "认证信息": "认证信息",
        "简介": "用户简介",
        "粉丝数": 10000,
        "微博数": 500,
        "文本": "最新微博内容",
        "mid": "微博ID"
      }
    ],
    "huya": [
      {
        "room": "123456",
        "name": "主播名称",
        "is_live": true
      }
    ]
  },
  "timestamp": "2024-01-01T12:00:00"
}
```

#### 按平台

```http
GET /api/monitor-status/weibo
GET /api/monitor-status/huya
```

返回该平台下所有监控项的数组，格式同上（`data` 为数组）。

#### 按平台 + 主键 ID（单条）

```http
GET /api/monitor-status/weibo/{uid}
GET /api/monitor-status/huya/{room}
```

示例：`GET /api/monitor-status/weibo/1234567890`、`GET /api/monitor-status/huya/123456`  
成功时 `data` 为单条对象；未找到时返回 `404`。

---

### 5. 日志查询

#### 获取日志

```http
GET /api/logs?lines=100
```

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

# 获取配置
config_response = session.get(f"{BASE_URL}/api/config")
print(config_response.json())

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
```

### cURL 示例

```bash
# 登录
curl -X POST http://localhost:8866/api/login \
  -d "username=admin&password=123" \
  -c cookies.txt

# 获取配置（使用保存的 Cookie）
curl -X GET http://localhost:8866/api/config \
  -b cookies.txt

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

- [README](../README.md) - 项目概览与快速开始
- [二次开发指南](SECONDARY_DEVELOPMENT.md) - 代码规范、black/ruff、测试等
