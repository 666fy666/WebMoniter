# 青龙面板兼容指南

WebMoniter 支持在 [青龙面板](https://github.com/whyour/qinglong) 中运行定时任务。青龙用户可通过**环境变量**配置参数，推送结果自动走**青龙内置通知**（QLAPI），与主项目逻辑完全兼容且互不影响。

## 概述

| 项目 | 说明 |
|------|------|
| **配置方式** | 青龙「环境变量」中添加 `WEBMONITER_` 前缀的变量 |
| **推送通知** | 自动使用 [QLAPI.systemNotify](https://qinglong.online/guide/user-guide/built-in-api)，与青龙「通知设置」一致 |
| **运行方式** | `python -m src.ql <task_id>`（统一 CLI，见 `src/ql/__main__.py`） |
| **与主项目** | 完全独立，可同时部署主项目与青龙脚本 |

---

## 一、部署方式

### 方式一：订阅整库（推荐）

1. 在青龙面板 → **订阅管理** → **添加订阅**  
   - 订阅地址：`https://github.com/666fy666/WebMoniter`  
   - 定时规则：`0 0 * * *`（每日 0 点拉取一次）  
   - 白名单：`src/ql/`（保留 `__main__.py`、`_runner.py`、`compat.py` 即可）

2. 查看可用任务 ID：
   ```bash
   cd /path/to/WebMoniter && python -m src.ql --list
   ```

### 方式二：克隆整库后运行

1. 克隆项目到青龙的 `scripts` 目录：
   ```bash
   cd /src/ql/scripts
   git clone https://github.com/666fy666/WebMoniter.git
   cd WebMoniter
   ```

2. 安装依赖（青龙容器内通常已有，可先执行任务看是否报错）：
   ```bash
   uv sync --locked
   # 或使用 pip: pip install -e .
   ```

3. 在青龙「定时任务」中新增任务：
   - 名称：iKuuu 签到
   - 命令：`cd /path/to/WebMoniter && python -m src.ql ikuuu_checkin`
   - 定时规则：`0 8 * * *`（每天 8:00）

> **迁移说明**：旧版 `src/ql/ikuuu_checkin.py` 等薄脚本已移除，请统一改用 `python -m src.ql <task_id>`。

---

## 二、环境变量配置

所有配置通过青龙「环境变量」添加，变量名以 `WEBMONITER_` 为前缀（部分支持无前缀）。

### 2.1 通用说明

| 规则 | 说明 |
|------|------|
| 启用任务 | `WEBMONITER_<任务>_ENABLE=true` 或 `1` |
| 单值 | 如 `WEBMONITER_CHECKIN_EMAIL=xxx` |
| 多值 | 使用 `,` 或 `|` 分隔，如 `WEBMONITER_TIEBA_COOKIES=cookie1,cookie2` |
| 多账号 JSON | 如 `WEBMONITER_CHECKIN_ACCOUNTS=[{"email":"a@b.com","password":"xx"}]` |
| 可选前缀 | 部分变量支持省略 `WEBMONITER_`，直接使用 `CHECKIN_EMAIL` 等 |

### 2.2 各任务环境变量一览

#### iKuuu 签到（`python -m src.ql ikuuu_checkin`）

| 环境变量 | 必填 | 说明 |
|----------|------|------|
| `WEBMONITER_CHECKIN_ENABLE` | 是 | `true` 或 `1` 启用 |
| `WEBMONITER_CHECKIN_EMAIL` | 是* | 登录邮箱（单账号） |
| `WEBMONITER_CHECKIN_PASSWORD` | 是* | 登录密码 |
| `WEBMONITER_CHECKIN_ACCOUNTS` | 多账号 | JSON：`[{"email":"a@b.com","password":"xx"}]` 或 `email1\|pass1,email2\|pass2` |
| `WEBMONITER_CHECKIN_TIME` | 否 | 签到时间 HH:MM，默认 08:00 |

**定时规则建议**：`0 8 * * *`

---

#### 百度贴吧签到（`python -m src.ql tieba_checkin`）

| 环境变量 | 必填 | 说明 |
|----------|------|------|
| `WEBMONITER_TIEBA_ENABLE` | 是 | `true` 启用 |
| `WEBMONITER_TIEBA_COOKIE` | 是* | 含 BDUSS 的 Cookie |
| `WEBMONITER_TIEBA_COOKIES` | 多账号 | 多个 Cookie 用 `\|` 分隔 |
| `WEBMONITER_TIEBA_TIME` | 否 | 默认 08:10 |

**定时规则建议**：`10 8 * * *`

---

#### 雨云签到（`python -m src.ql rainyun_checkin`）

| 环境变量 | 必填 | 说明 |
|----------|------|------|
| `WEBMONITER_RAINYUN_ENABLE` | 是 | `true` 启用 |
| `WEBMONITER_RAINYUN_USERNAME` | 单账号 | 雨云登录用户名 |
| `WEBMONITER_RAINYUN_PASSWORD` | 单账号 | 雨云登录密码 |
| `WEBMONITER_RAINYUN_API_KEY` | 否 | 可选，用于续费查询 |
| `WEBMONITER_RAINYUN_ACCOUNTS` | 多账号 | JSON：`[{"username":"u1","password":"p1","api_key":"可选"}]` |
| `WEBMONITER_RAINYUN_TIME` | 否 | 默认 08:30 |

**定时规则建议**：`30 8 * * *`

---

#### 阿里云盘签到（`python -m src.ql aliyun_checkin`）

| 环境变量 | 必填 | 说明 |
|----------|------|------|
| `WEBMONITER_ALIYUN_ENABLE` | 是 | `true` 启用 |
| `WEBMONITER_ALIYUN_REFRESH_TOKEN` | 是* | refresh_token |
| `WEBMONITER_ALIYUN_REFRESH_TOKENS` | 多账号 | 多个用 `,` 分隔 |
| `WEBMONITER_ALIYUN_TIME` | 否 | 默认 05:30 |

**定时规则建议**：`30 5 * * *`

---

#### 微博超话签到（`python -m src.ql weibo_chaohua_checkin`）

| 环境变量 | 必填 | 说明 |
|----------|------|------|
| `WEBMONITER_WEIBO_CHAOHUA_ENABLE` | 是 | `true` 启用 |
| `WEBMONITER_WEIBO_CHAOHUA_COOKIE` | 是* | 含 XSRF-TOKEN 的 Cookie |
| `WEBMONITER_WEIBO_CHAOHUA_COOKIES` | 多账号 | 多个用 `\|` 分隔 |
| `WEBMONITER_WEIBO_CHAOHUA_TIME` | 否 | 默认 23:45 |

**定时规则建议**：`45 23 * * *`

---

#### 天气推送（`python -m src.ql weather_push`）

| 环境变量 | 必填 | 说明 |
|----------|------|------|
| `WEBMONITER_WEATHER_ENABLE` | 是 | `true` 启用 |
| `WEBMONITER_WEATHER_CITY_CODE` | 是 | 城市代码，如 `101020100`（上海） |
| `WEBMONITER_WEATHER_TIME` | 否 | 默认 07:30 |

**定时规则建议**：`30 7 * * *`

---

### 2.3 其他任务环境变量速查

| task_id（`python -m src.ql <id>`） | 主要环境变量 |
|----------|--------------|
| `enshan_checkin` | `ENSHAN_ENABLE`, `ENSHAN_COOKIE`, `ENSHAN_COOKIES` |
| `tyyun_checkin` | `TYYUN_ENABLE`, `TYYUN_USERNAME`, `TYYUN_PASSWORD`, `TYYUN_ACCOUNTS` |
| `smzdm_checkin` | `SMZDM_ENABLE`, `SMZDM_COOKIE`, `SMZDM_COOKIES` |
| `zdm_draw` | `ZDM_DRAW_ENABLE`, `ZDM_DRAW_COOKIE`, `ZDM_DRAW_COOKIES` |
| `fg_checkin` | `FG_ENABLE`, `FG_COOKIE`, `FG_COOKIES` |
| `miui_checkin` | `MIUI_ENABLE`, `MIUI_ACCOUNT`, `MIUI_PASSWORD`, `MIUI_ACCOUNTS` |
| `iqiyi_checkin` | `IQIYI_ENABLE`, `IQIYI_COOKIE`, `IQIYI_COOKIES` |
| `lenovo_checkin` | `LENOVO_ENABLE`, `LENOVO_ACCESS_TOKEN`, `LENOVO_ACCESS_TOKENS` |
| `lbly_checkin` | `LBLY_ENABLE`, `LBLY_REQUEST_BODY`, `LBLY_REQUEST_BODIES` |
| `pinzan_checkin` | `PINZAN_ENABLE`, `PINZAN_ACCOUNT`, `PINZAN_PASSWORD`, `PINZAN_ACCOUNTS` |
| `dml_checkin` | `DML_ENABLE`, `DML_OPENID`, `DML_OPENIDS` |
| `xiaomao_checkin` | `XIAOMAO_ENABLE`, `XIAOMAO_TOKEN`, `XIAOMAO_TOKENS` |
| `ydwx_checkin` | `YDWX_ENABLE`, `YDWX_DEVICE_PARAMS`, `YDWX_TOKEN`, `YDWX_ACCOUNTS` |
| `xingkong_checkin` | `XINGKONG_ENABLE`, `XINGKONG_USERNAME`, `XINGKONG_PASSWORD`, `XINGKONG_ACCOUNTS` |
| `freenom_checkin` | `FREENOM_ENABLE`, `FREENOM_ACCOUNTS` |
| `qtw_checkin` | `QTW_ENABLE`, `QTW_COOKIE`, `QTW_COOKIES` |
| `kuake_checkin` | `KUAKE_ENABLE`, `KUAKE_COOKIE`, `KUAKE_COOKIES` |
| `kjwj_checkin` | `KJWJ_ENABLE`, `KJWJ_ACCOUNTS` |
| `fr_checkin` | `FR_ENABLE`, `FR_COOKIE` |
| `nine_nine_nine_task` | `NINE_NINE_NINE_ENABLE`, `NINE_NINE_NINE_TOKENS` |
| `zgfc_draw` | `ZGFC_ENABLE`, `ZGFC_TOKENS` |
| `ssq_500w_notice` | `SSQ_500W_ENABLE` |

所有变量均需加 `WEBMONITER_` 前缀，如 `WEBMONITER_ENSHAN_ENABLE`、`WEBMONITER_SMZDM_COOKIE` 等。

---

## 三、推送通知（QLAPI）

青龙环境下，推送自动使用 **青龙内置通知**，与青龙「系统设置 → 通知设置」一致，**无需额外配置**推送通道。

- 调用的是 [QLAPI.systemNotify](https://qinglong.online/guide/user-guide/built-in-api)
- 通知方式（Server 酱、Bark、Telegram 等）在青龙面板中统一配置
- 若 QLAPI 不可用（如非青龙环境），推送会静默跳过并记录日志

---

## 四、操作步骤示例

以 **iKuuu 签到** 为例：

### 1. 添加环境变量

在青龙 → **环境变量** 中新增：

| 名称 | 值 |
|------|-----|
| `WEBMONITER_CHECKIN_ENABLE` | `true` |
| `WEBMONITER_CHECKIN_EMAIL` | `你的邮箱@example.com` |
| `WEBMONITER_CHECKIN_PASSWORD` | `你的密码` |

### 2. 克隆或订阅项目

通过订阅或 `git clone` 获取完整仓库（需包含 `src/tasks/` 与 `src/ql/`）。

### 3. 添加定时任务

在青龙 → **定时任务** → **添加任务**：

- **名称**：iKuuu 签到
- **命令**：`cd /path/to/WebMoniter && python -m src.ql ikuuu_checkin`
- **定时规则**：`0 8 * * *`（每天 8:00）

### 4. 配置青龙通知（可选）

在青龙 → **系统设置** → **通知设置** 中配置推送方式，签到结果会按此处设置推送。

---

## 五、常见问题

### Q1：提示「QLAPI 不可用」？

- 确认脚本是在青龙面板内通过「定时任务」执行，而非本机直接运行
- 青龙会注入 `QLAPI`，本机测试时不会有此对象
- 若在青龙内仍不可用，可查看青龙版本是否支持 [内置 API](https://qinglong.online/guide/user-guide/built-in-api)

### Q2：提示找不到模块或依赖？

- 克隆整库时，确保工作目录为项目根目录，脚本会自动切换
- 缺少依赖时在青龙容器内执行：`pip3 install aiohttp beautifulsoup4 requests pyyaml pydantic`
- 部分任务（如小茅预约、小米社区）需要 `pycryptodome`

### Q3：多账号如何配置？

- **iKuuu**：`WEBMONITER_CHECKIN_ACCOUNTS=[{"email":"a@b.com","password":"xx"},{"email":"b@b.com","password":"yy"}]`
- **贴吧 / 值得买等**：`WEBMONITER_XXX_COOKIES=cookie1|cookie2|cookie3`
- **雨云 / 阿里云盘**：`WEBMONITER_XXX_KEYS=key1,key2` 或 `WEBMONITER_XXX_TOKENS=token1,token2`

### Q4：与主项目是否冲突？

- **不冲突**。青龙模式通过环境变量和 QLAPI 独立工作
- 主项目仍使用 `config.yml` 和原有推送通道
- 可同时部署：主项目做常驻监控 + 青龙做部分签到任务

### Q5：Cookie 如何获取？

- 浏览器登录对应网站 → 按 F12 打开开发者工具 → Network 面板 → 任意请求 → 复制 Cookie 请求头
- 贴吧需包含 BDUSS，微博超话需包含 XSRF-TOKEN，具体见主项目 **`config/config.yml.sample`** 注释

---

## 六、支持的任务列表

运行 `python -m src.ql --list` 可查看完整列表。常用 task_id：

| 命令 | 说明 |
|------|------|
| `python -m src.ql ikuuu_checkin` | iKuuu 签到 |
| `python -m src.ql tieba_checkin` | 百度贴吧签到 |
| `python -m src.ql rainyun_checkin` | 雨云签到 |
| `python -m src.ql aliyun_checkin` | 阿里云盘签到 |
| `python -m src.ql weibo_chaohua_checkin` | 微博超话签到 |
| `python -m src.ql weather_push` | 天气推送 |
| `python -m src.ql enshan_checkin` | 恩山论坛签到 |
| `python -m src.ql tyyun_checkin` | 天翼云盘签到 |
| `python -m src.ql smzdm_checkin` | 什么值得买签到 |
| `python -m src.ql zdm_draw` | 值得买每日抽奖 |
| `python -m src.ql fg_checkin` | 富贵论坛签到 |
| `python -m src.ql miui_checkin` | 小米社区签到 |
| `python -m src.ql iqiyi_checkin` | 爱奇艺签到 |
| `python -m src.ql lenovo_checkin` | 联想乐豆签到 |
| `python -m src.ql lbly_checkin` | 丽宝乐园签到 |
| `python -m src.ql pinzan_checkin` | 品赞签到 |
| `python -m src.ql dml_checkin` | 达美乐任务 |
| `python -m src.ql xiaomao_checkin` | 小茅预约（i茅台） |
| `python -m src.ql ydwx_checkin` | 一点万象签到 |
| `python -m src.ql xingkong_checkin` | 星空代理签到 |
| `python -m src.ql freenom_checkin` | Freenom 续期 |
| `python -m src.ql qtw_checkin` | 千图网签到 |
| `python -m src.ql kuake_checkin` | 夸克网盘签到 |
| `python -m src.ql kjwj_checkin` | 科技玩家签到 |
| `python -m src.ql fr_checkin` | 帆软签到 |
| `python -m src.ql nine_nine_nine_task` | 999 会员中心 |
| `python -m src.ql zgfc_draw` | 中国福彩抽奖 |
| `python -m src.ql ssq_500w_notice` | 双色球开奖通知 |

---

## 七、参考链接

- [青龙面板 GitHub](https://github.com/whyour/qinglong)
- [青龙内置 API 文档](https://qinglong.online/guide/user-guide/built-in-api)
- [WebMoniter 文档站](index.md)
