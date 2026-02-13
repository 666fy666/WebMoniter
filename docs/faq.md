# 常见问题

---

??? question "如何更新 Cookie？"
    直接修改 `config.yml` 中的 Cookie 值，**无需重启容器或程序**。系统支持配置热重载，会在约 5 秒内自动检测并应用新配置。

---

??? question "监控任务没有执行怎么办？"
    1. 查看日志：`logs/main_*.log`（总日志）或 `logs/task_{job_id}_*.log`（任务专属日志），也可在 Web 日志页面切换查看
    2. 确认 `config.yml` 格式正确（YAML 语法）
    3. 检查网络与 Cookie 是否有效
    4. 确认监控任务已启用（如 `enable: true`，或对应监控块已配置）

---

??? question "如何调整监控频率？"
    在 `config.yml` 中修改对应间隔（秒）即可，无需重启：
    - 微博：`weibo.monitor_interval_seconds`（默认 300）
    - 虎牙：`huya.monitor_interval_seconds`（默认 65）
    - 哔哩哔哩：`bilibili.monitor_interval_seconds`（默认 60）
    - 抖音：`douyin.monitor_interval_seconds`（默认 30）
    - 斗鱼：`douyu.monitor_interval_seconds`（默认 300）
    - 小红书：`xhs.monitor_interval_seconds`（默认 300）

---

??? question "数据库和日志文件在哪里？"
    | 部署方式   | 数据库位置   | 日志位置     |
    |:----------:|:------------:|:------------:|
    | Docker 部署 | `./data/` 目录 | `./logs/` 目录 |
    | 本地部署   | `./data/` 目录 | `./logs/` 目录 |

    日志目录内含：
    - `main_YYYYMMDD.log`：当日总日志
    - `task_{任务ID}_YYYYMMDD.log`：各任务专属日志

---

??? question "Web 界面无法访问怎么办？"
    1. 确认程序已正常启动（看控制台或日志）
    2. 确认端口 8866 未被占用
    3. Docker 部署时确认端口映射为 `8866:8866`
    4. 检查防火墙是否放行 8866

---

??? question "免打扰时段内会遗漏消息吗？"
    免打扰时段内，监控任务会**照常执行**并更新数据库，但**不会推送通知**。若担心遗漏，可查看日志或数据记录，或关闭免打扰配置。

---

??? question "青龙面板如何部署？"
    在青龙「环境变量」中添加 `WEBMONITER_*` 前缀的变量（如 `WEBMONITER_CHECKIN_ENABLE`、`WEBMONITER_CHECKIN_EMAIL`），拉取或克隆项目后，在「定时任务」中添加 `task ql/ikuuu_checkin.py` 等脚本。推送自动走青龙内置通知（QLAPI）。详见 [青龙面板兼容指南](QINGLONG.md)。

---

??? question "如何启用 AI 助手？"
    1. 执行 `uv sync --extra ai` 安装 AI 依赖（chromadb、httpx、openai）
    2. 在 `config.yml` 中配置 `ai_assistant` 节点，设置 `enable: true` 以及 `provider`、`api_key`、`model` 等
    3. 重启或等待热重载后，在配置管理、任务管理、数据展示页面底部即可看到「问 AI」入口

    支持 OpenAI、DeepSeek、通义千问、智谱、Moonshot、Ollama 等 OpenAI 兼容 API。详见 [AI 助手使用指南](guides/ai-assistant.md)。
