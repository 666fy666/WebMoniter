# 监控与定时任务

系统包含两类任务：

- **监控任务**：按固定间隔轮询，检测到变化（如微博新动态、虎牙开播）时推送。  
- **定时任务**：按每日定点时间（Cron）执行，如各类签到、日志清理、天气推送等。

**通用行为**：

- 项目**启动时**会执行一次所有定时任务（签到类仅在 `enable: true` 且配置完整时真正执行）。  
- 定时任务默认**当天已运行则跳过**；在 Web「任务管理」中**手动触发**可强制执行。  
- 修改 `config.yml` 后约 **5 秒热重载** 生效，无需重启。

---

## 任务管理界面

在 Web 管理界面的「任务管理」中，可查看所有监控任务与定时任务，支持「立即运行」手动触发、「查看日志」查看该任务今日日志。

![任务管理界面](../assets/screenshots/任务管理.png){ width="800" }

---

## 监控任务一览

| 平台 | 功能 | 配置节点 | 详细说明 |
|:----:|:-----|:--------|:--------|
| 微博 | 监控用户最新动态 | `weibo` | [监控任务详解](tasks/monitors.md) |
| 虎牙 | 监控直播间开播/下播 | `huya` | [监控任务详解](tasks/monitors.md) |
| 哔哩哔哩 | 动态 + 开播/下播 | `bilibili` | [监控任务详解](tasks/monitors.md) |
| 抖音 | 直播开播/下播 | `douyin` | [监控任务详解](tasks/monitors.md) |
| 斗鱼 | 直播开播/下播 | `douyu` | [监控任务详解](tasks/monitors.md) |
| 小红书 | 用户最新笔记 | `xhs` | [监控任务详解](tasks/monitors.md) |

完整配置项、Cookie/UID/房间号获取方式见 **[监控任务详解](tasks/monitors.md)**。各监控支持 `enable` 配置，设为 `false` 可暂停，热重载生效。

---

## 定时任务一览

| 任务 | 配置节点 | 默认时间 | 认证/说明 | 详细说明 |
|:-----|:--------|:--------|:----------|:--------|
| 微博超话签到 | `weibo_chaohua` | 23:45 | Cookie（XSRF-TOKEN） | [定时任务详解](tasks/checkin.md) |
| iKuuu 签到 | `checkin` | 08:00 | 邮箱+密码 | [定时任务详解](tasks/checkin.md) |
| 雨云签到 | `rainyun` | 08:30 | 账号+密码（api_key 可选续费） | [定时任务详解](tasks/checkin.md) |
| 百度贴吧签到 | `tieba` | 08:10 | Cookie（BDUSS） | [定时任务详解](tasks/checkin.md) |
| 恩山论坛签到 | `enshan` | 02:00 | Cookie | [定时任务详解](tasks/checkin.md) |
| 天翼云盘签到 | `tyyun` | 04:30 | 手机号+密码 | [定时任务详解](tasks/checkin.md) |
| 阿里云盘签到 | `aliyun` | 05:30 | refresh_token | [定时任务详解](tasks/checkin.md) |
| 什么值得买签到 | `smzdm` | 00:30 | Cookie | [定时任务详解](tasks/checkin.md) |
| 值得买每日抽奖 | `zdm_draw` | 07:30 | Cookie | [定时任务详解](tasks/checkin.md) |
| 富贵论坛签到 | `fg` | 00:01 | Cookie | [定时任务详解](tasks/checkin.md) |
| 小米社区签到 | `miui` | 08:30 | 账号+密码 | [定时任务详解](tasks/checkin.md) |
| 爱奇艺签到 | `iqiyi` | 06:00 | Cookie | [定时任务详解](tasks/checkin.md) |
| 联想乐豆签到 | `lenovo` | 05:30 | access_token | [定时任务详解](tasks/checkin.md) |
| 丽宝乐园签到 | `lbly` | 05:30 | 请求体 JSON | [定时任务详解](tasks/checkin.md) |
| 品赞代理签到 | `pinzan` | 08:00 | 账号+密码 | [定时任务详解](tasks/checkin.md) |
| 达美乐任务 | `dml` | 06:00 | openid | [定时任务详解](tasks/checkin.md) |
| 小茅预约（i茅台） | `xiaomao` | 09:00 | token 串 | [定时任务详解](tasks/checkin.md) |
| 一点万象签到 | `ydwx` | 06:00 | deviceParams+token | [定时任务详解](tasks/checkin.md) |
| 星空代理签到 | `xingkong` | 07:30 | 用户名+密码 | [定时任务详解](tasks/checkin.md) |
| Freenom 续期 | `freenom` | 07:33 | 邮箱+密码 | [定时任务详解](tasks/checkin.md) |
| 天气推送 | `weather` | 07:30 | 城市代码 | [定时任务详解](tasks/checkin.md) |
| 千图网签到 | `qtw` | 01:30 | Cookie | [定时任务详解](tasks/checkin.md) |
| 夸克网盘签到 | `kuake` | 02:00 | Cookie | [定时任务详解](tasks/checkin.md) |
| 科技玩家签到 | `kjwj` | 07:30 | 账号+密码 | [定时任务详解](tasks/checkin.md) |
| 帆软社区签到 | `fr` | 06:30 | Cookie | [定时任务详解](tasks/checkin.md) |
| 999 健康任务 | `nine_nine_nine` | 15:15 | Authorization | [定时任务详解](tasks/checkin.md) |
| 福彩抽奖 | `zgfc` | 08:00 | Authorization | [定时任务详解](tasks/checkin.md) |
| 双色球通知 | `ssq_500w` | 21:30 | 无需账号 | [定时任务详解](tasks/checkin.md) |
| 日志清理 | `log_cleanup` | 02:10 | 无 | [定时任务详解](tasks/checkin.md) |
| Demo 示例 | `plugins.demo_task` | 08:30 | 无 | [定时任务详解](tasks/checkin.md) |

每个任务的**配置项、获取方式、示例**见 **[定时任务（签到）详解](tasks/checkin.md)**。

---

## 免打扰与插件

- **免打扰时段**（`quiet_hours`）：在指定时间段内不推送通知，任务照常执行。详见 [定时任务详解 - 免打扰时段](tasks/checkin.md)。  
- **二次开发**：新增监控/定时任务见 [二次开发指南](../SECONDARY_DEVELOPMENT.md)。

---

## 青龙面板部署

若已使用 [青龙面板](https://github.com/whyour/qinglong)，可通过 `ql/` 目录下的脚本运行定时任务，配置使用**环境变量**，推送走**青龙内置通知**（QLAPI）。详见 [青龙面板兼容指南](../QINGLONG.md)。
