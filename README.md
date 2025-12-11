# Web监控系统

一个基于 Python 的异步 Web 监控系统，支持多平台监控任务（虎牙直播、微博等），使用 APScheduler 进行任务调度，支持企业微信推送和 MySQL 数据存储。

## 功能特性

- 🎯 **多平台监控**：支持虎牙直播、微博等平台监控
- ⏰ **任务调度**：基于 APScheduler 的灵活任务调度系统
- 📊 **数据存储**：MySQL 数据库存储监控数据
- 📱 **消息推送**：企业微信、PushPlus、邮件等多种推送方式
- 📝 **日志管理**：完善的日志记录和自动清理机制
- 🚀 **异步架构**：基于 asyncio 的高性能异步处理
- ⚙️ **配置管理**：基于YAML文件的配置管理，支持热重载

## 技术栈

- **Python**: >=3.10
- **异步框架**: asyncio, aiohttp
- **任务调度**: APScheduler
- **数据库**: MySQL (aiomysql)
- **配置管理**: pydantic, pyyaml
- **依赖管理**: uv

## 项目结构

```
WebMoniter/
├── main.py              # 主入口文件
├── pyproject.toml       # 项目配置和依赖
├── uv.lock              # 依赖锁定文件
├── src/                 # 核心模块
│   ├── config.py        # 配置管理
│   ├── database.py      # 数据库操作
│   ├── scheduler.py     # 任务调度器
│   ├── monitor.py       # 监控基类
│   ├── push.py          # 消息推送
│   └── log_manager.py   # 日志管理
├── monitors/            # 监控模块
│   ├── huya_monitor.py  # 虎牙直播监控
│   └── weibo_monitor.py # 微博监控
└── logs/                # 日志目录
```

## 安装与配置

### 1. 环境要求

- Python >= 3.10
- MySQL 数据库
- uv (Python 包管理器)

### 2. 安装依赖

使用 uv 安装项目依赖：

```bash
# 安装 uv (如果尚未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装项目依赖
uv sync
```

### 3. 配置文件设置

在项目根目录创建 `config.yml` 文件，复制示例配置文件并修改：

```bash
cp config.yml.sample config.yml
```

编辑 `config.yml` 文件，配置以下内容：

```yaml
# 企业微信配置
wechat:
  corpid: your_corpid
  secret: your_secret
  agentid: your_agentid
  touser: your_touser
  pushplus: null  # 可选
  email: null  # 可选

# 数据库配置
database:
  host: localhost
  port: 3306
  user: your_db_user
  password: your_db_password
  name: your_db_name

# 微博监控配置
weibo:
  cookie: your_weibo_cookie
  uids: uid1,uid2,uid3  # 逗号分隔的UID列表
  concurrency: 3  # 并发数，建议2-5

# 虎牙监控配置
huya:
  user_agent: your_user_agent
  cookie: your_huya_cookie  # 可选，没有可不填
  rooms: room1,room2,room3  # 逗号分隔的房间号列表
  concurrency: 7  # 并发数，建议5-10

# 调度器配置
scheduler:
  huya_monitor_interval_seconds: 65  # 虎牙监控间隔（秒），默认65秒
  weibo_monitor_interval_seconds: 300  # 微博监控间隔（秒），默认300秒（5分钟）
  cleanup_logs_hour: 2  # 日志清理时间（小时），默认2点
  cleanup_logs_minute: 0  # 日志清理时间（分钟），默认0分

# 可选配置
optional:
  config_json_url: null  # 可选：远程配置URL
```

**注意**：`config.yml` 文件不会被提交到 git，请妥善保管。

### 4. 数据库初始化

确保 MySQL 数据库已创建，监控系统会自动创建所需的数据表。

## 使用方法

### 启动监控系统

```bash
# 使用 uv 运行
uv run python main.py

# 或后台运行
nohup uv run python main.py > /dev/null 2>&1 &
```

### 使用 systemd 管理服务

创建 `/etc/systemd/system/web-monitor.service`：

```ini
[Unit]
Description=Web Monitor Service
After=network.target mysql.service

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/fengyu/WebMoniter
ExecStart=/home/fengyu/.local/bin/uv run python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

管理命令：

```bash
sudo systemctl daemon-reload
sudo systemctl start web-monitor
sudo systemctl enable web-monitor
sudo systemctl status web-monitor
sudo journalctl -u web-monitor -f
```

### 监控任务配置

监控任务在 `main.py` 的 `register_monitors()` 函数中配置：

- **虎牙监控**：默认每 2 分钟执行一次
- **微博监控**：默认每 5 分钟执行一次
- **日志清理**：默认每天凌晨 2 点执行

可以根据需要修改执行频率：

```python
# 修改执行间隔
scheduler.add_interval_job(
    func=run_huya_monitor,
    minutes=2,  # 修改这里的数值
    job_id="huya_monitor",
)
```

## 添加新的监控任务

1. 在 `monitors/` 目录下创建新的监控类，继承 `BaseMonitor`
2. 在 `main.py` 中创建运行函数（如 `run_xxx_monitor`）
3. 在 `register_monitors()` 函数中注册任务：

```python
async def run_new_monitor():
    """运行新监控任务"""
    config = get_config()
    async with NewMonitor(config) as monitor:
        await monitor.run()

# 在 register_monitors 中注册
scheduler.add_interval_job(
    func=run_new_monitor,
    minutes=5,
    job_id="new_monitor",
)
```

## 日志管理

- 日志文件存储在 `logs/` 目录
- 系统会自动清理 3 天前的日志文件（可配置）
- 前台运行时日志同时输出到控制台和文件
- 后台运行时日志仅输出到文件

## 开发

### 安装开发依赖

```bash
uv sync --extra dev
```

### 代码格式化

```bash
# 使用 black 格式化
uv run black .

# 使用 ruff 检查
uv run ruff check .
```

### 运行测试

```bash
uv run pytest
```

## 注意事项

1. **并发控制**：微博监控建议并发数设置为 2-5，避免触发限流；虎牙监控可以设置更高（5-10）
2. **Cookie 更新**：定期更新微博和虎牙的 Cookie，避免失效
3. **数据库连接**：确保 MySQL 服务正常运行，数据库连接配置正确
4. **日志清理**：定期检查日志目录大小，避免占用过多磁盘空间
5. **systemd 服务**：修改配置文件后需执行 `sudo systemctl daemon-reload`，确保 `ExecStart` 路径正确

## 许可证

本项目采用 MIT 许可证。

## 贡献

欢迎提交 Issue 和 Pull Request！

