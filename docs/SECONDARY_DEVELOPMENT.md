# 二次开发指南：新增监控任务与定时任务

本页说明当前扩展契约。模块边界和存储恢复原理见 [架构文档](ARCHITECTURE.md)，使用参数见 [配置说明](guides/config.md)、[任务指南](guides/tasks.md) 和 [推送通道](guides/push-channels.md)。

<a id="development-checks"></a>
## 开发环境与关键检查

在仓库根目录使用 Python 3.11：

```bash
uv python install 3.11
uv venv --python 3.11
uv sync --locked --extra dev --extra rainyun
uv run ruff check .
uv run pytest -q
npm ci --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
npm exec --prefix frontend -- playwright install chromium
npm run test:e2e --prefix frontend
```

浏览器任务需要 `rainyun` 可选依赖及本地 Chrome/Chromium、chromedriver；安装和预检见 [安装与运行](installation.md)。Node 24 用于 Vue 前端构建与测试，Python 服务提供静态产物，不运行 Node 服务。

Black 检查本轮修改的 Python 文件，例如 `uv run black --check src/web/routers/data.py`；需要格式化时对同一文件去掉 `--check`。前端修改用 `npm run format:check --prefix frontend` 和生产构建验证。文档检查为：

```bash
uv sync --locked --extra dev --extra rainyun --extra docs
uv run mkdocs build --strict --config-file docs/mkdocs.yml
```

Python 测试在收集前将配置、数据库、Cookie、会话和默认日志隔离到临时目录。注册完整性检查只对明确缺失的可选包允许跳过，其他导入错误应失败。前端使用 Vitest 与 Playwright，后者连接隔离的临时后端，不调用真实平台。Linux 缺少浏览器系统库时使用 `npm exec --prefix frontend -- playwright install --with-deps chromium`。

生产构建已包含 TypeScript 检查与 250 KiB gzip 资源预算，无需再单独重复类型检查；只改类型时可先执行 `npm run typecheck --prefix frontend`。Playwright 使用一个 worker，桌面覆盖关键功能，移动端只重复导航、图片操作、外观偏好与保存按钮可用性。截图留作人工观察，不比较像素基线；平板、极窄屏、字体和弱网性能改由人工验收。

只为结果、边界和一致性增加必要测试。配置合并、鉴权、调度结果、数据库恢复、监控去重、推送格式及请求竞态属于关键回归；颜色、CSS 字符串、固定资源版本、文案措辞和视觉细节不做源码断言。实际图片、触屏、主题和滚动检查见 [Web 自测清单](guides/web-ui.md#manual-checks)。

## 定时任务

### 配置、业务与注册

1. 在示例配置中定义参数。顶层配置同时补充 `AppConfig` 和 `src/settings/loader_specs.py` 的字段映射；多账号及 Cookie/Token 列表使用已有规格。`plugins` 配置可参考 `demo_task`，无需为每个插件参数新增扁平字段。
2. 在 `src/tasks/` 实现异步业务入口和触发参数函数。任务内读取最新配置，校验启用状态及必填项；真正完成返回 `TASK_SUCCESS`，失败、未启用或未执行返回 `TASK_FAILED`。不要用无返回值代表定时任务成功。
3. 在模块末尾调用 `register_task()`，并在 `TASK_SPECS` 登记同一任务 ID、模块路径、描述及配置字段。

当前 Demo 的核心契约如下；完整业务、资源释放和推送代码以 `src/tasks/demo_task.py` 为准：

```python
from src.jobs.task_outcome import TASK_FAILED, TASK_SUCCESS
from src.settings.config import get_config, parse_checkin_time

async def run_demo_task_once() -> bool:
    config = get_config(reload=True)
    plug = config.plugins.get("demo_task") or {}
    if not plug.get("enable", False):
        return TASK_FAILED
    # 完成实际业务；失败路径返回 TASK_FAILED。
    return TASK_SUCCESS

def _get_demo_task_trigger_kwargs(config) -> dict:
    plug = config.plugins.get("demo_task") or {}
    hour, minute = parse_checkin_time((plug.get("time") or "08:00").strip())
    return {"hour": hour, "minute": minute}
```

模块注册使用 `register_task("demo_task", run_demo_task_once, _get_demo_task_trigger_kwargs, description="二次开发示例任务")`。

| 注册选项 | 默认值与行为 |
|---|---|
| `skip_if_run_today` | `True`：跳过当天已有成功记录的任务；仅业务返回 `TASK_SUCCESS` 时写入成功记录 |
| `run_on_startup` | `True`：参与启动首轮；设为 `False` 后仅按触发器执行 |
| `description` | Web 展示文案，与元数据保持一致 |

Web「立即运行」使用 `original_run_func`，绕过当天跳过检查；业务内部的禁用或缺参校验仍有效。提交返回 `202 + run_id`，结果由执行记录查询；`False` 为失败，`TASK_PARTIAL` 为部分成功，禁用任务为跳过。手动执行经过统一队列，不经过每日记录包装层。

### 元数据与配置映射

`TaskSpec` 位于 `src/jobs/metadata.py`。维护以下字段即可由元数据生成发现名单和兼容映射：

| 字段 | 用途 |
|---|---|
| `job_id`、`module`、`description`、`kind`、`config_section` | 注册身份、导入路径和界面展示；`kind` 为 `monitor` 或 `task` |
| `enable_field` | `AppConfig` 中的启用字段；有字段时需保证映射存在 |
| `time_field`、`default_time` | Cron 任务的时间字段及默认值 |
| `interval_field` | 监控间隔字段 |
| `push_field` | 通道名称列表字段，同时用于配置页通道控件关联 |
| `ql_prefix`、`ql_extra_env` | 青龙环境变量映射 |
| `plugin_only` | 插件配置任务标记，如 Demo |

不要手动再维护 `MONITOR_MODULES`、`TASK_MODULES` 或 enable 映射。新增配置字段通过模型比较参与热重载，无需添加第二份字段比较清单。

### 真实示例

| 示例 | 源码入口与重点 |
|---|---|
| Demo | `src/tasks/demo_task.py`：插件配置、布尔结果、Cron 和统一推送 |
| iKuuu | `src/tasks/ikuuu_checkin.py`：`run_checkin_once()`、多账号、浏览器登录；域名入口为 `_extract_ikuuu_domain_with_retry()` |
| Freenom | `src/tasks/freenom_checkin.py`：多账号续期任务 |
| 天气 | `src/tasks/weather_push.py`：配置映射及消息构造 |
| 微博 Cookie 刷新 | `src/tasks/weibo_cookie_refresh.py`：浏览器执行、字段冲突检查和配置写回 |

示例中的平台流程会随网站变化，不在本文复制整段登录、签到或验证码实现。

## 监控任务

1. 在配置、`AppConfig` 和映射中增加目标列表、启用状态、间隔及通道字段。
2. 继承 `BaseMonitor`，实现 `run()`、`monitor_name`、`platform_name`，需要筛选通道时实现 `push_channel_names`。
3. 在入口中初始化监控器，并在 `finally` 中关闭资源；参考 `src/monitors/huya_monitor.py`。基类提供 `self.config`、HTTP 会话、`self.db`、`self.push` 和 Cookie 失效通知，未配置推送时可通过 `send_push_news()` 安全跳过。
4. 实现当前状态与旧快照的对比、首次运行和去重规则；保持有界并发，不在异步函数中直接执行浏览器或阻塞请求。
5. 调用 `register_monitor()`，在 `MONITOR_SPECS` 登记对应 `TaskSpec`；触发参数函数返回 `{"seconds": ...}`。
6. 若目标删除需同步清理存储，维护 `src/settings/db_sync.py` 的规则；若需 Web 数据展示，维护 `src/web/data_support.py` 的平台 SQL、主键和行转换，并更新 `frontend/src/views/Data.vue` 的平台展示。

监控入口允许返回 `None`，与必须返回布尔结果的定时任务区分。

## 持久化与兼容迁移

`BaseMonitor.initialize()` 初始化数据库与推送。业务使用 `AsyncDatabase`，不自行切换 MySQL/SQLite，也不绕过镜像和离线队列直接写底层连接。

| 方法 | 契约 |
|---|---|
| `execute_query(sql, params=None)` | 返回 `list[tuple]` |
| `execute_update(sql, params=None)` | 执行 INSERT/UPDATE/DELETE；SQL 操作失败记录日志并返回 `False`，调用方必须检查结果；连接初始化失败和任务取消仍可能向上传播 |
| `execute_insert(sql, params=None)` | 插入的语义入口，返回 `bool` |
| `is_table_empty(table_name)` | 返回表是否为空 |

参数使用字典及命名占位符，如 `%(room)s` 或 `:room`；现有转换处理两个后端及 `INSERT OR REPLACE`。条件更新/删除参数必须携带实际主键或通用 `pk`。离线回放只支持注册表和可还原到主键的操作，不能依赖任意批量条件 SQL 自动重放。

新增表需同时维护 SQLite `_init_tables()` 和 MySQL `TABLE_SPECS`，保证主键和字段顺序一致。已有表增字段还需同步两种后端的增量迁移及 `MYSQL_COLUMN_MIGRATIONS`。至少验证旧 SQLite、旧 MySQL、新安装、断线写入和恢复回放；权威数据关系见 [数据库设计](ARCHITECTURE.md#database-design)。

## 推送与任务日志

- 从 `config.push_channel_list` 创建 `build_push_manager()`；`channel_names` 非空时按名称筛选，空或 `None` 使用所有已配置通道。无有效通道时返回 `None`。
- 调用 `send_news(title=..., description=..., to_url=..., picurl=..., btntxt=...)`；推送前由业务判断 `is_in_quiet_hours(config)`，免打扰不应使已完成业务被误报为失败。
- 富文本使用 `RichTextBuilder`，由通道管理器渲染和限制 UTF-8 字节长度；不要自己拼接不安全链接。
- 通道管理器在 HTTP 会话生命周期内关闭，监控由基类收尾；初始化和单通道失败不阻断其他通道。
- 新增通道需实现 `PushChannel`，加入 `src/push_channel/__init__.py` 工厂和 `PUSH_CHANNEL_SPECS`，并补充必要的参数说明。

注册包装器及 Web 手动执行会挂载任务日志，文件名为 `task_{job_id}_YYYYMMDD.log`，通过 ContextVar 过滤并发任务的日志。直接绕开这些入口执行函数时，不会自动获得这一层日志包装。

## Web 配置与静态资源

YAML 文本视图可编辑完整配置；表单保存由后端合并，分区保存仅提交该分区字段。完整 YAML 仍是整份替换，推送通道列表和空账号列表的语义见 [配置 API](API.md)。

配置页位于 `frontend/src/views/Config.vue`，从 `/api/v1/config/metadata` 合并样例默认值，并通过 `components/FieldEditor.vue` 渲染字段、数组与嵌套对象。新增字段优先维护配置模型、样例和元数据映射；只有现有通用控件无法表达时才扩展组件。完整 YAML 编辑保留为高级入口。

Vue/CSS 修改后运行前端构建；Vite 自动生成带内容哈希的 `/assets/` 文件，首页使用 `no-cache`，无需手动递增版本。`src/web/static_files.py` 的版本仅用于保留的 `/static/` 资源。`src/webUI/` 不再包含 Jinja 模板或配置脚本。

## 青龙 CLI

```bash
python -m src.ql --list
python -m src.ql demo_task
```

CLI 通过任务元数据和注册表复用业务函数，配置来自 `WEBMONITER_*` 环境变量，使用 `qlapi` 通道发送系统通知；不会启动 Web 或常驻调度器。只有声明对应 `ql_prefix` 的任务会出现在 CLI 清单。新增支持时在同一 `TaskSpec` 维护环境变量映射，操作说明见 [青龙兼容指南](QINGLONG.md)。
