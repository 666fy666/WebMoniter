# Web任务系统 项目架构文档

## 项目概述 {#project-overview}

WebMoniter 使用 Python 3.11、FastAPI 和 APScheduler，统一管理六类平台监控、定时签到与提醒、多渠道推送和 Web 管理。任务、配置节及推送类型清单以 `src/jobs/metadata.py` 和运行时代码为准。

部署操作见 [安装与运行](installation.md)，配置参数见 [配置说明](guides/config.md)，接口见 [API 参考](API.md)，扩展步骤见 [二次开发指南](SECONDARY_DEVELOPMENT.md)。本页集中说明模块边界、生命周期和一致性机制。

## 整体架构 {#overall-architecture}

`config.yml → AppConfig → 任务注册/调度 → 平台请求 → 数据库状态对比 → 推送通道`

Web 页面通过 HTTP API 编辑配置、手动执行任务、读取监控快照和日志，与调度器共享配置及存储。前端由 Jinja2 模板和原生 JavaScript/CSS 组成。

### 启动与关闭

1. `main.py` 初始化日志、读取配置，启动后台 Uvicorn；默认监听 `0.0.0.0:8866`，端口可通过 `PORT` 覆盖。
2. 重置 Cookie 有效性缓存，初始化 SQLite，并按配置启用或恢复 MySQL。
3. 根据元数据导入任务模块，注册 interval/Cron 任务并暂停未启用项；按注册顺序执行启动首轮。`run_on_startup=False` 的任务不参与首轮，任务内部仍校验自身配置。
4. 启动 `ConfigWatcher` 和调度循环，处理后续配置变化与定时执行。
5. 退出时停止调度、配置监控、Web 服务和数据库。清理步骤有超时，`src/core/runtime.py` 提供阻塞线程及进程退出兜底，避免同步请求或浏览器任务无限阻塞关闭。

源码启动的环境预检、浏览器依赖及 Docker slim/full 差异见 [安装与运行](installation.md)。

## 核心模块 {#core-modules}

<span id="directory-structure"></span>
<span id="design-patterns"></span>

| 模块 | 职责 |
|---|---|
| `main.py` | 启动和关闭应用，连接配置、调度、Web 与存储 |
| `src/core/` | 路径、运行时、预检、版本和 HTTP 工具 |
| `src/settings/` | `AppConfig`、YAML 映射、写入事务、配置热重载与监控对象同步 |
| `src/jobs/` | 元数据、任务注册、启用映射、调度、结果、运行记录和任务日志 |
| `src/monitors/` | 平台监控；`BaseMonitor` 管理 HTTP 会话、数据库、推送和 Cookie 失效处理 |
| `src/tasks/` | 定时签到和提醒；浏览器相关实现放在任务内部或子包 |
| `src/storage/` | SQLite、MySQL、镜像、离线队列及 Cookie 有效性缓存 |
| `src/push_channel/` | 通道适配、统一推送、富文本格式和内容长度限制 |
| `src/web/` | FastAPI 应用、按功能划分的路由、鉴权、模板与数据转换 |
| `src/webUI/` | 页面模板、原生 JavaScript、CSS 和静态资源 |
| `src/ql/` | 青龙 CLI 和环境变量兼容层 |
| `src/tests/` | 关键 Python 回归及 Node 前端行为测试 |

`TaskSpec` 描述模块路径、任务 ID、配置字段和展示信息；任务模块通过 `register_monitor()` 或 `register_task()` 自注册。兼容模块列表、enable 映射、青龙环境变量和 Web 元数据由规格生成。业务实现与元数据必须同时维护，不能仅添加文件就认为已完成注册。

## 数据流 {#data-flow}

- **监控**：加载目标及已有快照 → 有界并发请求平台 → 判断直播状态或动态是否变化 → 更新快照 → 按任务通道与免打扰设置推送。各平台首次运行、去重和媒体处理规则保留在各自模块。
- **定时任务**：检查启用状态及每日运行记录 → 执行业务 → 返回明确结果。默认包装器只在 `TASK_SUCCESS` 时记录当天成功，失败或未捕获异常允许重试。Web 手动执行使用原始函数，绕过每日跳过检查，但仍执行业务函数内的配置校验。
- **Web**：配置表单提交 JSON 补丁，YAML 视图提交完整文本；数据 API 读取监控快照，日志页轮询今日文件。监控表保存每个目标的最近状态，不是历史动态列表。

阻塞浏览器及同步请求通过线程池执行，默认执行器上限为 32。监控内部使用并发限制，推送按通道并发并隔离错误；SQLite/MySQL 操作通过共享锁协调。增加任务并发、拆除存储锁或并行首轮执行需要另行验证任务顺序、平台限流和数据一致性。

## 配置管理 {#config-management}

- 根目录 `config.yml` 经 `loader_specs.py` 映射为扁平字段，并处理多账号、Cookie/Token 列表，再由 Pydantic 创建 `AppConfig`。配置读取带缓存及进程内锁。
- `ConfigWatcher` 默认每 5 秒检查文件修改时间，使用模型完整字段对比检测变化；回调更新调度时间、启用状态、监控目标和数据库配置。
- Web JSON 保存在同一写入事务内读取最新文件、合并已提交字段、校验并保存；分区保存不提交其他分区。完整 YAML 保存覆盖整份文本。
- 共享写入工具保留已有注释和引号，优先原子替换；针对 Docker 单文件绑定挂载提供写入兼容处理。Cookie 刷新使用字段期望值检查，遇到并发修改时保留较新值。
- `db_sync.py` 将配置中的监控对象同步到已有表；具体字段、列表清理及通道合并语义见 [配置说明](guides/config.md) 和 [API 参考](API.md)。

## 数据库设计 {#database-design}

### 权威后端与连接

MySQL 未配置或不可连接时由 SQLite 接管读写。MySQL 配置完整且在线时作为权威后端，SQLite 始终保留本地镜像。业务通过 `AsyncDatabase` 访问，无需自行选择后端。

SQLite 使用共享 `aiosqlite` 连接、WAL、`synchronous=NORMAL` 和 30 秒 `busy_timeout`。执行前检查连接健康，连接失效时重建。实例 `close()` 减少共享引用，不直接释放全局连接；应用关闭由 `close_shared_connection()` 统一收尾。MySQL 使用共享 `aiomysql` 连接池，配置变化时重建。

### 同步与故障回退

1. 在线写入先提交 MySQL，再更新 SQLite；镜像失败标记 `mirror_degraded`，由后续校准恢复。
2. MySQL 连接类错误触发 SQLite 回退。离线业务写入与 `mysql_sync_outbox` 事件在同一个 SQLite 事务内提交。
3. 恢复时，若 MySQL 业务表全为空，从 SQLite 初始化；否则先按主键幂等重放 outbox，再以 MySQL 完整刷新 SQLite。不能把旧 SQLite 镜像直接当成在线 MySQL 的权威副本。
4. 维护循环每 30 秒检查恢复，MySQL 在线时每两个周期（约 60 秒）校准镜像，以接收外部客户端写入。

离线回放仅支持 `TABLE_SPECS` 中的表；条件更新和删除参数必须包含实际主键或通用 `pk`，整表清空只识别无条件的 `DELETE FROM <table>`。队列操作为 `upsert`、`delete` 或 `clear`，不支持任意批量条件 SQL 的自动回放。

数据库状态 API 返回 `sqlite_only`、`in_sync`、`fallback`、`replaying` 或 `mirror_degraded`。字段与示例见 [API 参考](API.md)。

### 数据表与迁移

| 表 | 主键 | 保存内容 |
|---|---|---|
| `weibo` | `UID` | 用户信息、最近微博、媒体和结构化正文 |
| `huya` | `room` | 名称、直播状态、封面和头像 |
| `bilibili_live` | `uid` | 名称、直播间和直播状态 |
| `bilibili_dynamic` | `uid` | 名称、最近动态 ID 与正文 |
| `douyin` | `douyin_id` | 名称和直播状态 |
| `douyu` | `room` | 名称和直播状态 |
| `xhs` | `profile_id` | 用户名、最近笔记 ID 与标题 |
| `task_run_history` | `job_id` | 最近成功执行日期 |
| `mysql_sync_outbox` | 事件编号 | 仅 SQLite：待回放的表、主键、操作、行快照和时间 |

SQLite `_init_tables()`、MySQL `TABLE_SPECS` 和 `MYSQL_COLUMN_MIGRATIONS` 共同定义结构与兼容迁移。MySQL 启动检查旧表字段，容忍竞争迁移中的重复字段错误；账号需要建表、改表、元数据查询和业务读写权限。增表或字段时需同时维护两种后端及字段顺序，步骤见 [二次开发指南](SECONDARY_DEVELOPMENT.md)。

## 推送通道 {#push-architecture}

任务从 `push_channel` 配置构建 `UnifiedPushManager`，非空 `push_channels` 按通道名称筛选，空列表表示使用全部已配置通道。初始化失败的通道被关闭并跳过，发送时一个通道失败不阻止其他通道。

统一管理器处理富文本在各通道的格式、UTF-8 字节限制和结果收集。免打扰由监控或任务在调用推送前判断，不应假定所有直接 `send_news()` 调用都会自动检查免打扰。具体配置见 [推送通道](guides/push-channels.md)。

## Web 服务 {#web-architecture}

`src/web/app.py` 组装路由、中间件和静态资源，模板共享环境由 `templating.py` 提供。配置、任务、数据、日志等接口分置于 `routers/`，完整契约以 [API 参考](API.md) 为准。

认证使用 SessionMiddleware 与服务端会话文件。`data/auth.json`、`data/session_secret`、`data/web_sessions.json` 分别保存账户、会话签名密钥和活跃会话；Cookie 与服务端会话默认一年有效，持久化 `data/` 才能保留重启后的登录状态。修改密码清理其他旧会话。

数据及日志 GET 通过请求编号和取消信号防止旧响应覆盖当前视图。虎牙先读取基础卡片，再补充图片；微博先按时间排序原始行、分页，再转换当前页媒体字段。图片加载保持三个并发。日志读取扩展文件尾窗口以满足行数，避免固定字节估算漏行；大文件 `total_lines` 是读取窗口行数。

本地 CSS/JavaScript 共用 `STATIC_ASSET_VERSION`，修改静态资源时更新这一处缓存版本；它与项目发布版本独立。界面、加载反馈、键盘和触屏说明见 [Web 管理界面](guides/web-ui.md)。

## 技术栈 {#tech-stack}

Python 版本约束和依赖以 `pyproject.toml`、`uv.lock` 为准。后端主要使用 FastAPI/Uvicorn、APScheduler、Pydantic、aiohttp、aiosqlite/aiomysql 和 ruamel.yaml；前端没有 npm 构建步骤。Node 仅用于开发时的少量前端回归测试。

## 扩展机制 {#extension}

新增任务需同时维护配置映射、业务入口、注册和元数据；新增持久化平台还需维护数据库、配置同步及 Web 转换；新增通道需维护通道工厂和元数据。具体步骤、真实示例及验证命令统一放在 [二次开发指南](SECONDARY_DEVELOPMENT.md)，避免重复维护实现副本。
