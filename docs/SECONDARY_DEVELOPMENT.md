# 二次开发指南：新增监控任务与定时任务

本文档说明如何在不改动项目核心逻辑的前提下，用最少改动接入新的**监控任务**或**定时任务**，并支持配置热重载与统一推送。  
下文以项目内已实现的**虎牙监控**（监控任务）和 **iKuuu 签到 / Demo 任务**（定时任务）为例，按步骤对照真实代码说明。

---

## 零、开发环境与代码规范

### 代码检测

项目使用 `black` 和 `ruff` 进行代码格式化和检查。

#### 安装开发依赖

```bash
uv sync --extra dev
```

本地开发与调试 **iKuuu、雨云签到**（`src/tasks/ikuuu_checkin.py`、`src/tasks/rainyun`）时，还需安装 optional 依赖：`uv sync --locked --extra rainyun`（可与 `dev` 同时指定：`uv sync --locked --extra dev --extra rainyun`）。

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
# 或指定目录：uv run pytest src/tests/ -q
```

`src/tests/test_jobs_metadata.py` 与 `src/tests/test_registry_integrity.py` 会在新增任务时校验 `TaskSpec`、兼容模块清单与 enable 映射是否一致；漏配时测试失败。

---

## 一、架构简述

| 类型       | 触发方式     | 配置来源示例                          | 项目内示例           |
|------------|--------------|---------------------------------------|----------------------|
| 监控任务   | 固定间隔轮询 | `huya.monitor_interval_seconds`、`weibo.monitor_interval_seconds` | 虎牙监控、微博监控   |
| 定时任务   | Cron 每日定点 | `checkin.time`、`tieba.time`、`plugins.xxx.time` | iKuuu 签到、贴吧签到、Demo 任务 |

新增任务时只需：

1. **新增配置**：在 `config.yml` 中增加节点；若用顶层配置，还需在 `src/settings/config.py` 中补充字段与解析。
2. **补充配置映射**：若用顶层配置，在 `src/settings/config.py` 中增加 `AppConfig` 字段，并在 `src/settings/loader_specs.py` 中补充 YAML 到扁平字段的映射规格。
3. **实现任务逻辑**：一个无参的 async 入口函数（内部 `get_config(reload=True)`、业务逻辑、可选推送），返回 `TASK_SUCCESS` 或 `TASK_FAILED`（见 `src/jobs/task_outcome.py`）。
4. **注册与元数据**：在任务模块末尾调用 `register_monitor` 或 `register_task`，并在 `src/jobs/metadata.py` 的 `MONITOR_SPECS` / `TASK_SPECS` 中添加对应 `TaskSpec`。

主入口 `main.py` 通过 `src.jobs.registry.discover_and_import()` 加载所有列出的模块并注册到调度器，**无需再改 main.py**。

Web 后端统一放在 `src/web/`，按“应用组装 → 路由模块 → 辅助逻辑”分层，新增 Web 功能时优先复用：

- `src/web/app.py`：FastAPI 应用创建、SessionMiddleware、静态资源挂载、router 注册。
- `src/web/routers/`：页面、认证、任务、配置、数据、日志等 APIRouter。
- `src/web/auth.py`：登录会话、认证文件读写、密码哈希。
- `src/web/config_io.py`：配置合并、配置保存前校验与热重载。
- `src/web/data_support.py`：数据 API 的平台元数据、SQL 模板、数据库行到 JSON 的转换。
- `src/web/templating.py`、`src/web/static_files.py`：Jinja 模板环境与带 Cache-Control 的静态文件处理。
- `register_monitor` / `register_task` 的 `description` 参数：Web 任务列表展示文案。
- `src/settings/loader_specs.py`：`config.yml` 节点到 `AppConfig` 扁平字段的映射，以及多账号、多 Cookie/Token 字段规格。

---

## 二、定时任务示例一：iKuuu 签到（顶层配置）

iKuuu 签到使用**顶层配置**（与贴吧签到一致）：在 `config.yml` 中有独立节点 `checkin`，在 `AppConfig` 中有对应扁平字段，适合需要强类型、与现有风格统一的场景。

> **域名自动发现**：iKuuu 的可用域名会自动从 `ikuuu.club` 提取，无需在配置中手动填写 URL。系统在每次签到时会访问 `ikuuu.club`，通过多种正则匹配和 HTTP 探测从其混淆 JS 中提取可用域名（如 `ikuuu.nl`、`ikuuu.fyi` 等），并随机选择一个使用。

### 2.1 配置：config.yml

在 `config.yml` 中增加与 `tieba` 同级的 `checkin` 节点（参见 `config/config.yml.sample`）。

**单账号示例：**

```yaml
checkin:
  enable: false
  email: your@email.com
  password: your_password
  time: "08:00"   # 每日执行时间 HH:MM
```

**多账号示例（`accounts` 非空时优先于单账号 `email`/`password`）：**

```yaml
checkin:
  enable: true
  time: "08:00"
  accounts:
    - email: user1@example.com
      password: pass1
    - email: user2@example.com
      password: pass2
```

### 2.2 配置：src/settings/config.py

在 `AppConfig` 中增加扁平字段（与 YAML 的 `checkin` 一一对应）：

```python
# 每日签到配置（域名自动从 ikuuu.club 发现，无需手动配置 URL）
checkin_enable: bool = False
checkin_email: str = ""
checkin_password: str = ""
checkin_time: str = "08:00"
```

在 `src/settings/loader_specs.py` 的 `CONFIG_MAPPINGS` 中补充 `checkin` 节点到 `AppConfig` 扁平字段的映射；如果支持 `accounts` 多账号，再在 `MULTI_ACCOUNT_SPECS` 中补充对应规格。`load_config_from_yml()` 会统一按这些规格写入 `config_dict`。

### 2.3 任务实现：src/tasks/ikuuu_checkin.py

**① 配置校验与入口**

- 使用 dataclass 从 `AppConfig` 转成任务用配置，并做 `validate()`（未启用或缺少必填项则直接 return）：
- 域名通过 `_extract_ikuuu_domain()` 自动从 `ikuuu.club` 提取，URL 由域名自动构建（`@property`）：

```python
@dataclass
class CheckinConfig:
    enable: bool
    domain: str    # 自动发现的域名，如 ikuuu.nl
    email: str
    password: str
    time: str

    @property
    def login_url(self) -> str:
        return f"https://{self.domain}/auth/login"

    @property
    def checkin_url(self) -> str:
        return f"https://{self.domain}/user/checkin"

    @property
    def user_page_url(self) -> str:
        return f"https://{self.domain}/user"

    @classmethod
    def from_app_config(cls, config: AppConfig, domain: str) -> CheckinConfig:
        return cls(
            enable=config.checkin_enable,
            domain=domain,
            # ...
            time=config.checkin_time.strip() or "08:00",
        )

async def run_checkin_once() -> None:
    app_config = get_config(reload=True)
    if not app_config.checkin_enable:
        return
    # 自动发现 ikuuu 可用域名
    domain = await _extract_ikuuu_domain()
    if not domain:
        logger.error("ikuuu签到：无法自动发现可用域名，跳过本次执行")
        return
    cfg = CheckinConfig.from_app_config(app_config, domain=domain)
    if not cfg.validate():
        return
    # 业务逻辑：登录 → 签到 → 获取流量信息
    async with aiohttp.ClientSession(...) as session:
        push_manager = await build_push_manager(
            app_config.push_channel_list, session, logger, init_fail_prefix="ikuuu签到：",
            channel_names=cfg.push_channels if cfg.push_channels else None,  # 指定使用的通道
        )
        cookie = await _login_and_get_cookie(session, cfg)
        if not cookie:
            await _send_checkin_push(push_manager, title="ikuuu签到失败：登录失败", ...)
            return
        ok = await _checkin(session, cfg, cookie)
        traffic_info = await _get_user_traffic(session, cfg, cookie)
        await _send_checkin_push(push_manager, title=..., msg=..., success=ok, traffic_info=traffic_info)
        if push_manager:
            await push_manager.close()
```

**② 推送逻辑**

- 推送前用 `is_in_quiet_hours(app_cfg)` 判断免打扰，在免打扰时段内只打日志不推送：

```python
async def _send_checkin_push(push_manager, title, msg, success, cfg, traffic_info=None):
    if push_manager is None:
        return
    app_cfg = get_config()
    if is_in_quiet_hours(app_cfg):
        logger.debug("ikuuu签到：免打扰时段，不发送推送")
        return
    await push_manager.send_news(
        title=f"{title}（{masked_email}）",
        description=...,
        to_url=cfg.user_page_url,
        picurl="...",
        btntxt="查看账户",
    )
```

**③ 注册：Cron 触发参数 + register_task**

- 执行时间由 `checkin.time` 决定，使用公共方法 `parse_checkin_time` 得到 cron 的 `hour`、`minute`，并在模块末尾注册：

```python
from src.settings.config import AppConfig, get_config, is_in_quiet_hours, parse_checkin_time
from src.jobs.registry import register_task

def _get_checkin_trigger_kwargs(config: AppConfig) -> dict:
    hour, minute = parse_checkin_time(config.checkin_time)
    return {"minute": minute, "hour": hour}

register_task("ikuuu_checkin", run_checkin_once, _get_checkin_trigger_kwargs)
```

**④ 当天已运行则跳过（默认行为）**

`register_task` 默认启用 `skip_if_run_today=True`，任务在执行前会检查当天是否已经运行过：
- 如果已运行：输出日志 `{job_id}: 当天已经运行过了，跳过该任务`，然后跳过执行
- 如果未运行：正常执行任务；函数正常返回（未抛异常）后记录运行日期
- 如果任务抛出未捕获异常：不记录运行日期，允许后续重试
- 若任务内部自行捕获错误并 return，仍会被视为已运行

若某个任务需要每次触发都执行（不检查当天是否已运行），可在注册时禁用：

```python
register_task("always_run_task", run_task, _get_trigger_kwargs, skip_if_run_today=False)
```

**⑤ 手动触发执行**

通过 Web 管理界面的「任务管理」页面手动触发任务时，会使用 `JobDescriptor.original_run_func`（原始执行函数），绕过"当天已运行则跳过"检查，确保任务被强制执行。这对于调试或需要立即重新执行的场景非常有用。

### 2.4 任务元数据：src/jobs/metadata.py

在 `TASK_SPECS` 中已包含该模块，主程序启动时会根据元数据生成兼容的 `TASK_MODULES`，再导入并执行上述 `register_task`：

```python
TaskSpec(
    module="src.tasks.ikuuu_checkin",
    job_id="ikuuu_checkin",
    description="iKuuu 签到",
    config_section="checkin",
    enable_field="checkin_enable",
    time_field="checkin_time",
    push_field="checkin_push_channels",
    ql_prefix="IKUUU",
)
```

小结：顶层定时任务 = **config.yml 节点 → AppConfig + loader_specs 映射 → 任务模块（run_xxx_once + 推送 + _get_xxx_trigger_kwargs）→ register_task → TaskSpec 一项**。

---

## 三、定时任务示例二：Demo 任务（plugins 配置）

Demo 任务使用 **plugins** 配置：无需改 `AppConfig` 和 `load_config_from_yml()`，只需在 `config.yml` 的 `plugins` 下增加一个 key，适合快速扩展、字段灵活的场景。

### 3.1 配置：config.yml

```yaml
plugins:
  demo_task:
    enable: false
    time: "08:30"
    message: "Demo 定时任务执行完成"
```

### 3.2 任务实现：src/tasks/demo_task.py

- 从 `config.plugins.get("demo_task", {})` 读配置；未启用则直接 return。
- 使用 `parse_checkin_time(plug.get("time", "08:00"))` 得到 cron 的 hour/minute。
- 推送前用 `is_in_quiet_hours(config)` 判断免打扰。

核心片段：

```python
PLUGIN_KEY = "demo_task"

def _get_plugin_config(config: AppConfig) -> dict:
    return config.plugins.get(PLUGIN_KEY) or {}

async def run_demo_task_once() -> bool:
    config = get_config(reload=True)
    plug = _get_plugin_config(config)
    if not plug.get("enable", False):
        return TASK_FAILED
    # ... 业务与推送 ...
    return TASK_SUCCESS

def _get_demo_task_trigger_kwargs(config: AppConfig) -> dict:
    plug = _get_plugin_config(config)
    hour, minute = parse_checkin_time((plug.get("time") or "08:00").strip())
    return {"minute": minute, "hour": hour}

register_task("demo_task", run_demo_task_once, _get_demo_task_trigger_kwargs)
```

在 `src/jobs/registry.py` 的 `TASK_MODULES` 中需包含 `"src.tasks.demo_task"`（当前已包含）。  
完整代码见 `src/tasks/demo_task.py`。

---

## 四、监控任务示例：虎牙直播监控

虎牙监控按**固定间隔**轮询房间状态，使用顶层配置 + 继承 `BaseMonitor`，是典型的监控任务写法。

### 4.1 配置：config.yml

```yaml
huya:
  enable: true                  # 是否启用该监控，默认 true；设为 false 时任务暂停
  rooms: 991108,333003,518518   # 逗号分隔的房间号
  concurrency: 7
  monitor_interval_seconds: 65   # 轮询间隔（秒）
```

### 4.2 配置：src/settings/config.py

- **AppConfig** 中增加扁平字段：`huya_enable`、`huya_rooms`、`huya_concurrency`、`huya_monitor_interval_seconds`。
- **src/settings/loader_specs.py**：在 `CONFIG_MAPPINGS["huya"]` 中声明从 `yml_config["huya"]` 到 `AppConfig` 扁平字段的映射，`load_config_from_yml()` 会统一处理。
- 提供 **get_huya_config()** 返回结构化配置（列表 + 并发数），供监控类使用：

```python
class HuyaConfig(BaseModel):
    rooms: list[str]
    concurrency: int = 7

def get_huya_config(self) -> HuyaConfig:
    rooms = [r.strip() for r in self.huya_rooms.split(",") if r.strip()]
    return HuyaConfig(rooms=rooms, concurrency=self.huya_concurrency)
```

见 `src/settings/config.py` 中 `HuyaConfig`、`AppConfig.get_huya_config`，以及 `src/settings/loader_specs.py` 中的 huya 映射段落。

### 4.3 监控实现：src/monitors/huya_monitor.py

**① 继承 BaseMonitor**

- `BaseMonitor` 负责：`config`、`session`、`db`、`push`、`initialize()`（数据库 + 推送）、`close()`。子类只需实现 `run()` 和 `monitor_name`，以及可选的 `_get_session` 重写（如固定 User-Agent/Cookie）。

```python
from src.monitors.base import BaseMonitor

class HuyaMonitor(BaseMonitor):
    def __init__(self, config: AppConfig, session=None):
        super().__init__(config, session)
        self.huya_config = config.get_huya_config()
        self.old_data_dict = {}
        self._is_first_time = False

    async def initialize(self):
        await super().initialize()
        await self.load_old_info()   # 从 DB 加载旧状态

    async def run(self):
        new_config = get_config(reload=False)
        self.config = new_config
        self.huya_config = new_config.get_huya_config()
        # 并发轮询房间，比对 old_data_dict，有变化则更新 DB 并 push_notification
        semaphore = asyncio.Semaphore(self.huya_config.concurrency)
        tasks = [process_with_semaphore(rid) for rid in self.huya_config.rooms]
        await asyncio.gather(*tasks, return_exceptions=True)

    @property
    def monitor_name(self) -> str:
        return "虎牙直播监控🐯  🐯  🐯"
```

**② 推送**

- 在业务逻辑里调用 `self.push.send_news(...)`；推送前用 `is_in_quiet_hours(self.config)` 判断免打扰，若在免打扰时段则只打日志不推送。见 `huya_monitor.py` 中 `push_notification`。

**③ 对外入口与注册**

- 对外暴露一个无参的 async 函数，内部 `get_config(reload=True)` 后 `async with HuyaMonitor(config) as monitor: await monitor.run()`。
- 提供 `_get_huya_trigger_kwargs(config)` 返回 `{"seconds": config.huya_monitor_interval_seconds}`，并在模块末尾 `register_monitor`：

```python
async def run_huya_monitor() -> None:
    config = get_config(reload=True)
    async with HuyaMonitor(config) as monitor:
        await monitor.run()

def _get_huya_trigger_kwargs(config: AppConfig) -> dict:
    return {"seconds": config.huya_monitor_interval_seconds}

from src.jobs.registry import register_monitor
register_monitor("huya_monitor", run_huya_monitor, _get_huya_trigger_kwargs)
```

见 `src/monitors/huya_monitor.py` 末尾。

### 4.4 注册表：src/jobs/registry.py

在 `MONITOR_MODULES` 中已包含虎牙模块（当前全部监控模块如下）：

```python
MONITOR_MODULES: list[str] = [
    "src.monitors.huya_monitor",
    "src.monitors.weibo_monitor",
    "src.monitors.bilibili_monitor",
    "src.monitors.douyin_monitor",
    "src.monitors.douyu_monitor",
    "src.monitors.xhs_monitor",
]
```

### 4.5 配置热重载与数据库同步

项目已对所有 `AppConfig` 字段做完整覆盖，修改后约 5 秒内热重载生效。`config_watcher` 通过 Pydantic `model_dump()` 自动对比所有字段，**新增字段无需手动维护比较列表**。

**新增监控任务时**，若新监控使用 uid/room 类列表且需要从配置中删除时同步清理数据库，需在 `src/settings/db_sync.py` 的 `sync_rules` 中增加对应规则（配置属性名 → 表名 + 主键列名）。

**新增定时任务时**：只要在 `AppConfig` 中添加了对应字段，热重载即自动覆盖，无需额外操作。

小结：监控任务 = **config.yml（业务节点含 enable + scheduler 间隔）→ AppConfig + loader_specs 映射 + get_xxx_config → 继承 BaseMonitor 实现 run + 推送 → run_xxx_monitor + _get_xxx_trigger_kwargs → register_monitor → TaskSpec 一项**。`enable: false` 时任务会被暂停，热重载生效。

---

## 五、监控任务需要数据库时该怎么办

很多监控任务需要**持久化上一次状态**（例如上次是否在播、上次微博内容），以便本次轮询时对比、仅在变化时推送。本项目的做法是：**继承 BaseMonitor 即自带数据库与推送**，数据库使用项目内统一的 SQLite（`data/data.db`），由 `AsyncDatabase` 封装。

### 5.1 继承 BaseMonitor 即获得 self.db

在 `src/monitors/base.py` 中，`BaseMonitor.initialize()` 会：

- 创建 `self.db = AsyncDatabase()` 并 `await self.db.initialize()`；
- 创建 `self.push`（统一推送）；
- 可选 `self.session`（HTTP）。

因此你的监控类**只需继承 BaseMonitor**，在 `initialize()` 里可先 `await super().initialize()`，再加载本监控需要的“旧数据”；在 `run()` 里用 `self.db` 做查询/更新/插入即可。无需自己 new AsyncDatabase 或管理连接。

### 5.2 AsyncDatabase 常用 API（src/storage/database.py）

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `execute_query(sql, params=None)` | 查询，占位符用 `%(key)s`，params 为 dict | `list[tuple]`，每行一个元组 |
| `execute_update(sql, params=None)` | 执行 UPDATE/INSERT/DELETE | `bool`（是否成功） |
| `execute_insert(sql, params=None)` | 同 execute_update，语义上用于插入 | `bool` |
| `is_table_empty(table_name)` | 判断表是否为空（可用于“首次运行”逻辑） | `bool` |

- **SQL 占位符**：写 `%(name)s`、`%(room)s` 等，params 传字典如 `{"name": "xx", "room": "123"}`。模块内部会转换为 SQLite 的 `:name` 格式，无需改 SQL。
- **连接**：默认使用全局共享连接（单进程内复用），重试与重连已在 `execute_*` 内处理。

### 5.3 新监控需要新表时：在 database.py 中加表

当前所有表结构都在 `src/storage/database.py` 的 `_init_tables()` 里统一创建（`CREATE TABLE IF NOT EXISTS ...`）。  
若你的监控需要**自己的表**（例如 `my_monitor`），在 **`src/storage/database.py`** 的 **`_init_tables()`** 中增加一段即可，与现有 `weibo`、`huya` 表并列，例如：

```python
# 在 _init_tables(self, conn) 末尾、await conn.commit() 前增加：

# 创建 my_monitor 表（示例）
await conn.execute(
    """
    CREATE TABLE IF NOT EXISTS my_monitor (
        id TEXT PRIMARY KEY,
        name TEXT,
        status TEXT,
        updated_at TEXT
    )
    """
)
await conn.commit()
```

表名、字段名按你的业务设计即可；主键建议能唯一标识一条监控对象（如房间号、用户 ID）。

### 5.4 虎牙监控中的用法示例（对照代码）

- **加载旧数据**（在 `initialize()` 里调用，或 `run()` 开头）：  
  用 `execute_query` 把上一轮存的状态读进内存，供本轮对比：

```python
async def load_old_info(self):
    sql = "SELECT room, name, is_live FROM huya"
    results = await self.db.execute_query(sql)
    self.old_data_dict = {row[0]: row for row in results}
    self._is_first_time = len(self.old_data_dict) == 0
```

- **有变化时更新**：  
  用 `execute_update`，占位符与字典一一对应：

```python
sql = "UPDATE huya SET name=%(name)s, is_live=%(is_live)s WHERE room=%(room)s"
await self.db.execute_update(sql, data)
```

- **新对象首次写入**：  
  用 `execute_insert`：

```python
sql = "INSERT INTO huya (room, name, is_live) VALUES (%(room)s, %(name)s, %(is_live)s)"
await self.db.execute_insert(sql, data)
```

- **首次建表/首次运行**：  
  虎牙用 `_is_first_time` 标记“表里之前没有数据”。首次跑满一轮时只写入 DB、不推送，避免历史数据被当成“新变化”刷屏；从第二轮开始才按变化推送。你可按同样思路处理。

完整实现见 `src/monitors/huya_monitor.py`（`load_old_info`、`process_room` 中的 SQL 与 `self.db` 调用）。

### 5.5 小结：监控 + 数据库的步骤

1. **继承 BaseMonitor**，在 `initialize()` 里 `await super().initialize()` 后加载旧数据到内存（如 `load_old_info`）。
2. 在 **`src/storage/database.py` 的 `_init_tables()`** 里为你的监控**增加 CREATE TABLE IF NOT EXISTS**（若需要新表）。
3. 在 `run()` 里：拉取当前数据 → 与旧数据对比 → 有变化则 `execute_update` / `execute_insert` 更新 DB，并调用 `self.push.send_news(...)`；无变化则只打日志。
4. SQL 使用 **`%(key)s` + dict 参数**，通过 `self.db.execute_query` / `execute_update` / `execute_insert` 访问；连接与重试由 AsyncDatabase 统一处理。

---

## 六、推送逻辑（统一说明）

- 推送通道统一来自 `config.push_channel_list`（即 `config.yml` 的 `push_channel`），无需在任务里新增通道类型。
- **通道选择机制**：每个任务可以在配置中通过 `push_channels` 字段指定使用哪些推送通道（按名称匹配）。为空时使用全部已配置的通道。
- 在任务/监控内：
  1. 使用 `await build_push_manager(config.push_channel_list, session, logger, init_fail_prefix="任务名：", channel_names=["通道1", "通道2"])` 得到 `UnifiedPushManager`。`channel_names` 参数可选，用于指定仅初始化哪些通道（按 `name` 字段匹配），为空或 None 时使用全部通道。
  2. 需要推送时调用 `await push_manager.send_news(title=..., description=..., to_url=..., picurl=..., btntxt=...)`。
  3. 遵守免打扰：推送前 `if is_in_quiet_hours(config): return`（或只打日志），再调用 `send_news`。
  4. 使用完毕后 `await push_manager.close()`。

虎牙在类内使用 `self.push`（BaseMonitor 在 `initialize` 里已创建，会自动读取任务配置的 `push_channels`）；iKuuu/Demo 在 async 函数内自己创建 `push_manager` 并在同一 session 生命周期内 close。  
推送失败建议用 `logger.error(..., exc_info=True)` 记录，不中断主流程。

**任务专属日志**：新增任务无需额外处理，系统会在执行时自动将输出写入 `task_{job_id}_YYYYMMDD.log`。Handler 挂载在 root logger，可捕获任务内所有 logger（模块、类、推送通道等）的输出。

---

## 七、示例文件与代码位置一览

| 类型     | 示例       | 配置文件 | 配置解析 | 任务/监控实现 | 注册 |
|----------|------------|----------|----------|----------------|------|
| 定时任务 | iKuuu 签到 | `config.yml` → `checkin` | `AppConfig` + `CONFIG_MAPPINGS` / `MULTI_ACCOUNT_SPECS` | `src/tasks/ikuuu_checkin.py`（`run_checkin_once`、`_send_checkin_push`、`_get_checkin_trigger_kwargs`） | `register_task("ikuuu_checkin", ...)`，`TASK_SPECS` 含 `src.tasks.ikuuu_checkin` |
| 定时任务 | Demo 任务  | `config.yml` → `plugins.demo_task` | 无需改 config.py，用 `config.plugins.get("demo_task")` | `src/tasks/demo_task.py` | `register_task("demo_task", ...)`，`TASK_SPECS` 含 `src.tasks.demo_task` |
| 定时任务 | Freenom 续期 | `config.yml` → `freenom` | `AppConfig` + `CONFIG_MAPPINGS` / `MULTI_ACCOUNT_SPECS` | `src/tasks/freenom_checkin.py`（`run_freenom_checkin_once`、`_get_freenom_trigger_kwargs`） | `register_task("freenom_checkin", ...)`，`TASK_SPECS` 含 `src.tasks.freenom_checkin` |
| 定时任务 | 天气推送   | `config.yml` → `weather` | `AppConfig` + `CONFIG_MAPPINGS` | `src/tasks/weather_push.py`（`run_weather_push_once`、`_get_weather_trigger_kwargs`） | `register_task("weather_push", ...)`，`TASK_SPECS` 含 `src.tasks.weather_push` |
| 监控任务 | 虎牙监控   | `config.yml` → `huya`（含 `monitor_interval_seconds`） | `AppConfig`、`HuyaConfig`、`get_huya_config`、`CONFIG_MAPPINGS` | `src/monitors/huya_monitor.py`（`HuyaMonitor`、`run_huya_monitor`、`_get_huya_trigger_kwargs`） | `register_monitor("huya_monitor", ...)`，`MONITOR_SPECS` 含 `src.monitors.huya_monitor` |

- **parse_checkin_time**：`src/settings/config.py`，将 `"HH:MM"` 解析为 `(hour, minute)` 字符串元组，供 Cron 使用。
- **BaseMonitor**：`src/monitors/base.py`，提供 `config`、`db`、`push`、`initialize`、`close`，子类实现 `run`、`monitor_name`。

---

## 八、检查清单：新增定时任务

- [ ] 在 `config.yml` 中增加配置（顶层节点或 `plugins.xxx`）。
- [ ] 若用顶层配置：在 `AppConfig` 中补充字段，并在 `src/settings/loader_specs.py` 中补充映射规格；若用 `plugins`，无需改 config.py。
- [ ] 新建 `src/tasks/xxx.py`，实现 `run_xxx_once()`（内部 `get_config(reload=True)`、校验、业务、推送，成功返回 `TASK_SUCCESS`、失败或未执行返回 `TASK_FAILED`）、`_get_xxx_trigger_kwargs(config)`（返回 `{"minute": m, "hour": h}`，可用 `parse_checkin_time`）。
- [ ] 在模块末尾调用 `register_task("job_id", run_xxx_once, _get_xxx_trigger_kwargs)`。
  - 默认启用 `skip_if_run_today=True`，当天已运行则跳过
  - 若需每次触发都执行，设置 `skip_if_run_today=False`
- [ ] 在 `src/jobs/metadata.py` 的 `TASK_SPECS` 中添加 `TaskSpec`（包含模块路径、`job_id`、描述、配置节、enable/time/push 字段；plugins 任务标记 `plugin_only=True`）。
- [ ] 若该任务支持青龙环境变量：在同一个 `TaskSpec` 中配置 `ql_prefix` 与 `ql_env_fields`。

---

## 九、检查清单：新增监控任务

- [ ] 在 `config.yml` 中增加业务节点（如 `my_monitor`），并在该节点下增加 `monitor_interval_seconds` 字段（例如 `my_monitor.monitor_interval_seconds`）。
- [ ] 在 `AppConfig` 中增加扁平字段，在 `src/settings/loader_specs.py` 中补充映射规格；可选：提供 `get_my_monitor_config()` 返回结构化配置。热重载通过 `model_dump()` 自动覆盖所有字段，无需手动维护比较列表。
- [ ] 若监控使用 uid/room 类列表且需配置删除时同步清理 DB：在 `db_sync.sync_rules` 中增加对应规则（配置属性名 → 表名 + 主键列名）。
- [ ] 新建 `src/monitors/xxx.py`，继承 `BaseMonitor` 实现 `run()`、`monitor_name`，以及 `run_xxx_monitor()`、`_get_xxx_trigger_kwargs(config)`（返回 `{"seconds": config.xxx_interval_seconds}`）。
- [ ] **若监控需要数据库**：在 `src/storage/database.py` 的 `_init_tables()` 中增加 `CREATE TABLE IF NOT EXISTS your_table (...)`；在监控类 `initialize()` 里加载旧数据，在 `run()` 里用 `self.db.execute_query` / `execute_update` / `execute_insert` 读写（参见 **五、监控任务需要数据库时该怎么办**）。
- [ ] 在模块末尾调用 `register_monitor("job_id", run_xxx_monitor, _get_xxx_trigger_kwargs)`。
- [ ] 在 `src/jobs/metadata.py` 的 `MONITOR_SPECS` 中添加 `TaskSpec`（包含模块路径、`job_id`、描述、配置节、enable/push 字段）。

完成以上步骤后，新任务会被主程序自动加载、按配置调度，并在配置变更时通过 ConfigWatcher 热重载。

---

## 十、Web 前端对新增配置的响应

- **文本视图**：直接读写整份 `config.yml`，新增的任意 key（如 `plugins`、`freenom`、`weather` 等）都会完整显示、可编辑，保存后整份写回，**会正确响应**。
- **表格视图**：当前展示微博、虎牙、各类签到任务（iKuuu、贴吧、雨云、恩山、阿里云盘、什么值得买、Freenom、夸克、科技玩家、帆软、999、zgfc、双色球等）、调度器、免打扰、推送通道以及**插件配置**等固定区块。
  - 在表格视图中修改并保存时，后端会**合并**写回，因此文件中已有的 `plugins` 或其他顶层节点不会丢失。  
  - 插件配置可在配置页底部的「插件/扩展配置」中以 JSON 形式编辑 `config.plugins`；尚未在表格中单独列出的顶层 key 需使用文本视图编辑。

若你新增了与现有区块同级的配置（例如新的顶层节点），并希望在表格中编辑，需在 Web 前端增加对应卡片及 `loadSectionConfig` / `collectSectionConfig` / `collectConfig` 的处理（可参考本文档中已集成的 `freenom`/`weather`/`kuake`/`kjwj` 等实现方式）。

---

## 十一、青龙面板 CLI（python -m src.ql）

青龙环境下，主程序不运行，而是由青龙按 Cron 执行：

```bash
cd /path/to/WebMoniter && python -m src.ql <task_id>
```

- `src/ql/__main__.py` 通过 `discover_and_import_tasks_only()` 加载 `TASK_MODULES`，再调用 `_runner.run_task()`
- 配置来自**环境变量**（`WEBMONITER_*` 前缀），由 `src/ql/compat.py` 的 `load_config_from_env()` / `inject_ql_config()` 解析
- 推送通过 **qlapi** 通道，调用青龙内置的 `QLAPI.systemNotify`
- 与 `src/tasks/*`、`src/monitors/*` 主流程解耦，共用同一套业务逻辑（如签到、监控 API 调用）

**新增青龙任务**：在 `src/tasks/` 实现任务并在 `src/jobs/metadata.py` 的 `TASK_SPECS` 添加 `TaskSpec` 后，即可通过 `python -m src.ql <job_id>` 运行。详见 [青龙面板兼容指南](QINGLONG.md)。
