# 监控任务详解

监控任务按**固定间隔**轮询，检测到变化（如微博新动态、虎牙开播/下播）时通过推送通道发送通知。配置节点在 `config.yml` 中为 `weibo`、`huya`、`bilibili`、`douyin`、`douyu`、`xhs`。

---

## 微博监控

监控指定微博用户的**最新动态**，有新微博时推送通知（不检测开播）。

### 配置项说明

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `cookie` | 字符串 | ✅ | 微博网页版登录后的 Cookie，用于请求接口 |
| `uids` | 字符串 | ✅ | 要监控的用户 UID，多个用英文逗号分隔，如 `1234567890,9876543210` |
| `concurrency` | 整数 | 否 | 并发数，建议 2～5，避免触发限流，默认 2 |
| `monitor_interval_seconds` | 整数 | 否 | 监控间隔（秒），默认 300（5 分钟） |
| `push_channels` | 列表 | 否 | 推送通道名称列表，为空时使用全部已配置通道 |

### 如何获取 Cookie

1. 使用浏览器登录 [微博网页版](https://weibo.com)。  
2. 按 `F12` 打开开发者工具，切到 **Network（网络）**。  
3. 刷新页面或随便点开一条微博，在请求列表中选任意一个请求，在请求头里找到 **Cookie**，完整复制。  
4. 将复制的内容填入 `config.yml` 中 `weibo.cookie`。  

!!! warning "注意"
    Cookie 会过期，若监控不再推送可重新按上述步骤获取并更新，保存后约 5 秒热重载生效，无需重启。

### 如何获取 UID

- 打开要监控的用户的微博主页，看浏览器地址栏。  
- 地址形如：`https://weibo.com/u/1234567890` 或 `https://weibo.com/1234567890`，其中 **数字部分即为 UID**（如 `1234567890`）。  
- 多个用户用英文逗号拼接到 `uids`，如：`uids: 1234567890,9876543210`。

### 配置示例

```yaml
weibo:
  cookie: "SUB=xxx; SUBP=xxx; ALF=xxx; ..."   # 从浏览器开发者工具复制完整 Cookie
  uids: 1234567890,9876543210                  # 要监控的用户 UID，逗号分隔
  concurrency: 2
  monitor_interval_seconds: 300
  push_channels: []                            # 为空则使用全部通道
```

### 参考

- 微博开放平台（了解接口与限制）：[https://open.weibo.com](https://open.weibo.com)

---

## 虎牙监控

监控指定虎牙**直播间**的**开播/下播状态**，状态变化时推送通知。

### 配置项说明

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `rooms` | 字符串 | ✅ | 要监控的房间号，多个用英文逗号分隔，如 `123456,654321` |
| `concurrency` | 整数 | 否 | 并发数，建议 5～10，默认 5 |
| `monitor_interval_seconds` | 整数 | 否 | 监控间隔（秒），默认 65 |
| `push_channels` | 列表 | 否 | 推送通道名称列表，为空时使用全部已配置通道 |

### 如何获取房间号

- 打开虎牙直播间页面，看浏览器地址栏。  
- 地址形如：`https://www.huya.com/123456`，其中 **数字部分即为房间号**（如 `123456`）。  
- 多个房间用英文逗号拼接到 `rooms`，如：`rooms: 123456,654321`。

### 配置示例

```yaml
huya:
  rooms: 123456,654321
  concurrency: 5
  monitor_interval_seconds: 65
  push_channels: []
```

### 参考

- 虎牙开放平台：[https://open.huya.com](https://open.huya.com)（本任务为轮询网页/接口，不强制要求开放平台账号）

---

## 哔哩哔哩监控

监控指定 B 站 UP 主的**动态发布**与**直播开播/下播**，检测到变化时推送通知。

### 配置项说明

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `uids` | 字符串 | ✅ | 要监控的 UP 主 UID，多个用英文逗号分隔 |
| `cookie` | 字符串 | 否 | 可选，防 ban，建议用小号 |
| `payload` | 字符串 | 否 | 可选，用于 -352 时自动获取 buvid3 |
| `skip_forward` | 布尔 | 否 | 是否跳过转发类型动态，默认 true |
| `concurrency` | 整数 | 否 | 并发数，默认 2 |
| `monitor_interval_seconds` | 整数 | 否 | 监控间隔（秒），默认 60 |
| `push_channels` | 列表 | 否 | 推送通道名称列表 |

### 如何获取 UID

- 打开 UP 主空间页，如 `https://space.bilibili.com/1795147802`，其中 **数字部分即为 UID**。

### 配置示例

```yaml
bilibili:
  cookie: ""
  payload: ""
  uids: 1795147802,1669777785
  skip_forward: true
  concurrency: 2
  monitor_interval_seconds: 60
  push_channels: []
```

---

## 抖音直播监控

监控指定抖音**直播间**的**开播/下播状态**，状态变化时推送通知。

### 配置项说明

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `douyin_ids` | 字符串 | ✅ | 抖音号列表，逗号分隔，如 ASOULjiaran,Nana7mi0715 |
| `concurrency` | 整数 | 否 | 并发数，默认 2 |
| `monitor_interval_seconds` | 整数 | 否 | 监控间隔（秒），默认 30 |
| `push_channels` | 列表 | 否 | 推送通道名称列表 |

### 如何获取抖音号

- 打开抖音直播间，URL 形如 `https://live.douyin.com/ASOULjiaran`，**路径最后的字符串即为抖音号**。

### 配置示例

```yaml
douyin:
  douyin_ids: ASOULjiaran,Nana7mi0715
  concurrency: 2
  monitor_interval_seconds: 30
  push_channels: []
```

---

## 斗鱼直播监控

监控指定斗鱼**直播间**的**开播/下播状态**，状态变化时推送通知。

### 配置项说明

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `rooms` | 字符串 | ✅ | 房间号列表，逗号分隔 |
| `concurrency` | 整数 | 否 | 并发数，默认 2 |
| `monitor_interval_seconds` | 整数 | 否 | 监控间隔（秒），默认 300 |
| `push_channels` | 列表 | 否 | 推送通道名称列表 |

### 如何获取房间号

- 打开斗鱼直播间，URL 形如 `https://www.douyu.com/307876`，**数字部分即为房间号**。

### 配置示例

```yaml
douyu:
  rooms: 307876,12306
  concurrency: 2
  monitor_interval_seconds: 300
  push_channels: []
```

---

## 小红书动态监控

监控指定小红书**用户**的**最新笔记**，有新笔记时推送通知（类似微博动态）。

### 配置项说明

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `profile_ids` | 字符串 | ✅ | Profile ID 列表，逗号分隔 |
| `cookie` | 字符串 | 否 | 可选，防 ban |
| `concurrency` | 整数 | 否 | 并发数，默认 2 |
| `monitor_interval_seconds` | 整数 | 否 | 监控间隔（秒），默认 300 |
| `push_channels` | 列表 | 否 | 推送通道名称列表 |

### 如何获取 Profile ID

- 打开用户主页，URL 形如 `https://www.xiaohongshu.com/user/profile/52d8c541b4c4d60e6c867480`，**路径最后的字符串即为 Profile ID**。

### 配置示例

```yaml
xhs:
  cookie: ""
  profile_ids: 52d8c541b4c4d60e6c867480
  concurrency: 2
  monitor_interval_seconds: 300
  push_channels: []
```

---

## 通用说明

- **启动时**：程序启动后会按配置的间隔开始轮询，无需额外触发。  
- **热重载**：修改各监控任务配置并保存 `config.yml` 后，约 5 秒内生效，无需重启。  
- **推送**：若配置了 `quiet_hours`（免打扰），在免打扰时段内不会推送，但监控仍会执行并更新数据。  
