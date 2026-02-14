# 定时任务（签到）详解

以下为所有内置定时任务的配置说明。每个任务在 `config.yml` 中有独立配置节点，**必填项**未配置或 `enable: false` 时不会执行。  
**默认行为**：项目启动时会执行一次；之后按 `time` 每日定点执行；若当天已运行过则跳过（Web「任务管理」中手动触发可强制执行）。

---

## 通用配置项

多数签到任务支持以下字段（具体以各任务为准）：

| 配置项 | 说明 |
|:-------|:-----|
| `enable` | 是否启用，`true` 时且其他必填项齐全才会执行 |
| `time` | 每日执行时间，24 小时制 `HH:MM`，如 `"08:00"` |
| `push_channels` | 推送通道名称列表，为空时使用全部已配置通道 |

---

## 微博超话签到

**配置节点**：`weibo_chaohua`  
**默认时间**：23:45  
**认证方式**：Cookie（须包含 **XSRF-TOKEN**），支持多 Cookie。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `cookie` | 字符串 | 单账号必填 | 单账号时填写完整 Cookie |
| `cookies` | 列表 | 多账号时使用 | 多账号时每项为完整 Cookie 字符串，优先于 `cookie` |
| `time` | 字符串 | 否 | 签到时间，默认 `"23:45"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 如何获取 Cookie

1. 浏览器打开 [微博](https://weibo.com) 并登录。  
2. 按 `F12` → **Console（控制台）**，输入 `document.cookie` 回车，复制输出的整段字符串。  
3. 确保其中包含 **XSRF-TOKEN**，填入 `cookie` 或 `cookies` 列表中的一项。

### 示例

```yaml
weibo_chaohua:
  enable: true
  cookie: "SCF=xxx; XSRF-TOKEN=xxx; SUB=xxx; ..."
  # 多账号时使用 cookies:
  # cookies:
  #   - "SCF=xxx; XSRF-TOKEN=xxx; ..."
  #   - "SCF=yyy; XSRF-TOKEN=yyy; ..."
  time: "23:45"
  push_channels: []
```

---

## iKuuu 签到

**配置节点**：`checkin`  
**默认时间**：08:00  
**认证方式**：邮箱 + 密码。域名自动从 ikuuu.club 发现，无需配置 URL。支持多账号。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `email` | 字符串 | 单账号必填 | 登录邮箱 |
| `password` | 字符串 | 单账号必填 | 登录密码 |
| `accounts` | 列表 | 多账号时使用 | 每项 `email`、`password`，优先于单账号 |
| `time` | 字符串 | 否 | 默认 `"08:00"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 示例

```yaml
checkin:
  enable: true
  email: user@example.com
  password: your_password
  # 多账号：
  # accounts:
  #   - email: user1@example.com
  #     password: pass1
  #   - email: user2@example.com
  #     password: pass2
  time: "08:00"
  push_channels: []
```

---

## 雨云签到

**配置节点**：`rainyun`  
**默认时间**：08:30  
**认证方式**：账号密码（Selenium + ddddocr，参考 [Rainyun-Qiandao](https://github.com/Jielumoon/Rainyun-Qiandao)）。**签到使用账号密码登录**，`api_key` 仅用于服务器到期自动续费（可选）。需安装 Chrome/Chromium 及 chromedriver。  
**服务器自动续费**：签到完成后会检查游戏云服务器到期情况，剩余天数小于阈值且积分充足时自动续费 7 天。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `accounts` | 列表 | ✅ | 每项含 `username`、`password`，`api_key` 可选（用于续费） |
| `time` | 字符串 | 否 | 默认 `"08:30"` |
| `push_channels` | 列表 | 否 | 推送通道 |
| `auto_renew` | 布尔 | 否 | 是否启用服务器到期自动续费，默认 `true` |
| `renew_threshold_days` | 整数 | 否 | 剩余多少天内触发续费，默认 `7` |
| `renew_product_ids` | 列表 | 否 | 续费白名单（产品 ID），为空则续费所有即将到期的服务器 |

### 如何获取 API Key（续费用）

1. 登录 [雨云控制台](https://www.rainyun.com/)。  
2. 进入 **总览 → 用户 → 账户设置 → API 密钥**。  
3. 创建或复制 API 密钥，填入 `accounts` 中对应账号的 `api_key`（可选，仅续费时需要）。

### 示例

```yaml
rainyun:
  enable: true
  accounts:
    - username: 你的雨云账号
      password: 你的雨云密码
      api_key:  # 可选，用于服务器续费
    - username: 第二个账号
      password: 第二个密码
      api_key:  # 可选
  time: "08:30"
  push_channels: []
  auto_renew: true      # 服务器到期自动续费
  renew_threshold_days: 7  # 剩余 7 天内触发续费
  # renew_product_ids: [44500, 44501]  # 白名单，留空续费全部
```

### 参考

- 雨云官网：[https://www.rainyun.com](https://www.rainyun.com)
- Rainyun-Qiandao（三改版）：[https://github.com/Jielumoon/Rainyun-Qiandao](https://github.com/Jielumoon/Rainyun-Qiandao)

---

## 百度贴吧签到

**配置节点**：`tieba`  
**默认时间**：08:10  
**认证方式**：Cookie（**须包含 BDUSS**），支持多 Cookie。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `cookie` | 字符串 | 单账号必填 | 须含 BDUSS |
| `cookies` | 列表 | 多账号时使用 | 每项完整 Cookie |
| `time` | 字符串 | 否 | 默认 `"08:10"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 如何获取 Cookie

1. 浏览器登录 [百度贴吧](https://tieba.baidu.com)。  
2. `F12` → **Console**，输入 `document.cookie` 回车，复制整段。  
3. 确认其中包含 **BDUSS**，填入 `cookie` 或 `cookies` 中一项。

### 示例

```yaml
tieba:
  enable: true
  cookie: "BIDUPSID=xxx; BDUSS=xxx; ..."
  time: "08:10"
  push_channels: []
```

---

## 恩山论坛签到

**配置节点**：`enshan`  
**默认时间**：02:00  
**认证方式**：Cookie，支持多 Cookie。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `cookie` | 字符串 | 单账号必填 | 登录后 Cookie |
| `cookies` | 列表 | 多账号时使用 | 每项完整 Cookie |
| `time` | 字符串 | 否 | 默认 `"02:00"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 如何获取 Cookie

登录 [恩山论坛](https://www.right.com.cn/forum/) 后，F12 → Console → `document.cookie`，复制后填入。

### 示例

```yaml
enshan:
  enable: true
  cookie: "xxx"
  time: "02:00"
  push_channels: []
```

---

## 天翼云盘签到

**配置节点**：`tyyun`  
**默认时间**：04:30  
**认证方式**：手机号 + 密码，支持多账号（需 `rsa` 库）。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `username` | 字符串 | 单账号必填 | 手机号 |
| `password` | 字符串 | 单账号必填 | 密码 |
| `accounts` | 列表 | 多账号时使用 | 每项 `username`、`password` |
| `time` | 字符串 | 否 | 默认 `"04:30"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 示例

```yaml
tyyun:
  enable: true
  username: "13800138000"
  password: "xxx"
  time: "04:30"
  push_channels: []
```

---

## 阿里云盘签到

**配置节点**：`aliyun`  
**默认时间**：05:30  
**认证方式**：refresh_token，支持多 token。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `refresh_token` | 字符串 | 单账号必填 | 阿里云盘 refresh_token |
| `refresh_tokens` | 列表 | 多账号时使用 | 多个 token |
| `time` | 字符串 | 否 | 默认 `"05:30"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 如何获取 refresh_token

可参考社区脚本/wiki 获取，例如：[Common-scripts wiki - 阿里云盘 refresh_token](https://github.com/bighammer-link/Common-scripts/wiki)。

### 示例

```yaml
aliyun:
  enable: true
  refresh_token: "your_refresh_token"
  time: "05:30"
  push_channels: []
```

---

## 什么值得买签到

**配置节点**：`smzdm`  
**默认时间**：00:30  
**认证方式**：Cookie，支持多 Cookie。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `cookie` | 字符串 | 单账号必填 | 登录 Cookie |
| `cookies` | 列表 | 多账号时使用 | 每项完整 Cookie |
| `time` | 字符串 | 否 | 默认 `"00:30"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 如何获取 Cookie

登录 [什么值得买](https://www.smzdm.com/) 后，F12 → Console → `document.cookie`，复制填入。

### 示例

```yaml
smzdm:
  enable: true
  cookie: "xxx"
  time: "00:30"
  push_channels: []
```

---

## 值得买每日抽奖

**配置节点**：`zdm_draw`  
**默认时间**：07:30  
**认证方式**：与 smzdm 共用 Cookie，支持多 Cookie。

### 配置项

与 `smzdm` 类似：`enable`、`cookie`/`cookies`、`time`、`push_channels`。Cookie 获取方式同「什么值得买签到」。

### 示例

```yaml
zdm_draw:
  enable: true
  cookie: "xxx"
  time: "07:30"
  push_channels: []
```

---

## 富贵论坛签到

**配置节点**：`fg`  
**默认时间**：00:01  
**认证方式**：Cookie，支持多 Cookie。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `cookie` | 字符串 | 单账号必填 | 登录 Cookie |
| `cookies` | 列表 | 多账号时使用 | 每项完整 Cookie |
| `time` | 字符串 | 否 | 默认 `"00:01"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 如何获取 Cookie

登录富贵论坛后，F12 → Console → `document.cookie`，复制填入。

### 示例

```yaml
fg:
  enable: true
  cookie: "xxx"
  time: "00:01"
  push_channels: []
```

---

## 小米社区签到

**配置节点**：`miui`  
**默认时间**：08:30  
**认证方式**：手机号/账号 + 密码，支持多账号。需 `pycryptodome`，存在封号风险。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `account` | 字符串 | 单账号必填 | 手机号/账号 |
| `password` | 字符串 | 单账号必填 | 密码 |
| `accounts` | 列表 | 多账号时使用 | 每项 `account`、`password` |
| `time` | 字符串 | 否 | 默认 `"08:30"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 示例

```yaml
miui:
  enable: true
  account: "手机号"
  password: "密码"
  time: "08:30"
  push_channels: []
```

---

## 爱奇艺签到

**配置节点**：`iqiyi`  
**默认时间**：06:00  
**认证方式**：Cookie（须含 **P00001、P00003、QC005、__dfp** 等），支持多 Cookie。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `cookie` | 字符串 | 单账号必填 | 须含 P00001、P00003、QC005、__dfp |
| `cookies` | 列表 | 多账号时使用 | 每项完整 Cookie |
| `time` | 字符串 | 否 | 默认 `"06:00"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 如何获取 Cookie

登录 [爱奇艺](https://www.iqiyi.com/) 网页版，F12 → Network → 选任意请求 → 请求头中复制 Cookie，确保包含上述字段。

### 示例

```yaml
iqiyi:
  enable: true
  cookie: "P00001=xxx; P00003=xxx; QC005=xxx; __dfp=xxx; ..."
  time: "06:00"
  push_channels: []
```

---

## 联想乐豆签到

**配置节点**：`lenovo`  
**默认时间**：05:30  
**认证方式**：access_token（联想 App 请求头中 accesstoken），支持多 token。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `access_token` | 字符串 | 单账号必填 | 联想 App Headers 中 accesstoken |
| `access_tokens` | 列表 | 多账号时使用 | 多个 token |
| `time` | 字符串 | 否 | 默认 `"05:30"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 如何获取 access_token

在联想相关 App 内抓包，找到请求头中的 **accesstoken** 字段，复制其值填入。

### 示例

```yaml
lenovo:
  enable: true
  access_token: "xxx"
  time: "05:30"
  push_channels: []
```

---

## 丽宝乐园签到

**配置节点**：`lbly`  
**默认时间**：05:30  
**认证方式**：抓包获取请求体 JSON（含 MallID、Header.Token 等），支持多组 request_bodies。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `request_body` | 字符串 | 单账号必填 | 抓包得到的完整请求体 JSON |
| `request_bodies` | 列表 | 多账号时使用 | 多个请求体 JSON 字符串 |
| `time` | 字符串 | 否 | 默认 `"05:30"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 如何获取

抓包接口：`https://m.mallcoo.cn/api/user/User/GetRewardList`，复制请求体（JSON），填入 `request_body` 或 `request_bodies`。

### 示例

```yaml
lbly:
  enable: true
  request_body: '{"MallID":11192,"Header":{"Token":"xxx"}}'
  time: "05:30"
  push_channels: []
```

---

## 品赞代理签到

**配置节点**：`pinzan`  
**默认时间**：08:00  
**认证方式**：账号 + 密码，支持多账号。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `account` | 字符串 | 单账号必填 | 账号（如手机号） |
| `password` | 字符串 | 单账号必填 | 密码 |
| `accounts` | 列表 | 多账号时使用 | 每项 `account`、`password` |
| `time` | 字符串 | 否 | 默认 `"08:00"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 示例

```yaml
pinzan:
  enable: true
  account: "手机号"
  password: "密码"
  time: "08:00"
  push_channels: []
```

---

## 达美乐任务

**配置节点**：`dml`  
**默认时间**：06:00  
**认证方式**：小程序抓包获取 openid，支持多 openid。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `openid` | 字符串 | 单账号必填 | 抓包得到的 openid |
| `openids` | 列表 | 多账号时使用 | 多个 openid |
| `time` | 字符串 | 否 | 默认 `"06:00"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 如何获取 openid

达美乐小程序内抓包，从相关请求中获取 openid 参数，填入配置。

### 示例

```yaml
dml:
  enable: true
  openid: "xxx"
  time: "06:00"
  push_channels: []
```

---

## 小茅预约（i茅台）

**配置节点**：`xiaomao`  
**默认时间**：09:00  
**认证方式**：每条为「省份,城市,经度,纬度,设备id,token,MT-Token-Wap」（小茅运领奖励可不填 MT-Token-Wap）。需 `pycryptodome`。支持多账号 `tokens`。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `token` | 字符串 | 单账号必填 | 格式：省份,城市,经度,纬度,设备id,token,MT-Token-Wap |
| `tokens` | 列表 | 多账号时使用 | 多条上述格式字符串 |
| `mt_version` | 字符串 | 否 | 如 1.3.6，不填则尝试从 App Store 页获取 |
| `time` | 字符串 | 否 | 默认 `"09:00"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 示例

```yaml
xiaomao:
  enable: true
  token: "浙江省,宁波市,121.16,30.05,设备id,token,MT-Token-Wap"
  time: "09:00"
  push_channels: []
```

---

## 一点万象签到

**配置节点**：`ydwx`  
**默认时间**：06:00  
**认证方式**：deviceParams + token，支持多账号（accounts 中每项 device_params、token）。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `device_params` | 字符串 | 单账号必填 | 设备参数 |
| `token` | 字符串 | 单账号必填 | 令牌 |
| `accounts` | 列表 | 多账号时使用 | 每项 `device_params`、`token` |
| `time` | 字符串 | 否 | 默认 `"06:00"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 示例

```yaml
ydwx:
  enable: true
  device_params: "xxx"
  token: "xxx"
  time: "06:00"
  push_channels: []
```

---

## 星空代理签到

**配置节点**：`xingkong`  
**默认时间**：07:30  
**认证方式**：用户名 + 密码，支持多账号。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `username` | 字符串 | 单账号必填 | 用户名 |
| `password` | 字符串 | 单账号必填 | 密码 |
| `accounts` | 列表 | 多账号时使用 | 每项 `username`、`password` |
| `time` | 字符串 | 否 | 默认 `"07:30"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 示例

```yaml
xingkong:
  enable: true
  username: "user"
  password: "pass"
  time: "07:30"
  push_channels: []
```

---

## Freenom 免费域名续期

**配置节点**：`freenom`  
**默认时间**：07:33  
**认证方式**：邮箱 + 密码，支持多账号。对 14 天内到期的域名自动续期 12 个月。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `accounts` | 列表 | ✅ | 每项 `email`、`password`（Freenom 登录邮箱与密码） |
| `time` | 字符串 | 否 | 默认 `"07:33"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 参考

- Freenom 续期页：[https://my.freenom.com/domains.php?a=renewals](https://my.freenom.com/domains.php?a=renewals)

### 示例

```yaml
freenom:
  enable: true
  accounts:
    - email: "user1@example.com"
      password: "pass1"
    - email: "user2@example.com"
      password: "pass2"
  time: "07:33"
  push_channels: []
```

---

## 天气推送

**配置节点**：`weather`  
**默认时间**：07:30  
**说明**：按城市代码推送今日天气与未来 7 日预报，仅通知不写入数据库。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `city_code` | 字符串 | ✅ | 城市代码，如 101020100（上海） |
| `time` | 字符串 | 否 | 默认 `"07:30"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 如何获取城市代码

可参考：[city.json（城市代码示例）](https://fastly.jsdelivr.net/gh/Oreomeow/checkinpanel@master/city.json)  
接口说明：`http://t.weather.itboy.net/api/weather/city/{city_code}`。

### 示例

```yaml
weather:
  enable: true
  city_code: "101020100"
  time: "07:30"
  push_channels: []
```

---

## 千图网签到

**配置节点**：`qtw`  
**默认时间**：01:30  
**认证方式**：Cookie，支持多 Cookie。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `cookie` | 字符串 | 单账号必填 | 登录 Cookie |
| `cookies` | 列表 | 多账号时使用 | 每项完整 Cookie |
| `time` | 字符串 | 否 | 默认 `"01:30"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 示例

```yaml
qtw:
  enable: true
  cookie: "xxx"
  time: "01:30"
  push_channels: []
```

---

## 夸克网盘签到

**配置节点**：`kuake`  
**默认时间**：02:00  
**认证方式**：Cookie（登录 [pan.quark.cn](https://pan.quark.cn/) 后的请求头 Cookie），支持多 Cookie。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `cookie` | 字符串 | 单账号必填 | 完整 Cookie |
| `cookies` | 列表 | 多账号时使用 | 每项完整 Cookie |
| `time` | 字符串 | 否 | 默认 `"02:00"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 如何获取 Cookie

浏览器登录 [夸克网盘](https://pan.quark.cn/)，F12 → Network → 选任意请求 → 请求头复制 Cookie。

### 示例

```yaml
kuake:
  enable: true
  cookie: "quark_xxx=..."
  time: "02:00"
  push_channels: []
```

---

## 科技玩家签到

**配置节点**：`kjwj`  
**默认时间**：07:30  
**认证方式**：账号 + 密码，支持多账号。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `accounts` | 列表 | ✅ | 每项 `username`、`password` |
| `time` | 字符串 | 否 | 默认 `"07:30"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 示例

```yaml
kjwj:
  enable: true
  accounts:
    - username: "user1@example.com"
      password: "pass1"
  time: "07:30"
  push_channels: []
```

---

## 帆软社区签到

**配置节点**：`fr`  
**默认时间**：06:30  
**认证方式**：Cookie（社区签到 + 摇摇乐）。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `cookie` | 字符串 | ✅ | 登录 Cookie |
| `time` | 字符串 | 否 | 默认 `"06:30"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 示例

```yaml
fr:
  enable: true
  cookie: "xxx"
  time: "06:30"
  push_channels: []
```

---

## 999 会员中心健康任务

**配置节点**：`nine_nine_nine`  
**默认时间**：15:15  
**认证方式**：抓包 mc.999.com.cn 请求头中的 **Authorization**，支持多 token。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `tokens` | 列表 | ✅ | 每个账号的 Authorization 值 |
| `time` | 字符串 | 否 | 默认 `"15:15"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 示例

```yaml
nine_nine_nine:
  enable: true
  tokens:
    - "Bearer xxx"
  time: "15:15"
  push_channels: []
```

---

## 中国福彩抽奖

**配置节点**：`zgfc`  
**默认时间**：08:00  
**认证方式**：请求头 Authorization，支持多 token。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `tokens` | 列表 | ✅ | Authorization 值列表 |
| `time` | 字符串 | 否 | 默认 `"08:00"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 示例

```yaml
zgfc:
  enable: true
  tokens:
    - "xxx"
  time: "08:00"
  push_channels: []
```

---

## 双色球开奖通知

**配置节点**：`ssq_500w`  
**默认时间**：21:30  
**说明**：获取最新双色球开奖信息、守号检测、冷号机选等（仅娱乐通知，不涉及真实购彩）。无需账号，只需配置 `enable`、`time`、`push_channels`。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `time` | 字符串 | 否 | 默认 `"21:30"` |
| `push_channels` | 列表 | 否 | 推送通道 |

### 示例

```yaml
ssq_500w:
  enable: true
  time: "21:30"
  push_channels: []
```

---

## 日志清理

**配置节点**：`log_cleanup`  
**默认时间**：02:10  
**说明**：按保留天数清理历史日志文件，非签到类任务。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | 否 | 是否启用，默认 true |
| `time` | 字符串 | 否 | 执行时间，默认 `"02:10"` |
| `retention_days` | 整数 | 否 | 日志保留天数，默认 3 |

### 示例

```yaml
log_cleanup:
  enable: true
  time: "02:10"
  retention_days: 3
```

---

## 免打扰时段

**配置节点**：`quiet_hours`  
**说明**：在指定时间段内，监控与签到任务**照常执行并更新数据**，但**不推送通知**。支持跨天（如 22:00～08:00）。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用免打扰 |
| `start` | 字符串 | ✅ | 开始时间 HH:MM，如 `"22:00"` |
| `end` | 字符串 | ✅ | 结束时间 HH:MM，如 `"08:00"` |

### 示例

```yaml
quiet_hours:
  enable: true
  start: "22:00"
  end: "08:00"
```

!!! warning "注意"
    免打扰时段内可能遗漏重要消息，请按需使用。

---

## 插件示例任务（Demo）

**配置节点**：`plugins.demo_task`  
**默认时间**：08:30  
**说明**：二次开发示例任务，不需要可在 `job_registry.TASK_MODULES` 中移除。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | ✅ | 是否启用 |
| `time` | 字符串 | 否 | 默认 `"08:30"` |
| `message` | 字符串 | 否 | 自定义消息内容 |

### 示例

```yaml
plugins:
  demo_task:
    enable: false
    time: "08:30"
    message: "Demo 定时任务执行完成"
```

---

部分签到逻辑参考自 [only_for_happly](https://github.com/wd210010/only_for_happly)，已接入本项目统一推送与配置；主包未对其单独维护，若某平台接口变更可能导致任务失效，请以实际运行与日志为准。
