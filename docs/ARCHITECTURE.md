# Web任务系统 项目架构文档

## 📋 目录

- [项目概述](#项目概述)
- [整体架构](#整体架构)
- [核心模块详解](#核心模块详解)
- [数据流设计](#数据流设计)
- [扩展机制](#扩展机制)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [关键设计模式](#关键设计模式)
- [配置管理](#配置管理)
- [数据库设计](#数据库设计)
- [推送通道架构](#推送通道架构)
- [Web服务架构](#web服务架构)

---

## 项目概述

Web任务系统（项目代号 WebMoniter）是一个基于 Python 的**多平台任务系统**，采用异步IO架构，支持：

- **多平台监控**：虎牙直播、微博等平台的实时监控
- **定时任务**：iKuuu签到、百度贴吧签到、微博超话签到等
- **多渠道推送**：支持10+种推送通道（企业微信、钉钉、Telegram、Bark等）
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

## 整体架构

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
   - 加载配置文件 (`config.yml`)
   - 初始化日志系统 (`LogManager`)
   - 创建数据库连接 (`AsyncDatabase`)
   - 初始化Cookie缓存 (`CookieCache`)

2. **任务注册阶段**
   - 通过 `job_registry.discover_and_import()` 按 `MONITOR_MODULES`、`TASK_MODULES` 导入任务模块
   - 各模块调用 `register_monitor()` 或 `register_task()` 注册任务
   - 任务描述符 (`JobDescriptor`) 被添加到 `MONITOR_JOBS` 或 `TASK_JOBS`

3. **调度器启动阶段**
   - 创建 `TaskScheduler` 实例（基于 `APScheduler`）
   - 遍历 `MONITOR_JOBS` 和 `TASK_JOBS`，注册到调度器
   - 启动时立即执行一次所有任务（首次运行）

4. **Web服务启动阶段**
   - 创建 FastAPI 应用实例
   - 启动 Uvicorn 服务器（端口8866）
   - 提供Web界面和API接口

5. **配置监控启动阶段**
   - 启动 `ConfigWatcher`，每5秒检查配置文件变化
   - 检测到变化时触发回调，更新调度器中的任务参数

6. **运行阶段**
   - 调度器按配置的间隔/时间执行任务
   - 监控任务检测变化并推送通知
   - 定时任务按Cron表达式执行
   - Web服务处理HTTP请求

---

## 核心模块详解

### 1. main.py - 主入口模块

**职责**：系统启动和生命周期管理

**关键功能**：
- 初始化日志系统（控制台 + 文件）
- 创建并启动Web服务器（FastAPI + Uvicorn）
- 加载配置并创建调度器
- 注册所有监控和定时任务
- 启动配置监控器（热重载）
- 处理优雅关闭（信号处理）

**关键代码流程**：
```python
async def main():
    # 1. 设置日志
    setup_logging()
    
    # 2. 创建Web应用
    web_app = create_web_app()
    server = uvicorn.Server(...)
    
    # 3. 加载配置
    config = get_config()
    
    # 4. 创建调度器
    scheduler = TaskScheduler(config)
    
    # 5. 注册任务
    await register_monitors(scheduler)
    
    # 6. 启动配置监控
    config_watcher = ConfigWatcher(...)
    await config_watcher.start()
    
    # 7. 运行调度器
    await scheduler.run_forever()
```

---

### 2. src/config.py - 配置管理模块

**职责**：配置文件的加载、解析和验证

**核心类**：
- `AppConfig`：配置数据模型（基于 Pydantic）
- `WeiboConfig`：微博配置子模型
- `HuyaConfig`：虎牙配置子模型

**关键功能**：
- 从YAML文件加载配置
- 配置缓存机制（避免重复读取）
- 配置验证（Pydantic模型验证）
- 扁平化配置映射（YAML嵌套 → 扁平字段）

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
2. 将嵌套结构转换为扁平结构
3. 创建 `AppConfig` 实例（Pydantic验证）
4. 缓存配置实例（`_config_cache`）

---

### 3. src/monitor.py - 监控基类

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
        """平台名称（用于Cookie缓存）"""
        pass
```

**子类实现示例**：
- `HuyaMonitor`：虎牙直播监控
- `WeiboMonitor`：微博监控

---

### 4. src/scheduler.py - 任务调度器

**职责**：基于APScheduler的任务调度管理

**核心类**：
- `TaskScheduler`：任务调度器封装
- `TaskGroupFormatter`：日志格式化器（任务组分隔）

**关键功能**：
- 添加间隔任务（`add_interval_job`）
- 添加Cron任务（`add_cron_job`）
- 更新任务参数（热重载支持）
- 优雅关闭（信号处理）

**任务类型**：
- **间隔任务**：使用 `IntervalTrigger`，按固定间隔执行
  - 示例：虎牙监控每60秒执行一次
- **Cron任务**：使用 `CronTrigger`，按时间表达式执行
  - 示例：每天08:00执行签到任务

**热重载支持**：
- `update_interval_job()`：更新间隔任务的间隔时间
- `update_cron_job()`：更新Cron任务的执行时间

---

### 5. src/database.py - 数据库模块

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

### 6. src/job_registry.py - 任务注册表

**职责**：统一管理监控和定时任务的注册

**核心概念**：
- `JobDescriptor`：任务描述符（任务ID、执行函数、触发器配置）
- `MONITOR_MODULES`：监控模块列表
- `TASK_MODULES`：定时任务模块列表
- `MONITOR_JOBS`：已注册的监控任务列表
- `TASK_JOBS`：已注册的定时任务列表

**注册流程**：
1. 在 `MONITOR_MODULES` 或 `TASK_MODULES` 中添加模块路径
2. `discover_and_import()` 自动导入模块
3. 模块加载时调用 `register_monitor()` 或 `register_task()`
4. 任务描述符被添加到对应列表

**扩展新任务**：
```python
# 1. 在 monitors/ 或 tasks/ 下创建模块
# 2. 在 job_registry.py 中添加模块路径
MONITOR_MODULES = [
    "monitors.huya_monitor",
    "monitors.weibo_monitor",
    "monitors.new_monitor",  # 新增
]

# 3. 在模块中注册任务
from src.job_registry import register_monitor

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

### 7. src/config_watcher.py - 配置监控器

**职责**：监控配置文件变化并触发热重载

**核心类**：
- `ConfigWatcher`：配置文件监控器

**关键功能**：
- 定期检查配置文件修改时间（默认5秒）
- 检测到变化时重新加载配置
- 比较配置内容变化（避免无效重载）
- 触发回调函数更新调度器任务参数

**热重载流程**：
1. `ConfigWatcher` 每5秒检查 `config.yml` 的修改时间
2. 检测到文件修改时，调用 `get_config(reload=True)` 重新加载
3. 比较新旧配置，检测实际变化
4. 调用 `on_config_changed()` 回调
5. 回调函数更新调度器中的任务参数

**配置变化检测**：
- 比较关键配置字段（监控间隔、推送通道、免打扰时段等）
- 支持嵌套配置比较（多账号、多Cookie等）
- 避免因文件保存但内容未变而触发重载

---

### 8. src/cookie_cache.py - Cookie缓存管理

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

### 9. src/push_channel/ - 推送通道模块

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

### 10. src/web_server.py - Web服务器

**职责**：提供Web管理界面和API接口

**技术栈**：
- FastAPI：Web框架
- Jinja2：模板引擎
- Uvicorn：ASGI服务器

**主要功能**：
- **配置管理**：在线编辑 `config.yml`（保留注释）
- **数据查看**：查看监控数据（分页、过滤）
- **日志查看**：查看系统日志
- **API接口**：RESTful API供外部调用

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
- `GET /api/logs`：获取日志内容
- `GET /api/monitor-status/{platform}`：获取监控状态（无需登录）
- `GET /api/version`：获取版本信息（无需登录，用于前端检测新版本）

**配置保存特性**：
- 使用 `ruamel.yaml` 保留YAML注释
- 配置验证（加载测试）
- 保存后自动触发热重载

---

### 11. src/log_manager.py - 日志管理

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
  main_20250130.log
  main_20250129.log
  main_20250128.log
  cleanup_20250130.log
```

**日志清理**：
- 定时任务每天执行一次（默认02:00）
- 删除超过 `retention_days` 天的日志文件
- 从文件名提取日期或使用文件修改时间

---

### 12. src/version.py - 版本信息模块

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
from src.version import (
    __version__,          # 当前版本号，如 "2.0.0"
    GITHUB_RELEASES_URL,  # GitHub Tags 页面 URL
    GITHUB_API_LATEST_TAG # GitHub API 获取最新 tag 的 URL
)
```

**前端版本检测流程**：
1. 前端调用 `GET /api/version` 获取当前版本和 GitHub API 地址
2. 前端调用 GitHub Tags API 获取最新 tag 的 `name`
3. 比较版本号，若有新版本则显示更新提示横幅
4. 用户可点击跳转至 GitHub Tags 页面查看更新内容

---

## 数据流设计

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
   - 更新 task_run_history 表
   - 仅在任务成功时标记
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
   - 检测关键字段变化
   - 检测嵌套配置变化
   ↓
4. 更新调度器
   - 更新间隔任务的间隔时间
   - 更新Cron任务的执行时间
   - 更新免打扰时段配置
   ↓
5. 记录日志
```

---

## 扩展机制

### 添加新监控平台

**步骤**：

1. **创建监控模块**（`monitors/new_platform_monitor.py`）
```python
from src.monitor import BaseMonitor, CookieExpiredError
from src.config import get_config

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
from src.job_registry import register_monitor

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

2. **在 `job_registry.py` 中添加模块路径**
```python
MONITOR_MODULES = [
    "monitors.huya_monitor",
    "monitors.weibo_monitor",
    "monitors.new_platform_monitor",  # 新增
]
```

3. **在 `config.py` 中添加配置字段**
```python
class AppConfig(BaseModel):
    new_platform_interval_seconds: int = 300
    # 其他配置...
```

4. **在 `config.py` 中添加配置映射**
```python
config_mappings = {
    "new_platform": {
        "interval_seconds": "new_platform_interval_seconds",
    },
    # ...
}
```

### 添加新定时任务

**步骤**：

1. **创建任务模块**（`tasks/new_task.py`）
```python
from src.job_registry import register_task
from src.config import get_config, parse_checkin_time

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

2. **在 `job_registry.py` 中添加模块路径**
```python
TASK_MODULES = [
    "tasks.log_cleanup",
    "tasks.new_task",  # 新增
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

## 技术栈

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

## 目录结构

```
WebMoniter/
├── main.py                 # 主入口
├── config.yml              # 配置文件（用户创建）
├── config.yml.sample        # 配置示例文件
├── pyproject.toml          # 项目配置和依赖
├── uv.lock                 # 依赖锁定文件
├── Dockerfile              # Docker镜像构建文件
├── docker-compose.yml      # Docker Compose配置
│
├── src/                    # 核心源代码
│   ├── __init__.py
│   ├── config.py           # 配置管理
│   ├── config_watcher.py   # 配置监控（热重载）
│   ├── cookie_cache.py    # Cookie缓存管理
│   ├── database.py         # 数据库操作
│   ├── job_registry.py     # 任务注册表
│   ├── ql_compat.py        # 青龙面板兼容（环境变量配置、QLAPI）
│   ├── log_manager.py      # 日志管理
│   ├── monitor.py          # 监控基类
│   ├── scheduler.py        # 任务调度器
│   ├── task_tracker.py     # 任务运行追踪（当天已运行则跳过）
│   ├── utils.py            # 工具函数
│   ├── version.py          # 版本信息管理
│   ├── web_server.py       # Web服务器
│   │
│   └── push_channel/       # 推送通道模块
│       ├── __init__.py
│       ├── _push_channel.py # 推送通道基类
│       ├── manager.py      # 统一推送管理器
│       ├── wecom_apps.py   # 企业微信自建应用
│       ├── wecom_bot.py    # 企业微信群聊机器人
│       ├── dingtalk_bot.py # 钉钉机器人
│       ├── feishu_apps.py  # 飞书自建应用
│       ├── feishu_bot.py   # 飞书机器人
│       ├── telegram_bot.py # Telegram机器人
│       ├── qq_bot.py       # QQ频道机器人
│       ├── napcat_qq.py    # NapCatQQ
│       ├── bark.py         # Bark
│       ├── gotify.py       # Gotify
│       ├── webhook.py      # Webhook
│       ├── email.py        # 电子邮件
│       ├── pushplus.py     # PushPlus
│       ├── wxpusher.py     # WxPusher
│       ├── server_chan_turbo.py  # Server酱Turbo
│       ├── server_chan_3.py     # Server酱3
│       └── qlapi.py             # 青龙 QLAPI 推送
│
├── ql/                     # 青龙单任务脚本（ql/*.py）
│
├── monitors/               # 监控模块
│   ├── __init__.py
│   ├── huya_monitor.py     # 虎牙直播监控
│   ├── weibo_monitor.py    # 微博监控
│   ├── bilibili_monitor.py # 哔哩哔哩动态+直播监控
│   ├── douyin_monitor.py   # 抖音直播监控
│   ├── douyu_monitor.py    # 斗鱼直播监控
│   └── xhs_monitor.py      # 小红书动态监控
│
├── tasks/                  # 定时任务模块
│   ├── __init__.py
│   ├── demo_task.py        # 示例任务
│   ├── log_cleanup.py      # 日志清理
│   ├── ikuuu_checkin.py    # iKuuu签到
│   ├── tieba_checkin.py    # 百度贴吧签到
│   ├── weibo_chaohua_checkin.py  # 微博超话签到
│   ├── rainyun_checkin.py       # 雨云签到
│   ├── enshan_checkin.py        # 恩山论坛签到
│   ├── fg_checkin.py            # 富贵论坛签到
│   ├── aliyun_checkin.py        # 阿里云盘签到
│   ├── smzdm_checkin.py         # 什么值得买签到
│   ├── zdm_draw.py              # 值得买每日抽奖
│   ├── tyyun_checkin.py         # 天翼云盘签到
│   ├── miui_checkin.py          # 小米社区签到
│   ├── iqiyi_checkin.py         # 爱奇艺签到
│   ├── lenovo_checkin.py        # 联想乐豆签到
│   ├── lbly_checkin.py          # 丽宝乐园签到
│   ├── pinzan_checkin.py        # 品赞签到
│   ├── dml_checkin.py           # 达美乐任务
│   ├── xiaomao_checkin.py       # 小茅预约（i茅台）
│   ├── ydwx_checkin.py          # 一点万象签到
│   ├── xingkong_checkin.py      # 星空代理签到
│   ├── freenom_checkin.py       # Freenom 免费域名续期
│   ├── weather_push.py          # 天气每日推送
│   ├── qtw_checkin.py           # 千图网签到
│   ├── kuake_checkin.py         # 夸克网盘签到
│   ├── kjwj_checkin.py          # 科技玩家签到
│   ├── fr_checkin.py            # 帆软社区签到 + 摇摇乐
│   ├── nine_nine_nine_task.py   # 999 会员中心健康打卡任务
│   ├── zgfc_draw.py             # 中国福彩抽奖活动
│   └── ssq_500w_notice.py       # 七星彩/双色球开奖通知
│
├── web/                    # Web前端资源
│   ├── static/             # 静态文件
│   │   ├── css/
│   │   └── js/
│   └── templates/          # Jinja2模板
│       ├── login.html
│       ├── dashboard.html  # 控制台首页
│       ├── config.html
│       ├── tasks.html      # 任务管理
│       ├── data.html
│       └── logs.html
│
├── docs/                   # 文档
│   ├── API.md              # API文档
│   ├── SECONDARY_DEVELOPMENT.md  # 二次开发指南
│   └── ARCHITECTURE.md     # 架构文档（本文档）
│
├── data/                   # 数据目录（运行时创建）
│   ├── data.db             # SQLite数据库
│   └── cookie_cache.json    # Cookie缓存
│
└── logs/                   # 日志目录（运行时创建）
    └── main_*.log          # 日志文件（按日期）
```

---

## 关键设计模式

### 1. 插件化架构

**实现**：通过 `job_registry` 模块（`discover_and_import()`、`MONITOR_MODULES`、`TASK_MODULES`）实现任务的自动发现和注册。**青龙面板** 下通过 `ql/*.py` 单任务脚本 + 环境变量 + `ql_compat` 模块实现兼容，与主流程解耦。

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

## 配置管理

### 配置文件结构

配置文件采用YAML格式，支持嵌套结构和注释：

```yaml
# 监控配置
weibo:
  enable: true   # 是否启用，默认 true；设为 false 时任务暂停
  cookie: "xxx"
  uids: "123,456"
  concurrency: 2

huya:
  enable: true
  rooms: "123,456"
  concurrency: 5

# 监控间隔配置（按任务配置）
huya:
  enable: true
  rooms: "123,456"
  concurrency: 5
  monitor_interval_seconds: 60

weibo:
  enable: true
  cookie: "xxx"
  uids: "123,456"
  concurrency: 2
  monitor_interval_seconds: 300

# 推送通道配置（每个任务可通过 push_channels 字段选择使用哪些通道）
push_channel:
  - name: "企业微信"
    type: wecom_apps
    # ...
```

### 配置加载流程

1. **读取YAML文件**：`load_config_from_yml()`
2. **扁平化转换**：嵌套结构 → 扁平字段
3. **Pydantic验证**：创建 `AppConfig` 实例
4. **缓存配置**：避免重复读取

### 配置热重载

- **检测机制**：`ConfigWatcher` 每5秒检查文件修改时间
- **变化检测**：比较关键配置字段
- **更新机制**：更新调度器任务参数
- **生效时间**：约5秒内生效

---

## 数据库设计

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

> 该表由 `src/task_tracker.py` 在首次使用时创建，用于实现"当天已运行则跳过"功能，避免定时任务在程序重启或定时触发时重复执行。

### 连接管理

- **共享连接**：多个 `AsyncDatabase` 实例共享同一连接
- **引用计数**：跟踪连接使用情况
- **健康检查**：自动检测连接失效
- **自动重连**：连接失效时自动重建

---

## 推送通道架构

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

## Web服务架构

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
4. **统一推送**：支持10+种推送通道，统一管理
5. **Web管理**：提供友好的Web界面进行配置和数据管理

该架构设计使得系统易于维护、扩展和部署，适合个人和小团队使用。