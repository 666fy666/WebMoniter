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
4. 启动 `ConfigWatcher`，然后创建 Web 资源预热任务并进入调度循环。预热不参与启动首轮，不阻塞调度，处理方式见下文。
5. 退出时停止调度、取消并等待预热任务，再停止配置监控、Web 服务和数据库。清理步骤有超时，`src/core/runtime.py` 提供阻塞线程及进程退出兜底，避免同步请求或浏览器任务无限阻塞关闭。

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

SQLite 使用共享 `aiosqlite` 连接、WAL、`synchronous=NORMAL` 和 30 秒 `busy_timeout`。执行前通过驱动公开属性识别已关闭连接，不为每条业务 SQL 排队额外的 `SELECT 1`；失效时在连接锁内重建，并复用其他调用者已恢复的连接。连接完成配置及建表后才发布，初始化失败或被取消时关闭局部连接，避免留下半初始化状态及工作线程。

实例 `close()` 减少共享引用，不直接释放全局连接；应用关闭由 `close_shared_connection()` 统一收尾。MySQL 使用共享 `aiomysql` 连接池，配置变化时重建。连接初始化、权威写入、镜像与 outbox 仍使用现有锁和事务，避免以并发优化破坏同步顺序。

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

会话文件只在路径、设备、inode、大小或纳秒修改时间发生变化时重新解析 JSON；每次鉴权仍检查文件状态、会话到期并执行原有续期逻辑。外部撤销、删除或损坏文件会在下一次检查生效，没有按 TTL 缓存登录权限。认证文件以同目录临时文件写入、刷新后原子替换，清理异常不覆盖保存结果。密码比较使用恒定时间比较，保留原密码散列格式；异常散列返回校验失败，保留登录及改密错误码。

### 启动后的异步预热

`src/web/warmup.py` 在数据库、启动首轮和配置监控就绪后，按以下阶段预热：

1. 在线程中编译八个页面及公共模板。
2. 在线程中创建带 certifi CA 校验的 TLS 上下文，HTTP 连接器复用这个上下文。
3. 从现有数据库读取最多 4096 条微博主键和正文，在线程中预计算日期与分页排序索引。

每个阶段有 10 秒等待预算，失败只记录阶段和异常类型，并继续下一阶段；成功记录耗时。关闭时取消并等待协程。线程中的同步工作不能被强制中断，但只处理上述有界的本地资源，仍受现有运行时退出机制管理。预热不触发监控、签到、推送或额外外部请求，也不建立第二套数据库连接池。

### 查询与缓存边界

微博分页每次先从当前权威数据库读取 `UID` 和正文中的时间，再按原来的时间规则及稳定顺序计算当前页主键；媒体、转发等完整字段只按这些主键读取，每批最多 500 个。行转换及较大的 JSON 编码移入线程，避免占用事件循环。虎牙图片接口对房间去重并每 500 个分批查询，保持原有返回结构。

时间解析缓存最多 2048 个不超过 80 字符的时间字段；排序缓存最多两份、每份不超过 4096 行，UID 超过 255 字符或非字符串时跳过排序缓存。缓存键来自本次查询的 UID、时间和原始顺序，写入或外部更新自然产生新键，不缓存正文、媒体或 API 响应。超过边界仍使用原排序规则处理全部结果。排序仍需读取匹配行的元数据，数据量增长时并非恒定成本；没有引入影响旧数据兼容性的字段迁移。

平台筛选及第二阶段批量读取使用已有主键索引，无需添加重复索引。分页参数、权限、错误码、SQL 参数绑定、MySQL 回退、镜像及幂等回放机制保持原有约定。

### 页面加载与交互

本地脚本使用 `defer` 并保持依赖顺序。SortableJS 固定为原有 1.15.2 版本，随静态资源提供并保留 MIT 授权，数据页拖拽不依赖 CDN 是否可达。配置页并行读取元数据、配置和状态，初始只布局默认模块，表单填充分段让出主线程；搜索和指针效果合并到动画帧，同一元素每帧复用一次几何测量。无障碍标签关联在每批 DOM 变化中集中建立，避免逐个控件读取 `labels` 并重复扫描整页，保留已有 HTML 标签、ARIA 名称和缺失名称回退。

数据、任务、配置和日志读取通过请求编号或取消信号防止旧响应覆盖当前视图。公共 GET 工具的 30 秒期限覆盖响应头及 JSON 响应体读取；数据加载失败提供原地重试。配置和任务写入保留原请求语义，不自动重试，避免重复执行。

配置表单跟踪各分区是否编辑及编辑版本，保存只刷新对应分区，保留其他分区和保存期间继续输入的内容。单推送通道保存只提交推送配置补丁。YAML 草稿在表格/文本视图切换、读取失败或保存期间继续编辑时保留，显式重新加载仍允许恢复服务端文本。

页面隐藏或离线时暂停日志自动刷新，恢复可见或网络后继续；离开页面时清理读取请求、计时器、观察器和动画帧，数据与任务页支持浏览器往返缓存恢复。指针离开卡片或窗口失焦时释放倾斜及合成层提示。虎牙仍先读取基础卡片，再补充图片；图片加载保持三个并发。日志读取扩展文件尾窗口以满足行数，避免固定字节估算漏行；大文件 `total_lines` 是读取窗口行数。

### 响应与可观测性

客户端支持时对超过 1024 字节的响应使用 gzip；微博图片和静态图片跳过重复压缩。API 响应增加 `Cache-Control: no-store`，避免共享缓存保留用户数据；响应体及状态码不变。`Server-Timing` 提供生成响应头前的应用耗时，超过 500 毫秒时记录方法、路由模板、状态码和耗时，不记录查询参数、实际用户 ID 或请求内容。

本地 CSS/JavaScript 共用 `STATIC_ASSET_VERSION`，修改静态资源时更新这一处缓存版本；它与项目发布版本独立。仅携带唯一且正确版本参数的静态资源使用一年不可变缓存，无版本或错误版本要求重新验证；图片 404 不带长期不可变缓存，避免稍后生成的图片持续不可见。界面、加载反馈、键盘和触屏说明见 [Web 管理界面](guides/web-ui.md)。

### 设计参考

参考 [Uptime Kuma 的数据库初始化](https://github.com/louislam/uptime-kuma/blob/master/server/database.js) 和 [青龙的启动加载器](https://github.com/whyour/qinglong/blob/develop/back/loaders/app.ts)，结合本项目保留共享连接、WAL、连接池和分阶段初始化；启动关键流程完成后才调度可失败的后台预热。生命周期及前端暂停机制也参考 [FastAPI 生命周期文档](https://fastapi.tiangolo.com/advanced/events/) 和 [MDN 页面可见性文档](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API)。这些是针对现有架构的取舍，没有引入新的服务或运行依赖。

## 性能与回归验证（2026-10-01）

Python 完整回归 277 项、Node 前端行为回归 17 项通过；覆盖主流程就绪后预热及取消、初始化失败关闭连接、连接重建、外部更新后的排序、分批分页、鉴权缓存失效、异常散列与认证文件保存失败、压缩及资源缓存边界，以及旧请求、超时、页面隐藏、分区/YAML 草稿保存竞态和无障碍名称规则。Ruff、所改 Python 文件的 Black 检查和 `git diff --check` 通过。

本地 SQLite 基准使用临时数据库、3000 条不同发布时间的微博，每条含 30 个长图片 URL，页大小 25；同一脚本分别运行修改前版本、修改后未预热和修改后完成预热版本。顺序调用取 12 次中位数，并另测 16 个并发请求：

| 版本 | 首次调用 | 后续调用中位数 | 16 并发 P95 | 16 并发吞吐 |
|---|---:|---:|---:|---:|
| 修改前 | 48.47 ms | 40.19 ms | 667.29 ms | 24.0 次/秒 |
| 修改后，未预热 | 36.05 ms | 7.89 ms | 163.99 ms | 97.1 次/秒 |
| 修改后，已预热 | 9.77 ms | 8.10 ms | 202.22 ms | 78.8 次/秒 |

这是本机单次合成样本，直接调用路由，不能代表生产网络或所有数据规模；并发采样存在运行环境波动。预热主要减少首次日期解析与排序成本，后续收益来自批量读取当前页和复用排序。

真实 Chrome 使用样例配置及隔离数据库，检查配置、任务、数据和日志页在桌面 1280×900、手机 390×844 下的加载与交互，并阻断外部 HTTPS 依赖。七个平台切换、分页、灯箱、模拟手动任务、任务日志、分区和 YAML 草稿保护、显式 YAML 重载通过。最终八次页面检查均无 JavaScript 错误、整页横向溢出或达到 50 ms 的长任务。对比采样中，配置页 DOM 就绪在桌面由 67 ms 降至 47 ms，在手机由 91 ms 降至 55 ms。性能采样定位并消除了约 40 ms 的重复标签扫描，时间值仍受本机负载影响。

相同尺寸和样例数据下，最终手机配置、任务、日志页稳定状态截图逐像素一致；数据页仅有图标边缘的 9 个像素渲染差异，内容及布局一致。

验证没有使用真实平台凭据。MySQL 的迁移、断连回退、镜像与 outbox 回放由现有回归测试覆盖，未进行真实 MySQL 服务或生产流量压测。

可在仓库根目录执行：

```bash
.venv/bin/python -m pytest -q
node src/tests/frontend_runtime.test.js
.venv/bin/ruff check .
git diff --check
```

### 本次变更文件

| 范围 | 文件 |
|---|---|
| 启动、HTTP 与数据库 | `main.py`、`src/core/http.py`、`src/storage/database.py` |
| Web 服务 | `src/web/app.py`、`src/web/auth.py`、`src/web/data_support.py`、`src/web/routers/data.py`、`src/web/static_files.py`、`src/web/templating.py`、`src/web/middleware.py`、`src/web/warmup.py` |
| 页面脚本与样式 | `src/webUI/static/js/common.js`、`config.js`、`data.js`、`logs.js`、`tasks.js`；`src/webUI/static/css/style.css` |
| 页面模板 | `src/webUI/templates/base.html`、`login.html`、`config.html`、`data.html`、`logs.html`、`tasks.html` |
| 固定版本静态依赖 | `src/webUI/static/vendor/Sortable.min.js`、`src/webUI/static/vendor/Sortable.LICENSE` |
| 回归测试 | `src/tests/frontend_runtime.test.js`、`test_database_refcount.py`、`test_main_lifecycle.py`、`test_web_api.py`、`test_web_auth_sessions.py`、`test_web_performance.py` |
| 架构与验证记录 | `docs/ARCHITECTURE.md` |

## 技术栈 {#tech-stack}

Python 版本约束和依赖以 `pyproject.toml`、`uv.lock` 为准。后端主要使用 FastAPI/Uvicorn、APScheduler、Pydantic、aiohttp、aiosqlite/aiomysql 和 ruamel.yaml；前端没有 npm 构建步骤。Node 仅用于开发时的少量前端回归测试。

## 扩展机制 {#extension}

新增任务需同时维护配置映射、业务入口、注册和元数据；新增持久化平台还需维护数据库、配置同步及 Web 转换；新增通道需维护通道工厂和元数据。具体步骤、真实示例及验证命令统一放在 [二次开发指南](SECONDARY_DEVELOPMENT.md)，避免重复维护实现副本。
