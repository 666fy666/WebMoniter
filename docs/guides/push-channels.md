# 推送通道配置详解

监控与签到结果通过 **推送通道** 发送。在 `config.yml` 的 **`push_channel`** 中配置一个或多个通道（每项需 `name`、`type` 及该 type 所需参数）；各任务通过 **`push_channels`** 指定使用哪些通道（按 `name` 匹配），为空时使用全部已配置通道。

!!! tip "青龙面板用户"
    在 [青龙面板](https://github.com/whyour/qinglong) 中运行 `ql/*.py` 脚本时，推送**自动使用青龙内置通知**（QLAPI），与青龙「系统设置 → 通知设置」一致，无需在 `config.yml` 中配置推送通道。详见 [青龙面板兼容指南](../QINGLONG.md)。

---

## 通道一览

| 通道 | type | 支持图片 | 推荐度 | 说明 |
|:-----|:-----|:--------|:------|:-----|
| 企业微信群聊机器人 | wecom_bot | ✅ | 推荐 | 群内添加自定义机器人，配置简单 |
| 钉钉群聊机器人 | dingtalk_bot | ✅ | 推荐 | 群内添加自定义机器人，关键词建议用「【」 |
| 飞书群聊机器人 | feishu_bot | ❌ | 推荐 | 群内添加自定义机器人 |
| WxPusher | wxpusher | ✅ | 推荐 | 微信消息推送，需在官网创建应用 |
| 企业微信自建应用 | wecom_apps | ✅ | 可选 | 需企业微信后台创建应用，新应用需配置可信 IP |
| 飞书自建应用 | feishu_apps | ✅ | 可选 | 可创建个人版应用 |

| 通道 | type | 支持图片 | 说明 |
|:-----|:-----|:--------|:-----|
| Telegram 机器人 | telegram_bot | ✅ | 需自备网络环境 |
| NapCatQQ | napcat_qq | ✅ | 需自建 NapCatQQ 服务 |
| Bark | bark | ❌ | 苹果设备，轻量 |
| Server酱 Turbo | serverChan_turbo | ✅ | 免费 5 次/天 |
| Server酱 3 | serverChan_3 | ✅ | 需安装 app |
| PushPlus | pushplus | ✅ | 支持微信/邮件/Webhook 等 |
| Webhook | webhook | ✅ | 通用 HTTP 回调 |
| Gotify | gotify | ❌ | 自建推送服务 |
| 电子邮件 | email | ✅ | SMTP 发送邮件 |
| QQ 频道机器人 | qq_bot | ✅ | 需创建 QQ 机器人并开通频道发言 |
| 青龙 QLAPI | qlapi | ❌ | 青龙环境下自动使用 systemNotify，无需配置 |

---

## 企业微信群聊机器人

通过企业微信群内「添加群机器人」获得 Webhook，向群内推送消息。**支持图片**。

### 官方文档

- [企业微信 - 群机器人配置说明](https://developer.work.weixin.qq.com/document/path/99110)

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一，供任务 `push_channels` 引用 |
| `type` | 字符串 | ✅ | 固定为 `wecom_bot` |
| `key` | 字符串 | ✅ | 机器人 Webhook 的 key 参数（创建机器人时获得） |

### 如何获取 key

1. 在企业微信中创建群聊（或使用已有群）。  
2. 群设置 → **群机器人** → **添加群机器人**，设置名称后创建。  
3. 复制机器人 Webhook 地址，形如：`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx`，其中 **key=** 后面的部分即为 `key`。

### 配置示例

```yaml
push_channel:
  - name: 企业微信机器人
    type: wecom_bot
    key: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

---

## 钉钉群聊机器人

通过钉钉群内「添加自定义机器人」获得 Webhook。**支持图片**。自定义关键词建议使用「【」以兼容系统消息格式。

### 官方文档

- [钉钉 - 自定义机器人接入](https://open.dingtalk.com/document/robots/custom-robot-access)

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `dingtalk_bot` |
| `access_token` | 字符串 | ✅ | 机器人 Webhook 中的 access_token（创建机器人时获得） |
| `secret` | 字符串 | 否 | 加签密钥（SEC 开头的字符串）；若配置则使用加签方式，否则使用普通方式 |

### 如何获取 access_token 与 secret

1. 钉钉群 → **群设置** → **智能群助手** → **添加机器人** → **自定义**。  
2. 设置机器人名称、安全设置（可选「加签」并复制 **secret**）。  
3. 完成后的 Webhook 地址形如：`https://oapi.dingtalk.com/robot/send?access_token=xxxx`，其中 **access_token=** 后面的部分即为 `access_token`。

### 配置示例

```yaml
push_channel:
  - name: 钉钉机器人
    type: dingtalk_bot
    access_token: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    secret: "SECxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # 可选，加签时必填
```

---

## 飞书群聊机器人

通过飞书群内「添加机器人」→「自定义机器人」获得 Webhook。**暂不支持图片**。自定义关键词建议使用「【」。

### 官方文档

- [飞书 - 自定义机器人](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `feishu_bot` |
| `webhook_key` | 字符串 | ✅ | 机器人 Webhook URL 中的关键部分（创建时获得） |
| `sign_secret` | 字符串 | 否 | 签名密钥；若配置则使用签名校验方式 |

### 如何获取 webhook_key

1. 飞书群聊 → **设置** → **群机器人** → **添加机器人** → **自定义机器人**。  
2. 复制生成的 Webhook 地址，从中提取 webhook 的 key 部分填入 `webhook_key`。

### 配置示例

```yaml
push_channel:
  - name: 飞书机器人
    type: feishu_bot
    webhook_key: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    # sign_secret: "xxx"  # 可选
```

---

## 飞书自建应用

使用飞书开放平台创建的「自建应用」发送消息，可发到群、用户等。**支持图片**。可使用个人版飞书创建应用。

### 官方文档

- [飞书开放平台 - 创建应用](https://open.feishu.cn/app?lang=zh-CN)  
- [飞书 - 发送消息](https://open.feishu.cn/document/server-docs/im-v1/message/create)

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `feishu_apps` |
| `app_id` | 字符串 | ✅ | 应用 App ID |
| `app_secret` | 字符串 | ✅ | 应用 App Secret |
| `receive_id_type` | 字符串 | ✅ | 接收者 ID 类型，如 `chat_id`（群）、`user_id`（用户）等 |
| `receive_id` | 字符串 | ✅ | 接收者 ID（群聊 ID 或用户 open_id） |

### 如何获取

1. 登录 [飞书开放平台](https://open.feishu.cn/app?lang=zh-CN)，创建企业自建应用（或个人应用）。  
2. 在应用凭证中获取 **App ID**、**App Secret**。  
3. 为应用开通「获取群信息」「发送消息」等权限；获取群聊的 **chat_id** 或用户的 **open_id**，填入 `receive_id`，`receive_id_type` 填 `chat_id` 或 `user_id`。

### 配置示例

```yaml
push_channel:
  - name: 飞书自建应用
    type: feishu_apps
    app_id: "cli_xxxxxxxx"
    app_secret: "xxxxxxxxxxxxxxxx"
    receive_id_type: "chat_id"
    receive_id: "oc_xxxxxxxxxxxxxxxx"
```

---

## 企业微信自建应用

使用企业微信「自建应用」发送消息。**支持图片**。2022年6月20日后新创建的应用需配置可信 IP。

### 官方文档

- [企业微信 - 应用管理](https://work.weixin.qq.com/wework_admin/frame#apps/createApiApp)  
- [企业微信 - 发送应用消息](https://developer.work.weixin.qq.com/document/path/90236)

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `wecom_apps` |
| `corp_id` | 字符串 | ✅ | 企业 ID |
| `agent_id` | 字符串 | ✅ | 应用 AgentId |
| `corp_secret` | 字符串 | ✅ | 应用 Secret |
| `touser` | 字符串 | 否 | 接收成员 ID，多个用 `|` 分隔，`@all` 表示所有人，默认 `@all` |

### 如何获取

1. 企业微信管理后台 → **应用管理** → **自建** → 创建应用。  
2. 在「我的企业」中获取 **企业 ID**（corp_id）。  
3. 在应用详情中获取 **AgentId**、**Secret**。  
4. 新应用需在应用详情中配置 **可信 IP**（服务器出口 IP）。

### 配置示例

```yaml
push_channel:
  - name: 企业微信应用
    type: wecom_apps
    corp_id: "wwxxxxxxxx"
    agent_id: "1000002"
    corp_secret: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    touser: "@all"
```

---

## Telegram 机器人

通过 Telegram Bot API 发送消息到指定会话（群组或私聊）。**支持图片**。需服务器能访问 Telegram API（自备网络环境）。

### 官方文档

- [Telegram Bot API](https://core.telegram.org/bots/api)  
- [创建 Bot](https://core.telegram.org/bots#botfather)

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `telegram_bot` |
| `api_token` | 字符串 | ✅ | Bot 的 API Token（由 @BotFather 发放） |
| `chat_id` | 字符串 | ✅ | 接收消息的聊天 ID（群组或用户） |

### 如何获取 api_token

1. 在 Telegram 中搜索 **@BotFather**，发送 `/newbot` 按提示创建机器人。  
2. 创建完成后 BotFather 会返回 **API Token**，形如 `123456789:ABCdefGHI...`。

### 如何获取 chat_id

- **用户**：可先给机器人发一条消息，访问 `https://api.telegram.org/bot<api_token>/getUpdates` 查看返回中的 `chat.id`。  
- **群组**：将机器人拉入群，在群内发一条消息，同样通过 getUpdates 查看该群的 `chat.id`（通常为负数）。

### 配置示例

```yaml
push_channel:
  - name: Telegram机器人
    type: telegram_bot
    api_token: "123456789:ABCdefGHIxxxxxxxxxxxxxxxx"
    chat_id: "-1001234567890"
```

---

## QQ 频道机器人

通过 QQ 开放平台创建的机器人向指定频道发送消息。**支持图片**。需创建机器人并开通在频道内发言的权限。不推荐优先使用，需使用 app_secret 获取 AccessToken。

### 官方文档

- [QQ 开放平台 - 创建机器人](https://q.qq.com/#/app/create-bot)  
- [QQ 机器人文档](https://bot.q.qq.com/wiki/)

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `qq_bot` |
| `base_url` | 字符串 | 否 | 默认 `https://api.sgroup.qq.com` |
| `app_id` | 字符串 | ✅ | 机器人应用 App ID |
| `app_secret` | 字符串 | ✅ | 机器人应用 App Secret（用于获取 AccessToken） |
| `push_target_list` | 列表 | ✅ | 推送目标：`guild_name`（频道名）、`channel_name_list`（子频道名列表） |

### 如何获取

1. 打开 [QQ 机器人开放平台](https://q.qq.com/#/app/create-bot) 创建应用/机器人。  
2. 在应用管理中获取 **App ID**、**App Secret**。  
3. 将机器人在目标频道/子频道开通发言权限，填写对应的 **频道名称**、**子频道名称** 到 `push_target_list`。

### 配置示例

```yaml
push_channel:
  - name: QQ机器人
    type: qq_bot
    base_url: https://api.sgroup.qq.com
    app_id: "123456789"
    app_secret: "xxxxxxxxxxxxxxxx"
    push_target_list:
      - guild_name: "我的频道"
        channel_name_list:
          - "通知"
          - "日志"
```

---

## NapCatQQ

通过自建的 [NapCatQQ](https://github.com/NapNeko/NapCatQQ) 服务推送至 QQ 群/好友。**支持图片**。需自行部署 NapCatQQ。

### 官方文档

- [NapCatQQ 项目](https://github.com/NapNeko/NapCatQQ)

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `napcat_qq` |
| `api_url` | 字符串 | 否 | NapCat 服务地址，默认 `http://localhost:3000` |
| `token` | 字符串 | ✅ | NapCat 鉴权 token |
| `user_id` | 字符串 | 与 group_id 二选一 | 推送目标 QQ 号（私聊） |
| `group_id` | 字符串 | 与 user_id 二选一 | 推送目标群号 |
| `at_qq` | 字符串 | 否 | 群内 @ 的 QQ，如 `all` 表示 @全体 |

### 配置示例

```yaml
push_channel:
  - name: NapCatQQ
    type: napcat_qq
    api_url: http://localhost:3000
    token: "your_napcat_token"
    group_id: "123456789"
    at_qq: "all"
```

---

## Bark

向苹果设备上的 Bark App 推送。**不支持图片**。轻量、适合个人使用。

### 官方文档 / 应用

- [Bark App Store](https://apps.apple.com/cn/app/id1403753865)  
- 自建或使用公共服务器，如 `https://api.day.app`

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `bark` |
| `server_url` | 字符串 | 否 | Bark 服务器地址，默认 `https://api.day.app` |
| `key` | 字符串 | ✅ | Bark 设备 Key（App 内获取） |

### 如何获取 key

在 iPhone 上安装 Bark，打开 App 即可看到设备 Key（或扫码/URL 中的 key 参数）。

### 配置示例

```yaml
push_channel:
  - name: Bark
    type: bark
    server_url: https://api.day.app
    key: "xxxxxxxxxxxxxxxxxxxxxxxx"
```

---

## WxPusher

通过 [WxPusher](https://wxpusher.zjiecode.com/) 向微信推送消息。**支持图片**。需在 WxPusher 后台创建应用并绑定微信。

### 官方文档

- [WxPusher 官网](https://wxpusher.zjiecode.com/)  
- [WxPusher 文档](https://wxpusher.zjiecode.com/docs/)

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `wxpusher` |
| `app_token` | 字符串 | ✅ | 应用 Token（后台创建应用后获得） |
| `uids` | 字符串 | 与 topic_ids 二选一 | 用户 UID 列表，逗号分隔 |
| `topic_ids` | 字符串 | 与 uids 二选一 | 主题 ID 列表，逗号分隔 |
| `content_type` | 整数 | 否 | 1-文本，2-html，3-markdown，默认 1 |

### 如何获取

1. 登录 [WxPusher](https://wxpusher.zjiecode.com/)，创建应用，获取 **AppToken**。  
2. 用户扫码关注后可在后台看到 **UID**；或创建主题，用户订阅主题后使用 **Topic ID**。

### 配置示例

```yaml
push_channel:
  - name: WxPusher
    type: wxpusher
    app_token: "AT_xxxxxxxxxxxxxxxx"
    uids: "UID_xxx,UID_yyy"
    # topic_ids: "123,456"
    content_type: 1
```

---

## Server酱 Turbo（sct.ftqq.com）

通过 Server酱 Turbo 推送，免费版 5 次/天。**支持图片**。

### 官方文档

- [Server酱 Turbo 官网](https://sct.ftqq.com/)

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `serverChan_turbo` |
| `send_key` | 字符串 | ✅ | 在 sct.ftqq.com 后台获取的 SendKey |

### 配置示例

```yaml
push_channel:
  - name: Server酱_Turbo
    type: serverChan_turbo
    send_key: "SCTxxxxxxxxxxxxxxxx"
```

---

## Server酱 3（sc3.ft07.com）

需安装官方 App 接收推送。**支持图片**。

### 官方文档

- [Server酱 3 官网](https://sc3.ft07.com/)

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `serverChan_3` |
| `send_key` | 字符串 | ✅ | 后台 SendKey |
| `uid` | 字符串 | 否 | 用户 UID |
| `tags` | 字符串 | 否 | 标签等 |

### 配置示例

```yaml
push_channel:
  - name: Server酱_3
    type: serverChan_3
    send_key: "xxx"
    uid: ""
    tags: ""
```

---

## PushPlus

支持微信、邮件、Webhook、企业微信、短信等多种渠道。**支持图片**。

### 官方文档

- [PushPlus 官网](https://www.pushplus.plus/)

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `pushplus` |
| `token` | 字符串 | ✅ | 在 pushplus 后台获取的 token |
| `channel` | 字符串 | 否 | 推送渠道：wechat、mail、webhook、cp、sms 等，默认 wechat |
| `topic` | 字符串 | 否 | 群组代码，群组推送时使用 |
| `template` | 字符串 | 否 | html、txt、json、markdown 等，默认 html |
| `to` | 字符串 | 否 | 好友消息的接收者标识 |

### 配置示例

```yaml
push_channel:
  - name: PushPlus
    type: pushplus
    token: "xxxxxxxxxxxxxxxx"
    channel: wechat
    template: html
```

---

## Webhook

向任意 URL 发送 HTTP 请求，可带 `title`、`content` 等参数或 Body。**支持图片**（如 POST 带图片 URL）。通用集成方式。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `webhook` |
| `webhook_url` | 字符串 | ✅ | 请求 URL，支持占位符如 `{{title}}`、`{{content}}` |
| `request_method` | 字符串 | 否 | GET 或 POST，默认 GET |

### 配置示例

```yaml
push_channel:
  - name: Webhook
    type: webhook
    webhook_url: "https://your-server.com/notify?title={{title}}&content={{content}}"
    request_method: GET
```

---

## Gotify

自建 [Gotify](https://gotify.net/) 服务器接收推送。**不支持图片**。适合自建环境。

### 官方文档

- [Gotify 官网](https://gotify.net/)

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `gotify` |
| `web_server_url` | 字符串 | ✅ | Gotify 推送地址；若服务端要求 token，请将 token 写在 URL 中，如 `https://gotify.example.com/message?token=xxx` |

### 如何获取

自建 Gotify 服务后，在应用/客户端中创建 Application，获取推送 URL（含 token），完整填入 `web_server_url`。

### 配置示例

```yaml
push_channel:
  - name: Gotify
    type: gotify
    web_server_url: "https://gotify.example.com/message?token=your_app_token"
```

---

## 电子邮件

通过 SMTP 发送邮件。**支持图片**（如以附件或内嵌形式）。

### 配置项

| 配置项 | 类型 | 必填 | 说明 |
|:-------|:-----|:----:|:-----|
| `name` | 字符串 | ✅ | 通道名称，唯一 |
| `type` | 字符串 | ✅ | 固定为 `email` |
| `smtp_host` | 字符串 | ✅ | SMTP 服务器地址，如 `smtp.qq.com` |
| `smtp_port` | 整数 | ✅ | SMTP 端口，如 465、587 |
| `smtp_ssl` | 布尔 | 否 | 是否使用 SSL，默认 true |
| `smtp_tls` | 布尔 | 否 | 是否使用 STARTTLS，默认 false |
| `sender_email` | 字符串 | ✅ | 发件人邮箱 |
| `sender_password` | 字符串 | ✅ | 发件人密码或授权码 |
| `receiver_email` | 字符串 | ✅ | 收件人邮箱 |

### 配置示例（QQ 邮箱）

QQ 邮箱需在「设置 → 账户」中开启 SMTP 并生成**授权码**，用授权码作为 `sender_password`。

```yaml
push_channel:
  - name: Email
    type: email
    smtp_host: smtp.qq.com
    smtp_port: 465
    smtp_ssl: true
    smtp_tls: false
    sender_email: "your@qq.com"
    sender_password: "授权码"
    receiver_email: "receiver@example.com"
```

---

## 青龙 QLAPI（qlapi）

在 [青龙面板](https://github.com/whyour/qinglong) 中运行 `ql/*.py` 脚本时，系统会自动使用 `qlapi` 类型通道，调用 `QLAPI.systemNotify` 发送推送。该通道**由青龙环境自动注入**，用户无需在 `config.yml` 中配置；推送方式在青龙「系统设置 → 通知设置」中统一配置。非青龙环境下 `qlapi` 不可用，会静默跳过。

---

## 任务级通道选择

在任意监控或签到任务的配置中，可设置 **`push_channels`**（列表，元素为上述某通道的 `name`）：

- **为空**：使用全部已配置的推送通道。  
- **非空**：仅使用列出的通道，便于不同任务推送到不同群或应用。

示例：仅微博监控使用「钉钉机器人」，签到使用「企业微信机器人」：

```yaml
weibo:
  push_channels: [钉钉机器人]
tieba:
  push_channels: [企业微信机器人]
```
