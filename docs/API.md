# API v1

管理接口统一使用 `/api/v1`，由同源 Vue 页面调用。新部署不提供旧 `/api/*` 协议迁移。除会话、登录与健康检查外，接口均要求登录；响应使用 `Cache-Control: no-store`。

## 会话与安全

先 `GET /api/v1/session`，获得 `authenticated` 和 `csrf_token`，同时接收 HttpOnly 会话 Cookie。所有写入请求，包括登录，必须携带该 Cookie 与 `X-CSRF-Token` 请求头。同源 `Origin` 校验适用于浏览器请求。登录成功返回新的 CSRF Token，后续请求必须更新。请求体上限 2 MiB。

| 方法 | 地址 | 请求／结果 |
|---|---|---|
| GET | `/session` | `{authenticated, csrf_token}` |
| POST | `/login` | JSON `{username, password}`；成功更新会话与 CSRF |
| POST | `/logout` | 清除当前会话 |
| POST | `/password` | `{old_password, new_password}`；新密码为 1–1024 字符，撤销其他会话 |

首次管理员默认账号 `admin`、密码 `123`；可选 `WEBMONITER_ADMIN_USERNAME`、`WEBMONITER_ADMIN_PASSWORD` 覆盖初始凭据。Argon2id 保存摘要；登录按来源地址限制 5 次／5 分钟，并限制同时进行的密码验证数量。会话有效期 7 天，活动时续期。生产 HTTPS 设置 `WEBMONITER_SECURE_COOKIE=1`。

## 任务与执行记录

| 方法 | 地址 | 说明 |
|---|---|---|
| GET | `/tasks` | `{tasks: [...]}`，含启用、可用、最近运行、下次执行时间 |
| POST | `/tasks/{job_id}/runs` | `202 {run_id, duplicate}`；立即入队 |
| GET | `/runs?limit=50` | 最近记录，最大 200 |
| GET | `/runs/{run_id}` | 指定运行状态和摘要 |

同一任务已有排队或执行实例时，提交返回已有 `run_id`。队列满返回 503 与 `Retry-After`，不存在的任务返回 404。所有手动、定时和启动入口共用队列；手动触发可绕过“今日已完成”，但不会绕过禁用配置。

运行状态：`queued`、`running`、`success`、`partial`、`failed`、`skipped`、`timeout`、`interrupted`。记录包含 `job_id`、`source`、`created_at`、`started_at`、`finished_at`、`message`。时间戳单位秒。最近记录有 10,000 条保留上限，重启时未完成任务标为中断，不自动重放外部操作。

## 配置

| 方法 | 地址 | 说明 |
|---|---|---|
| GET | `/config/metadata` | 配置模板、字段提示、多账号结构、任务与推送渠道元数据 |
| GET | `/config` | `{version, config}`；敏感字段返回不透明保留标记 |
| PUT | `/config` | `{version, config: {section: {...}}}` 分区更新 |
| POST | `/config/reveal` | `{version, content}`，完整敏感 YAML |
| PUT | `/config` | `{version, content}` 完整 YAML 保存 |
| GET | `/database/status` | 当前数据库后端、回退与同步状态 |
| POST | `/database/test` | `{mysql: {...}}` 测试未保存连接设置，支持原样提交密码保留标记 |

`version` 是当前文件内容摘要。版本不一致返回 409，用户必须重新读取并合并修改。未修改的 `__KEEP_SECRET__:` 标记应原样回传，显式空字符串用于清除凭据；标记与值绑定，账号重排不会串用密码。进程重启后重新读取配置。禁止将完整 YAML 或配置响应存入浏览器持久化缓存。

校验失败返回 422，`fields` 包含 `{path, message}`，前端定位配置分区和字段。错误不回传输入凭据。配置原子写入并热重载；Web 监听端口等启动参数修改后需重启。

## 监控数据

`GET /data/{platform}?page=1&page_size=50` 返回 `{data, page, page_size, total}`，每页最大 200。平台包括 `weibo`、`huya`、`bilibili_dynamic`、`bilibili_live`、`douyin`、`douyu`、`xhs`、`kuaishou`。字段与过滤参数见代码 `src/web/data_support.py`、`src/web/routers/data.py`。`GET /data/{platform}/{item_id}` 返回单条快照。

微博按入库时计算的 `published_at` 索引排序。MySQL 与 SQLite 的权威写入、镜像、outbox 和回退行为保持一致。旧无界 `/api/monitor-status` 接口不再挂载。

## 增量日志

`GET /logs?task=log_cleanup&lines=200&cursor=...` 返回 `{lines, cursor, reset}`。省略 `task` 读取主日志。下次提交上次游标；文件轮转或截断后 `reset=true`，客户端清空旧窗口。单次最多 1,000 行、256 KiB，首次读取当前文件尾部。尾部未写完的行留到下一次读取。前端最多保留 2,000 行，隐藏页面暂停轮询。

## 健康与错误

`GET /health/live` 表示 Web 进程存活；`GET /health/ready` 检查本地 SQLite 与执行服务，成功 200，启动中或故障 503，不依赖第三方平台在线。生产仅运行一个 Web／调度进程。

错误状态：401 未登录、403 CSRF／来源不符、409 配置冲突、413 体积超限、422 字段错误、429 登录限流、503 队列或服务暂不可用。错误正文为 `error` 或 FastAPI 的 `detail`；客户端统一解析，禁止将服务器原始异常直接展示为配置内容。
