# 监控任务详解

监控任务按**固定间隔**轮询，检测到变化（如微博新动态、虎牙开播/下播）时通过推送通道发送通知。配置节点在 `config.yml` 中为 `weibo`、`huya`、`bilibili`、`douyin`、`douyu`、`xhs`。

---

## 微博监控

监控指定微博用户的**最新动态**，有新微博时推送通知（不检测开播）。

### 配置项说明

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | 否 | 是否启用该监控，默认 true；设为 false 时任务暂停，热重载生效 |
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
  enable: true                                 # 是否启用微博监控
  cookie: "SUB=xxx; SUBP=xxx; ALF=xxx; ..."   # 从浏览器开发者工具复制完整 Cookie
  uids: 1234567890,9876543210                  # 要监控的用户 UID，逗号分隔
  concurrency: 2
  monitor_interval_seconds: 300
  push_channels: []                            # 为空则使用全部通道
```

### 头像与封面图缓存 & 推送图片

微博监控在拉取用户信息时，会自动：

- 将头像相关图片缓存到 `data/weibo/<用户名>/` 目录下，包含：
  - `profile_image.jpg`（`profile_image_url`）
  - `avatar_large.jpg`（`avatar_large`）
  - `avatar_hd.jpg`（`avatar_hd`）
  - `cover_image_phone.jpg`（`cover_image_phone`，手机端封面图）
- 首次下载成功后会复用本地文件，后续监控只在文件不存在时才尝试重新下载。

配合 `config.yml` 中的 `app.base_url` 与 Web 服务暴露的静态目录：

- 当 `app.base_url` 配置为例如 `http://localhost:8866` 时，封面图可通过  
  `http://localhost:8866/weibo_img/<用户名>/cover_image_phone.jpg` 访问；
- 大部分支持 `picurl` 的推送通道（如企业微信应用、钉钉机器人、PushPlus 等）会直接使用该 URL 作为卡片图片；
- 对于支持本地图片上传的通道（当前为 `telegram_bot`），系统会优先读取本地 `cover_image_phone.jpg`，通过官方 Bot API 上传原图。

> 提示：微博侧的图片链接通常带有过期时间与签名参数，系统会在链接仍有效时尽快缓存到本地；若远端链接已全部失效，则该用户将不再更新本地封面图，但不影响监控与文本推送。

### 参考

- 微博开放平台（了解接口与限制）：[https://open.weibo.com](https://open.weibo.com)

---

## 虎牙监控

监控指定虎牙**直播间**的**开播/下播状态**，状态变化时推送通知。

### 配置项说明

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `enable` | 布尔 | 否 | 是否启用该监控，默认 true；设为 false 时任务暂停，热重载生效 |
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
  enable: true
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
| `enable` | 布尔 | 否 | 是否启用该监控，默认 true；设为 false 时任务暂停，热重载生效 |
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
  enable: true
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
| `enable` | 布尔 | 否 | 是否启用该监控，默认 true；设为 false 时任务暂停，热重载生效 |
| `douyin_ids` | 字符串 | ✅ | 抖音号列表，逗号分隔，如 ASOULjiaran,Nana7mi0715 |
| `concurrency` | 整数 | 否 | 并发数，默认 2 |
| `monitor_interval_seconds` | 整数 | 否 | 监控间隔（秒），默认 30 |
| `push_channels` | 列表 | 否 | 推送通道名称列表 |

### 如何获取抖音号

- 打开抖音直播间，URL 形如 `https://live.douyin.com/ASOULjiaran`，**路径最后的字符串即为抖音号**。

### 配置示例

```yaml
douyin:
  enable: true
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
| `enable` | 布尔 | 否 | 是否启用该监控，默认 true；设为 false 时任务暂停，热重载生效 |
| `rooms` | 字符串 | ✅ | 房间号列表，逗号分隔 |
| `concurrency` | 整数 | 否 | 并发数，默认 2 |
| `monitor_interval_seconds` | 整数 | 否 | 监控间隔（秒），默认 300 |
| `push_channels` | 列表 | 否 | 推送通道名称列表 |

### 如何获取房间号

- 打开斗鱼直播间，URL 形如 `https://www.douyu.com/307876`，**数字部分即为房间号**。

### 配置示例

```yaml
douyu:
  enable: true
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
| `enable` | 布尔 | 否 | 是否启用该监控，默认 true；设为 false 时任务暂停，热重载生效 |
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
  enable: true
  cookie: ""
  profile_ids: 52d8c541b4c4d60e6c867480
  concurrency: 2
  monitor_interval_seconds: 300
  push_channels: []
```

---

## 通用说明

- **启用开关**：各监控任务支持 `enable` 配置，设为 `false` 时暂停该监控，热重载生效；未配置时默认为 `true`。  
- **启动时**：程序启动后会按配置的间隔开始轮询，无需额外触发。  
- **热重载**：修改各监控任务配置并保存 `config.yml` 后，约 5 秒内生效，无需重启。  
- **推送**：若配置了 `quiet_hours`（免打扰），在免打扰时段内不会推送，但监控仍会执行并更新数据。  
