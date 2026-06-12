# Web任务系统 项目架构文档

## 📋 目录

- [项目概述](#project-overview)
- [整体架构](#overall-architecture)
- [核心模块详解](#core-modules)
- [数据流设计](#data-flow)
- [扩展机制](#extension)
- [技术栈](#tech-stack)
- [目录结构](#directory-structure)
- [关键设计模式](#design-patterns)
- [配置管理](#config-management)
- [数据库设计](#database-design)
- [推送通道架构](#push-architecture)
- [Web服务架构](#web-architecture)

---

## 项目概述 {#project-overview}

Web任务系统（项目代号 WebMoniter）是一个基于 Python 的**多平台任务系统**，采用异步IO架构，支持：

- **多平台监控**：虎牙直播、微博等平台的实时监控
- **定时任务**：iKuuu签到、百度贴吧签到、微博超话签到等
- **多渠道推送**：支持15+种推送通道（企业微信、钉钉、Telegram、Bark等）
- **配置热重载**：修改配置文件无需重启，5秒内自动生效
- **Web管理界面**：提供友好的Web界面进行配置管理和数据查看

### 核心特性

- ✅ **异步IO架构**：基于 `asyncio` 和 `aiohttp`，支持高并发
- ✅ **任务调度**：基于 `APScheduler` 的灵活任务调度系统
- ✅ **插件化设计**：监控和定时任务采用插件化架构，易于扩展
- ✅ **配置热重载**：配置文件修改后自动检测并应用，无需重启
- ✅ **Cookie管理**：智能Cookie缓存和过期检测机制
- ✅ **免打扰时段**：支持配置免打扰时段，静默运行监控任务
- ✅ **版本更新检测**：自动检测 GitHub 新版本并在 Web 界面提示更新

---

## 整体架构 {#overall-architecture}

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Web Server  │  │  Scheduler   │  │ Config Watcher│   │
│  │  (FastAPI)   │  │ (APScheduler)│  │  (热重载)     │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘   │
└─────────┼──────────────────┼─────────────────┼────────────┘
          │                  │                 │
          │                  │                 │
┌─────────▼──────────────────▼─────────────────▼────────────┐
│                    Job Registry                            │
│  ┌──────────────┐              ┌──────────────┐          │
│  │ MONITOR_JOBS │              │  TASK_JOBS   │          │
│  └──────┬───────┘              └──────┬───────┘          │
└─────────┼─────────────────────────────┼──────────────────┘
          │                             │
          │                             │
┌─────────▼─────────────────────────────▼──────────────────┐
│  ┌──────────────┐              ┌──────────────┐         │
│  │  Monitors    │              │    Tasks     │         │
│  │  Huya/Weibo  │              │  Checkin/    │         │
│  │  Bilibili/   │              │  Tieba 等    │         │
│  └──────┬───────┘              └──────┬───────┘         │
└─────────┼─────────────────────────────┼──────────────────┘
          │                             │
          │                             │
┌─────────▼─────────────────────────────▼──────────────────┐
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Database   │  │ Push Manager │  │ Cookie Cache │   │
│  │  (SQLite)    │  │  (统一推送)  │  │  (状态管理)  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└───────────────────────────────────────────────────────────┘
```

### 系统启动流程

1. **初始化阶段**
   - 设置日志系统：先 `setup_logging()`（仅控制台；非 TTY 环境不输出到控制台），创建 Web 应用与 Uvicorn 服务器（FastAPI）后，再挂载 `main` 文件日志 Handler（`LogManager.setup_file_logging("main")`）到 root logger
   - Web 服务默认端口 8866，可通过环境变量 `PORT` 覆盖
   - 加载配置文件 (`config.yml`)；失败则 `sys.exit(1)`
   - 重置 Cookie 缓存 (`cookie_cache.reset_all()`)

2. **任务注册阶段**
   - 通过 `src.jobs.registry.discover_and_import()` 按 `MONITOR_MODULES`、`TASK_MODULES` 导入任务模块
   - 各模块调用 `register_monitor()` 或 `register_task()` 注册任务
   - 任务描述符 (`JobDescriptor`) 被添加到 `MONITOR_JOBS` 或 `TASK_JOBS`

3. **调度器启动阶段**
   - 创建 `TaskScheduler` 实例（基于 `APScheduler`）
   - 遍历 `MONITOR_JOBS` 和 `TASK_JOBS`，注册到调度器
   - 启动时立即执行一次所有任务（首次运行）

4. **Web 服务与配置监控启动**
   - Web 服务以 `asyncio.create_task` 与调度器并行运行
   - 启动 `ConfigWatcher`（默认每 5 秒检查 `config.yml` 修改时间）

5. **配置变化回调**（由 ConfigWatcher 在检测到变化时触发）
   - 先执行 `sync_config_to_db`（删除配置中已移除的 uid/room 对应数据库记录）
   - 再更新调度器任务参数（间隔、Cron、暂停/恢复、免打扰）

6. **运行阶段**
   - 调度器按配置的间隔/时间执行任务
   - 监控任务检测变化并推送通知
   - 定时任务按Cron表达式执行
   - Web服务处理HTTP请求

---

## 核心模块详解 {#core-modules}

### 1. main.py - 主入口模块

**职责**：系统启动和生命周期管理

**关键功能**：
- 初始化日志系统（控制台；main 文件日志在创建 Web 应用后挂载）
- 创建并启动 Web 服务器（FastAPI + Uvicorn）
- 加载配置并创建调度器
- 注册所有监控和定时任务
- 启动配置监控器（热重载）
- 处理优雅关闭（信号处理）

**关键代码流程**（`main.py` 负责编排，`src/jobs/lifecycle.py` 封装 Web/调度细节）：
```python
async def main():
    # 1. 设置日志（控制台；非 TTY 不输出）
    setup_logging(log_level="INFO", console_output=not is_background)
    # 2. 创建 Web 应用与 Uvicorn，后台启动 Web 服务
    web_app = create_web_app()
    server = build_uvicorn_server(web_app)
    web_task = start_uvicorn_background(server, logger)
    setup_main_file_logging()  # 挂载 main_YYYYMMDD.log

    # 3. 加载配置（失败则 sys.exit(1)）
    config = get_config()

    # 4. 重置 Cookie 缓存
    await cookie_cache.reset_all()

    # 5. 创建调度器、发现并注册任务、启动首轮执行
    scheduler = TaskScheduler(config)
    await register_and_prime_jobs(scheduler, config)

    # 6. 启动配置监控（热重载），回调 on_scheduler_config_changed
    config_watcher = ConfigWatcher(..., on_config_changed=...)
    await config_watcher.start()

    # 8. 运行调度器（阻塞直至收到停止信号）；finally 中优雅关闭 Web/监控器/DB
    await scheduler.run_forever()
```

---

### 2. src/settings/config.py / src/settings/loader_specs.py - 配置管理模块

**职责**：配置文件的加载、解析、验证与 YAML 映射规格管理

**核心类**：
- `AppConfig`：配置数据模型（基于 Pydantic）
- `WeiboConfig`：微博配置子模型
- `HuyaConfig`：虎牙配置子模型
- `CONFIG_MAPPINGS`：`config.yml` 节点到 `AppConfig` 扁平字段的映射规格
- `MULTI_ACCOUNT_SPECS` / `MULTI_STRING_SPECS`：多账号、多 Cookie/Token 字段解析规格

**关键功能**：
- 从YAML文件加载配置
- 配置缓存机制（避免重复读取）
- 配置验证（Pydantic模型验证）
- 扁平化配置映射（YAML嵌套 → 扁平字段，规格集中在 `src/settings/loader_specs.py`）

**配置结构**：
```python
class AppConfig(BaseModel):
    # 微博配置
    weibo_cookie: str
    weibo_uids: str  # 逗号分隔
    weibo_concurrency: int
    
    # 虎牙配置
    huya_rooms: str  # 逗号分隔
    huya_concurrency: int
    
    # 调度器配置
    huya_monitor_interval_seconds: int
    weibo_monitor_interval_seconds: int
    
    # 推送通道配置
    push_channel_list: list[dict]
    
    # 免打扰时段
    quiet_hours_enable: bool
    quiet_hours_start: str
    quiet_hours_end: str
    
    # 插件配置（供扩展使用）
    plugins: dict
```

**配置加载流程**：
1. `load_config_from_yml()` 读取YAML文件
2. 按 `CONFIG_MAPPINGS` 将嵌套结构转换为扁平结构
3. 按 `MULTI_ACCOUNT_SPECS` / `MULTI_STRING_SPECS` 解析多账号与多字符串字段
4. 创建 `AppConfig` 实例（Pydantic验证）
5. 缓存配置实例（`_config_cache`）

---

### 3. src/monitors/base.py - 监控基类

**职责**：提供监控任务的抽象基类和通用功能

**核心类**：
- `BaseMonitor`：监控基类（抽象类）
- `CookieExpiredError`：Cookie过期异常

**关键功能**：
- 数据库初始化和管理
- 推送服务初始化和管理
- HTTP会话管理（共享或独立）
- Cookie过期检测和处理
- 异步上下文管理器支持

**基类接口**：
```python
class BaseMonitor(ABC):
    @abstractmethod
    async def run(self):
        """运行监控任务"""
        pass

    @property
    @abstractmethod
    def monitor_name(self) -> str:
        """监控器名称"""
        pass

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """平台名称（用于 Cookie 缓存）"""
        pass

    @property
    def push_channel_names(self) -> list[str] | None:
        """推送通道名称列表，用于过滤；返回 None 或空列表时使用全部通道。子类可重写以返回任务配置中的 push_channels。"""
        return None
```

**子类实现示例**：
- `HuyaMonitor`：虎牙直播监控
- `WeiboMonitor`：微博监控

---

### 4. src/jobs/scheduler.py - 任务调度器

**职责**：基于APScheduler的任务调度管理

**核心类**：
- `TaskScheduler`：任务调度器封装
- `TaskGroupFormatter`：日志格式化器（任务组分隔）

**关键功能**：
- 添加间隔任务（`add_interval_job`）
- 添加Cron任务（`add_cron_job`）
- 更新任务参数（热重载支持）
- 优雅关闭（信号处理）：Ctrl+C 后停止调度器接收新任务，不无限等待正在执行的同步任务；第二次 Ctrl+C 强制退出

**任务类型**：
- **间隔任务**：使用 `IntervalTrigger`，按固定间隔执行
  - 示例：虎牙监控每 65 秒执行一次，哔哩哔哩监控每 60 秒执行一次
- **Cron任务**：使用 `CronTrigger`，按时间表达式执行
  - 示例：每天08:00执行签到任务

**热重载支持**：
- `update_interval_job()`：更新间隔任务的间隔时间
- `update_cron_job()`：更新Cron任务的执行时间

### 5. src/core/runtime.py - 运行时与退出兜底

**职责**：统一运行 asyncio 主协程，并处理 Ctrl+C 时的退出兜底。

**关键功能**：
- 使用带 daemon worker 的默认线程池，避免 `asyncio.to_thread()` 中的同步网络/Selenium 任务拖住进程。
- 关闭时取消未完成异步任务，并给默认线程池一个短超时。
- 收到 Ctrl+C 后启动 watchdog；若清理流程卡住，会在兜底时间后强制退出。

---

### 6. src/storage/database.py - 数据库模块

**职责**：异步SQLite数据库操作

**核心类**：
- `AsyncDatabase`：异步数据库操作类

**关键特性**：
- **共享连接模式**：多个实例共享同一个数据库连接（提高性能）
- **WAL模式**：启用Write-Ahead Logging，提高并发性能
- **连接健康检查**：自动检测连接失效并重连
- **重试机制**：数据库锁定时的指数退避重试
- **SQL兼容**：支持MySQL风格的参数占位符转换

**表结构**：
```sql
-- 微博表
CREATE TABLE weibo (
    UID TEXT PRIMARY KEY,
    用户名 TEXT NOT NULL,
    认证信息 TEXT,
    简介 TEXT,
    粉丝数 TEXT,
    微博数 TEXT,
    文本 TEXT,
    mid TEXT
);

-- 虎牙表
CREATE TABLE huya (
    room TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_live TEXT
);
```

**连接管理**：
- 全局单例连接（`_shared_connection`）
- 引用计数机制（`_connection_ref_count`）
- 线程安全的连接管理（`_connection_lock`）

---

### 7. src/jobs/registry.py - 任务注册表

**职责**：统一管理监控和定时任务的注册

**核心概念**：
- `JobDescriptor`：任务描述符（job_id、run_func、trigger、get_trigger_kwargs、original_run_func；其中 original_run_func 用于 Web 手动触发时绕过「当天已运行则跳过」）
- `MONITOR_MODULES`：监控模块列表
- `TASK_MODULES`：定时任务模块列表
- `MONITOR_JOBS`：已注册的监控任务列表
- `TASK_JOBS`：已注册的定时任务列表

**注册流程**：
1. 在 `MONITOR_MODULES` 或 `TASK_MODULES` 中添加模块路径
2. `discover_and_import()` 按 `MONITOR_MODULES`、`TASK_MODULES` 顺序导入模块，模块加载时调用 `register_monitor()` 或 `register_task()`，任务描述符加入 `MONITOR_JOBS` 或 `TASK_JOBS`
3. 调度器启动时注册 `MONITOR_JOBS`、`TASK_JOBS`

**扩展新任务**：
```python
# 1. 在 src/monitors/ 或 src/tasks/ 下创建模块（见 docs/SECONDARY_DEVELOPMENT.md）
# 2. 在 src/jobs/registry.py 的 MONITOR_MODULES 或 TASK_MODULES 中追加模块路径
MONITOR_MODULES: list[str] = [
    "src.monitors.huya_monitor",
    "src.monitors.weibo_monitor",
    "src.monitors.bilibili_monitor",
    "src.monitors.douyin_monitor",
    "src.monitors.douyu_monitor",
    "src.monitors.xhs_monitor",
    "src.monitors.new_monitor",  # 新增
]

# 3. 在模块中注册任务
from src.jobs.registry import register_monitor

async def run_new_monitor():
    # 监控逻辑
    pass

register_monitor(
    job_id="new_monitor",
    run_func=run_new_monitor,
    get_trigger_kwargs=lambda c: {"seconds": c.new_monitor_interval_seconds}
)
```

---

### 8. src/settings/db_sync.py - 配置与数据库同步

**职责**：在配置热重载时，删除配置中已移除的 uid/room 对应的数据库记录，保持配置与数据库一致。

**核心函数**：
- `sync_config_to_db(old_config, new_config)`：对比新旧配置中的监控列表（weibo_uids、huya_rooms、bilibili_uids、douyin_douyin_ids、douyu_rooms、xhs_profile_ids），计算 `removed_ids = old_ids - new_ids`，对每个监控平台对应的表执行 `DELETE`，删除已从配置中移除的记录。首次启动（`old_config is None`）时不执行删除。

**支持的平台与表映射**：微博 → weibo.UID；虎牙 → huya.room；哔哩哔哩 → bilibili_dynamic.uid、bilibili_live.uid；抖音 → douyin.douyin_id；斗鱼 → douyu.room；小红书 → xhs.profile_id。

---

### 9. src/jobs/lifecycle.py - 生命周期编排

**职责**：Web 服务、任务注册与首轮执行、配置热重载回调等启动/关闭细节（由 `main.py` 调用）。

**关键函数**：
- `register_and_prime_jobs()`：`discover_and_import()` → 注册间隔/Cron 任务 → 暂停未启用监控 → 启动时对所有任务执行首轮
- `on_scheduler_config_changed()`：热重载时 `sync_config_to_db` + 更新 APScheduler 间隔/Cron/暂停状态
- `build_uvicorn_server()` / `start_uvicorn_background()` / `shutdown_web_server()`：Web 服务启停

---

### 10. src/settings/watcher.py - 配置监控器

**职责**：监控配置文件变化并触发热重载

**核心类**：
- `ConfigWatcher`：配置文件监控器

**关键功能**：
- 定期检查配置文件修改时间（默认5秒）
- 检测到变化时重新加载配置
- 比较配置内容变化（避免无效重载）
- 触发回调函数更新调度器任务参数

**热重载流程**：
1. `ConfigWatcher` 每 5 秒检查 `config.yml` 的修改时间（`check_interval` 默认 5）
2. 检测到 `st_mtime` 变化时：调用 `get_config(reload=True)` 重新加载
3. 通过 `_config_changed()` 利用 Pydantic `model_dump()` 对比新旧配置的完整序列化结果，判断是否发生实际变化。避免文件保存但内容未变时误触发
4. 若有变化则调用 `on_config_changed()` 回调
5. 回调内先执行 `sync_config_to_db`（删除配置中已移除的 uid/room），再更新调度器任务参数（间隔、Cron、暂停/恢复、免打扰）

**配置变化检测**：
- 利用 `model_dump()` 自动覆盖 AppConfig 的所有字段（新增字段无需手动维护比较列表）
- 避免因文件保存但内容未变而触发重载

---

### 11. src/storage/cookie_cache.py - Cookie缓存管理

**职责**：管理各平台Cookie的过期状态

**核心类**：
- `CookieCache`：Cookie缓存管理器

**关键功能**：
- Cookie有效性状态缓存（`valid`）
- 过期提醒发送状态（`notified`）
- 文件持久化（`data/cookie_cache.json`）
- 异步操作（带锁保护）

**缓存结构**：
```json
{
  "weibo": {
    "valid": true,
    "notified": false
  },
  "huya": {
    "valid": true,
    "notified": false
  }
}
```

**状态管理**：
- `mark_expired()`：标记Cookie为过期
- `mark_valid()`：标记Cookie为有效（重置提醒状态）
- `reset_all()`：启动时重置所有Cookie为有效状态
- `is_notified()`：检查是否已发送过期提醒

**使用场景**：
- 监控任务检测到Cookie失效时，调用 `mark_expired()`
- 避免重复发送Cookie过期提醒（通过 `notified` 标记）
- Cookie恢复有效时，重置提醒状态，允许下次过期时再次提醒

---

### 12. src/push_channel/ - 推送通道模块

**职责**：统一管理多种推送通道

**核心组件**：
- `_push_channel.py`：推送通道基类
- `manager.py`：统一推送管理器
- 各通道实现：`wecom_apps.py`、`dingtalk_bot.py` 等

**支持的推送通道**：
- 企业微信（自建应用、群聊机器人）
- 钉钉（群聊机器人）
- 飞书（自建应用、群聊机器人）
- Telegram机器人
- QQ频道机器人、NapCatQQ
- Server酱、PushPlus、WxPusher
- Bark、Gotify、Webhook、Email

**推送通道基类**：
```python
class PushChannel(ABC):
    @abstractmethod
    async def push(self, title, content, jump_url, pic_url, extend_data):
        """推送消息"""
        pass
```

**统一推送管理器**：
- `UnifiedPushManager`：管理多个推送通道
- `send_news()`：并发发送到所有启用的通道
- 支持通道特定的描述生成（`description_func`）

**通道注册机制**：
```python
# src/push_channel/__init__.py
_channel_type_to_class = {
    "wecom_apps": WeComApps,
    "dingtalk_bot": DingtalkBot,
    # ...
}

def get_push_channel(config: dict, session) -> PushChannel:
    channel_type = config.get("type")
    return _channel_type_to_class[channel_type](config, session)
```

---

### 13. src/web/ - Web服务器

**职责**：提供 Web 管理界面和 API 接口。`src/web/app.py` 负责 FastAPI 应用组装，具体接口按功能拆到 `src/web/routers/`，通用逻辑放在同一 `src/web/` 功能包内。

**技术栈**：
- FastAPI：Web框架
- Jinja2：模板引擎
- Uvicorn：ASGI服务器

**主要功能**：
- **配置管理**：在线编辑 `config.yml`（保留注释）
- **数据查看**：查看监控数据（分页、过滤）
- **日志查看**：查看系统日志
- **API接口**：RESTful API供外部调用

**模块层级**：
- `src/web/app.py`：应用创建、SessionMiddleware、静态资源挂载、router 注册
- `src/web/routers/pages.py`：页面模板路由
- `src/web/routers/auth.py`：登录、登出、改密、版本 API
- `src/web/routers/tasks.py`：任务列表与手动执行 API
- `src/web/routers/config.py`：配置读取与保存 API
- `src/web/routers/data.py`：数据展示与监控状态 API
- `src/web/routers/logs.py`：日志读取 API
- `src/web/auth.py`：登录会话、认证文件读写、密码哈希
- `src/web/config_io.py`：配置合并、配置保存前校验、热重载触发
- `src/web/data_support.py`：数据 API 的平台元数据、SQL 模板、数据库行到 JSON 的转换
- `JobDescriptor.description`：任务 ID 到展示文案（在 `register_*` 时注册）

**页面路由**：
- `/`：首页（已登录则配置页，未登录则登录页）
- `/login`：登录页面
- `/config`：配置管理页面
- `/tasks`：任务管理页面
- `/data`：数据展示页面
- `/logs`：日志展示页面

**API接口**：
- `GET /api/config`：获取配置
- `POST /api/config`：保存配置（触发热重载）
- `GET /api/data/{platform}`：获取监控数据
- `GET /api/logs`：获取日志内容（可选 `task` 参数指定任务今日日志）
- `GET /api/logs/tasks`：获取任务日志列表
- `GET /api/monitor-status`：获取全部监控状态（无需登录）
- `GET /api/monitor-status/{platform}`：按平台获取监控状态（无需登录）
- `GET /api/version`：获取版本信息（无需登录，用于前端检测新版本）

**配置保存特性**：
- 使用 `ruamel.yaml` 保留YAML注释
- 配置验证（加载测试）
- 保存后自动触发热重载

---

### 14. src/jobs/log_manager.py - 日志管理

**职责**：统一管理日志文件

**核心类**：
- `LogManager`：日志管理器
- `DailyRotatingFileHandler`：按日期轮转的文件处理器

**关键功能**：
- 按日期自动轮转日志文件（`main_20250130.log`）
- 日志清理（删除超过保留天数的日志）
- 日志文件大小统计

**日志文件结构**：
```
logs/
  main_20250130.log           # 今日总日志
  main_20250129.log
  task_ikuuu_checkin_20250130.log   # 各任务专属日志（按任务名+日期）
  task_huya_monitor_20250130.log
  task_log_cleanup_20250130.log
```

- 总日志 `main_*.log`：所有输出汇总
- 任务日志 `task_{job_id}_*.log`：每个任务执行时单独写入

**任务日志实现**：`src.jobs.registry` 通过 `_task_logging_context` 异步上下文管理器，在任务执行期间将专属文件 Handler 挂到 `logging.root`，执行结束后自动移除。这样可统一捕获监控类（`BaseMonitor` 的 `__class__.__name__` logger）、推送通道、定时任务模块等所有相关输出，避免仅挂模块 logger 时漏掉监控/推送日志。

**日志清理**：
- 定时任务每天执行一次（默认 02:10）
- 删除超过 `retention_days` 天的日志文件（包括总日志和各任务日志）
- 从文件名提取日期或使用文件修改时间

---

### 15. src/core/version.py - 版本信息模块

**职责**：管理应用版本信息，支持版本更新检测

**核心功能**：
- 从 `pyproject.toml` 读取当前版本号
- 提供 GitHub 仓库信息（用于检测新版本）
- 缓存版本号避免重复读取

**版本获取流程**：
1. 优先从 `importlib.metadata.version()` 读取（已安装包场景）
2. 失败则从 `pyproject.toml` 直接解析版本号
3. 缓存到 `__version__` 变量

**导出内容**：
```python
from src.core.version import (
    __version__,          # 当前版本号，如 "2.3.5"
    GITHUB_RELEASES_URL,  # GitHub Tags 页面 URL
    GITHUB_API_LATEST_TAG # GitHub API 获取 tags 的 URL
)
```

**前端版本检测流程**：
1. 前端调用 `GET /api/version` 获取当前版本和 GitHub API 地址
2. 前端调用 GitHub Tags API 获取最新 tag 的 `name`
3. 比较版本号，若有新版本则显示更新提示横幅
4. 用户可点击跳转至 GitHub Tags 页面查看更新内容

---

## 数据流设计 {#data-flow}

### 监控任务执行流程

```
1. 调度器触发任务
   ↓
2. 监控任务初始化
   - 加载数据库中的旧数据
   - 初始化推送服务
   ↓
3. 并发获取平台数据
   - 使用 aiohttp 请求平台API/页面
   - 解析响应数据
   ↓
4. 数据对比
   - 与数据库中的旧数据对比
   - 检测变化（新内容、开播等）
   ↓
5. 更新数据库
   - 插入或更新数据
   ↓
6. 推送通知（如有变化）
   - 检查免打扰时段
   - 构建推送消息
   - 并发发送到所有启用的推送通道
   ↓
7. 记录日志
```

### 定时任务执行流程

```
1. 调度器触发任务（Cron）
   ↓
2. 检查当天是否已运行（skip_if_run_today）
   - 查询 task_run_history 表
   - 如果当天已运行，记录日志并跳过
   - Web「立即运行」使用 original_run_func，不经过此检查
   ↓
3. 任务初始化
   - 加载配置
   - 初始化推送服务
   ↓
4. 执行任务逻辑
   - 登录（如需要）
   - 执行签到/清理等操作
   ↓
5. 标记为已运行
   - 任务函数正常返回（未抛出异常）后更新 task_run_history 表
   - 若任务内部捕获错误并仍正常 return，也会被视为已运行
   ↓
6. 推送结果
   - 构建推送消息
   - 发送到推送通道
   ↓
7. 记录日志
```

### 配置热重载流程

```
1. ConfigWatcher 检测文件变化
   ↓
2. 重新加载配置
   - get_config(reload=True)
   - 解析YAML并验证
   ↓
3. 比较配置变化
  - 利用 Pydantic model_dump() 完整对比所有 AppConfig 字段
  ↓
4. 配置与数据库同步（sync_config_to_db）
  - 从配置中删除的 uid/room 对应删除数据库记录
  ↓
5. 更新调度器
   - 更新间隔任务的间隔时间
   - 更新Cron任务的执行时间
   - 更新免打扰时段配置
   ↓
6. 记录日志
```

---

## 扩展机制 {#extension}

### 添加新监控平台

**步骤**：

1. **创建监控模块**（`src/monitors/new_platform_monitor.py`）
```python
from src.monitors.base import BaseMonitor, CookieExpiredError
from src.settings.config import get_config

class NewPlatformMonitor(BaseMonitor):
    @property
    def monitor_name(self) -> str:
        return "新平台监控"
    
    @property
    def platform_name(self) -> str:
        return "new_platform"
    
    async def run(self):
        config = get_config()
        # 监控逻辑
        pass

# 注册任务
from src.jobs.registry import register_monitor

async def run_new_platform_monitor():
    config = get_config()
    async with NewPlatformMonitor(config) as monitor:
        await monitor.run()

register_monitor(
    job_id="new_platform_monitor",
    run_func=run_new_platform_monitor,
    get_trigger_kwargs=lambda c: {"seconds": c.new_platform_interval_seconds}
)
```

2. **在 `src/jobs/registry.py` 中添加模块路径**
```python
MONITOR_MODULES = [
    "src.monitors.huya_monitor",
    "src.monitors.weibo_monitor",
    "src.monitors.new_platform_monitor",  # 新增
]
```

3. **在 `src/settings/config.py` 中添加配置字段**
```python
class AppConfig(BaseModel):
    new_platform_interval_seconds: int = 300
    # 其他配置...
```

4. **在 `loader_specs.py` 中添加配置映射**
```python
CONFIG_MAPPINGS = {
    "new_platform": {
        "interval_seconds": "new_platform_interval_seconds",
    },
    # ...
}
```

### 添加新定时任务

**步骤**：

1. **创建任务模块**（`src/tasks/new_task.py`）
```python
from src.jobs.registry import register_task
from src.settings.config import get_config, parse_checkin_time

async def run_new_task():
    config = get_config()
    # 任务逻辑
    pass

register_task(
    job_id="new_task",
    run_func=run_new_task,
    get_trigger_kwargs=lambda c: {
        "hour": parse_checkin_time(c.new_task_time)[0],
        "minute": parse_checkin_time(c.new_task_time)[1],
    }
)
```

2. **在 `src/jobs/registry.py` 中添加模块路径**
```python
TASK_MODULES = [
    "src.tasks.log_cleanup",
    "src.tasks.new_task",  # 新增
]
```

3. **在配置文件中添加配置项**
```yaml
new_task:
  enable: true
  time: "08:00"
```

### 添加新推送通道

**步骤**：

1. **创建推送通道类**（`src/push_channel/new_channel.py`）
```python
from ._push_channel import PushChannel

class NewChannel(PushChannel):
    def __init__(self, config: dict, session):
        super().__init__(config, session)
        # 初始化配置
    
    async def push(self, title, content, jump_url, pic_url, extend_data):
        # 推送逻辑
        pass
```

2. **在 `__init__.py` 中注册**
```python
from .new_channel import NewChannel

_channel_type_to_class = {
    "new_channel": NewChannel,
    # ...
}
```

---

## 技术栈 {#tech-stack}

### 核心依赖

| 库名 | 版本 | 用途 |
|------|------|------|
| Python | >=3.10 | 编程语言 |
| aiohttp | >=3.9.0 | 异步HTTP客户端 |
| aiosqlite | >=0.19.0 | 异步SQLite数据库 |
| APScheduler | >=3.10.0 | 任务调度器 |
| Pydantic | >=2.5.0 | 数据验证和配置模型 |
| FastAPI | >=0.104.0 | Web框架 |
| Uvicorn | >=0.24.0 | ASGI服务器 |
| PyYAML | >=6.0.0 | YAML解析 |
| ruamel.yaml | >=0.18.0 | YAML编辑（保留注释） |

### 架构模式

- **异步IO**：全面使用 `asyncio` 和 `async/await`
- **插件化架构**：监控和任务采用插件化设计
- **依赖注入**：通过构造函数注入配置和会话
- **工厂模式**：推送通道通过工厂函数创建
- **单例模式**：数据库连接、Cookie缓存采用单例
- **观察者模式**：配置监控器观察配置文件变化

---

## 目录结构 {#directory-structure}

```
WebMoniter/
├── main.py                 # 主入口（生命周期编排，细节见 src/jobs/lifecycle.py）
├── config.yml              # 配置文件（用户在仓库根创建）
├── config/
│   └── config.yml.sample   # 配置模板（复制到根目录 config.yml）
├── docker/
│   ├── Dockerfile          # 精简镜像（构建：`docker build -f docker/Dockerfile .`）
│   ├── Dockerfile.full     # 完整镜像（iKuuu/雨云/Chromium）
│   ├── docker-compose.yml
│   ├── docker-compose.full.yml
│   ├── docker-entrypoint.sh
│   └── README.md           # Compose 与构建说明
├── pyproject.toml          # 项目配置和依赖
├── uv.lock                 # 依赖锁定文件
│
├── src/                    # 核心源代码
│   ├── core/               # 运行时、路径、版本、HTTP 工具
│   │   ├── runtime.py      # asyncio 运行与 Ctrl+C 退出兜底（12 秒 watchdog）
│   │   ├── paths.py        # 配置/数据/日志路径常量
│   │   ├── version.py      # 版本号与 GitHub API 地址
│   │   ├── utils.py
│   │   └── http.py
│   ├── settings/           # 配置加载、映射、热重载、DB 同步
│   │   ├── config.py       # AppConfig 与 get_config()
│   │   ├── loader_specs.py # YAML → AppConfig 映射规格
│   │   ├── watcher.py      # ConfigWatcher（默认 5 秒轮询）
│   │   └── db_sync.py      # 热重载时删除已移除的 uid/room 记录
│   ├── jobs/               # 调度、注册、日志、生命周期
│   │   ├── scheduler.py    # APScheduler 封装
│   │   ├── registry.py     # MONITOR_MODULES / TASK_MODULES、register_* 
│   │   ├── lifecycle.py    # Web/调度启动编排与热重载回调
│   │   ├── log_manager.py  # 按日轮转与任务专属日志
│   │   ├── tracker.py      # task_run_history 读写 API 再导出
│   │   └── enable_fields.py # 任务启用开关映射（registry + 青龙 compat 共用）
│   ├── storage/            # 持久化
│   │   ├── database.py     # AsyncDatabase（SQLite WAL）
│   │   └── cookie_cache.py # Cookie 过期状态缓存
│   ├── monitors/           # 平台监控（interval 触发）
│   │   ├── base.py
│   │   ├── huya_monitor.py
│   │   ├── weibo_monitor.py
│   │   ├── bilibili_monitor.py
│   │   ├── douyin_monitor.py
│   │   ├── douyu_monitor.py
│   │   └── xhs_monitor.py
│   ├── tasks/              # 定时/签到任务（Cron 触发）
│   │   ├── log_cleanup.py
│   │   ├── ikuuu_checkin.py
│   │   ├── rainyun_checkin.py
│   │   ├── rainyun/        # 雨云子包（浏览器、验证码、续费等）
│   │   ├── demo_task.py    # 二次开发示例
│   │   └── ...             # 其余签到任务见 src/jobs/registry.py TASK_MODULES
│   ├── push_channel/       # 推送通道（18 种 type，含 demo、qlapi）
│   │   ├── _push_channel.py
│   │   ├── manager.py
│   │   └── ...             # wecom_apps、dingtalk_bot、telegram_bot 等
│   ├── web/                # FastAPI 应用与 API
│   │   ├── app.py
│   │   ├── auth.py
│   │   ├── config_io.py
│   │   ├── data_support.py
│   │   └── routers/        # pages、auth、tasks、config、data、logs
│   ├── webUI/              # 前端静态资源与 Jinja2 模板
│   │   ├── static/         # css、js、截图等
│   │   └── templates/      # login、config、tasks、data、logs（dashboard.html 暂无路由）
│   ├── ql/                 # 青龙 CLI 与环境变量兼容
│   │   ├── __main__.py     # python -m src.ql <task_id>
│   │   ├── _runner.py      # run_task() 执行封装
│   │   └── compat.py       # WEBMONITER_* 环境变量 → 配置
│   └── tests/              # 单元与 smoke 测试（pytest，见 pyproject.toml）
│
├── docs/                   # 文档（MkDocs 源目录，配置见 docs/mkdocs.yml）
│   ├── mkdocs.yml
│   ├── index.md、API.md、ARCHITECTURE.md、SECONDARY_DEVELOPMENT.md
│   ├── installation.md、faq.md、QINGLONG.md
│   └── guides/             # config、tasks、web-ui、push-channels 等
│
├── data/                   # 运行时数据（gitignore）
│   ├── data.db             # SQLite（监控数据 + task_run_history）
│   ├── cookie_cache.json
│   └── auth.json           # Web 登录凭据
│
└── logs/                   # 运行时日志（gitignore）
    ├── main_YYYYMMDD.log
    └── task_{job_id}_YYYYMMDD.log
```

---

## 关键设计模式 {#design-patterns}

### 1. 插件化架构

**实现**：通过 `src.jobs.registry` 模块（`discover_and_import()`、`MONITOR_MODULES`、`TASK_MODULES`）实现任务的自动发现和注册。**青龙面板** 下通过 `python -m src.ql <task_id>` CLI + 环境变量 + `src.ql.compat` 模块实现兼容，与主流程解耦。

**优势**：
- 新增任务只需添加模块路径，无需修改核心代码
- 任务模块独立，易于维护和测试
- 支持动态加载和卸载任务

### 2. 工厂模式

**实现**：推送通道通过 `get_push_channel()` 工厂函数创建

**优势**：
- 统一创建接口，隐藏具体实现
- 易于扩展新的推送通道
- 支持配置驱动的通道选择

### 3. 单例模式

**实现**：
- 数据库连接：全局 `_shared_connection`
- Cookie缓存：全局 `cookie_cache` 实例

**优势**：
- 避免资源浪费（连接复用）
- 保证状态一致性

### 4. 观察者模式

**实现**：`ConfigWatcher` 观察配置文件变化

**优势**：
- 解耦配置变化和业务逻辑
- 支持配置热重载
- 易于扩展配置变化处理

### 5. 模板方法模式

**实现**：`BaseMonitor` 定义监控流程模板

**优势**：
- 统一监控任务的结构
- 子类只需实现具体逻辑
- 减少代码重复

---

## 配置管理 {#config-management}

### 配置文件结构

配置文件采用YAML格式，支持嵌套结构和注释：

```yaml
# 监控配置（示例：微博、虎牙，各任务可配置 monitor_interval_seconds 与 push_channels）
weibo:
  enable: true   # 是否启用，默认 true；设为 false 时任务暂停
  cookie: "xxx"
  uids: "123,456"
  concurrency: 3
  monitor_interval_seconds: 300

huya:
  enable: true
  rooms: "123,456"
  concurrency: 7
  monitor_interval_seconds: 65

# 推送通道配置（每个任务可通过 push_channels 字段选择使用哪些通道）
push_channel:
  - name: "企业微信"
    type: wecom_apps
    # ...
```

### 配置加载流程

1. **读取YAML文件**：`load_config_from_yml()`
2. **扁平化转换**：按 `src/settings/loader_specs.py` 的 `CONFIG_MAPPINGS` 将嵌套结构转为扁平字段
3. **列表规格解析**：按 `MULTI_ACCOUNT_SPECS` / `MULTI_STRING_SPECS` 解析多账号、多 Cookie/Token
4. **Pydantic验证**：创建 `AppConfig` 实例
5. **缓存配置**：避免重复读取

### 配置热重载

- **检测机制**：`ConfigWatcher` 每5秒检查文件修改时间
- **变化检测**：利用 Pydantic `model_dump()` 完整对比所有字段，新增字段自动覆盖，无需手动维护比较列表
- **更新机制**：更新调度器任务参数（间隔任务间隔、Cron 执行时间、暂停/恢复）
- **生效时间**：约5秒内生效

---

## 数据库设计 {#database-design}

### 数据库选择

- **SQLite**：轻量级、无需单独服务、适合单机部署
- **WAL模式**：提高并发性能
- **异步操作**：使用 `aiosqlite` 支持异步IO

### 表结构

**weibo表**：
- `UID`：用户ID（主键）
- `用户名`：用户昵称
- `认证信息`：认证标识
- `简介`：用户简介
- `粉丝数`：粉丝数量
- `微博数`：微博数量
- `文本`：最新微博内容
- `mid`：微博ID

**huya表**：
- `room`：房间号（主键）
- `name`：主播名称
- `is_live`：直播状态（"1"=直播中，"0"=未开播）
- `room_pic`、`avatar_url`：封面与头像 URL（旧库通过 ALTER TABLE 迁移追加，可选）

**bilibili_dynamic表**（B 站动态）：
- `uid`：UP 主 UID（主键）
- `uname`：UP 主昵称
- `dynamic_id`：最近一条动态 ID
- `dynamic_text`：最近一条动态的文本内容

**bilibili_live表**（B 站直播）：
- `uid`：UP 主 UID（主键）
- `uname`：UP 主昵称
- `room_id`：直播间房间号
- `is_live`：直播状态

**douyin表**：
- `douyin_id`：抖音号（主键）
- `name`：用户名
- `is_live`：直播状态

**douyu表**：
- `room`：房间号（主键）
- `name`：主播名称
- `is_live`：直播状态

**xhs表**（小红书）：
- `profile_id`：用户 profile_id（主键）
- `user_name`：用户名
- `latest_note_title`：最近一条笔记标题

**task_run_history表**（定时任务运行记录）：
- `job_id`：任务ID（主键）
- `last_run_date`：最后运行日期（ISO格式，如 "2025-02-04"）

> 该表在 `src/storage/database.py` 的 `_init_tables()` 中创建；读写 API 由同模块提供，`src/jobs/tracker.py` 对其再导出。用于实现"当天已运行则跳过"功能。任务包装函数在 `run_func` 正常返回后写入记录；若抛出未捕获异常则不写入，允许后续重试。Web「立即运行」使用 `original_run_func`，不经过此检查。

### 连接管理

- **共享连接**：多个 `AsyncDatabase` 实例共享同一连接
- **引用计数**：跟踪连接使用情况
- **健康检查**：自动检测连接失效
- **自动重连**：连接失效时自动重建

---

## 推送通道架构 {#push-architecture}

### 统一推送接口

所有推送通道实现统一的 `PushChannel` 接口：

```python
class PushChannel(ABC):
    async def push(self, title, content, jump_url, pic_url, extend_data):
        """推送消息"""
        pass
```

### 推送管理器

`UnifiedPushManager` 管理多个推送通道：

- **并发推送**：同时发送到所有启用的通道
- **错误处理**：单个通道失败不影响其他通道
- **通道过滤**：只发送到 `enable=true` 的通道

### 推送流程

1. 构建推送消息（标题、内容、链接、图片）
2. 检查免打扰时段
3. 并发发送到所有启用的通道
4. 收集推送结果和错误
5. 记录日志

---

## Web服务架构 {#web-architecture}

### 技术栈

- **FastAPI**：现代、快速的Web框架
- **Jinja2**：模板引擎
- **Uvicorn**：ASGI服务器

### 路由设计

- **页面路由**：返回 HTML 页面（配置、任务管理、数据、日志）
- **API路由**：返回 JSON 数据（配置、任务、数据、日志、监控状态、版本信息）

### 认证机制

- **Session认证**：基于 `SessionMiddleware`
- **登录验证**：用户名密码验证（默认 `admin/123`）
- **会话管理**：`active_sessions` 集合管理活跃会话

### API设计

- **RESTful风格**：资源导向的URL设计
- **统一响应格式**：JSON格式响应
- **错误处理**：HTTP状态码 + 错误消息

---

## 总结

Web任务系统采用**模块化、插件化、异步IO**的架构设计，具有以下特点：

1. **高可扩展性**：新增监控或任务只需添加模块，无需修改核心代码
2. **配置热重载**：修改配置无需重启，5秒内自动生效
3. **异步高性能**：全面使用异步IO，支持高并发
4. **统一推送**：支持 15+ 种推送通道，统一管理
5. **Web管理**：提供友好的Web界面进行配置和数据管理

该架构设计使得系统易于维护、扩展和部署，适合个人和小团队使用。
