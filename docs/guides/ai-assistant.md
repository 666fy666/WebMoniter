# AI 助手

AI 助手通过 RAG（检索增强生成）+ LLM 为 WebMoniter 提供智能对话能力，支持配置生成、日志诊断、数据洞察与当前状态查询。

## 入口

- **Web 界面**：在**配置管理**、**任务管理**、**数据展示**页面底部有悬浮「问 AI」按钮
- **推送平台**：支持在企业微信、Telegram 等具备交互能力的推送渠道中与 AI 对话

## 平台交互接入

以下推送渠道支持接收用户消息并回复 AI 助手，可在对应应用中直接对话：

| 平台 | 配置项 | Webhook URL | 说明 |
|------|--------|-------------|------|
| 企业微信自建应用 | `callback_token`、`encoding_aes_key` | `{base_url}/api/webhooks/wecom` | 在企业微信后台「接收消息」配置 URL；参考 [企业微信文档](https://developer.work.weixin.qq.com/document/path/90238) |
| Telegram 机器人 | `api_token` | `{base_url}/api/webhooks/telegram/{通道名}` | 调用 `setWebhook` 设置 URL；参考 [Telegram 文档](https://core.telegram.org/bots/api) |

> 仅支持推送的渠道（钉钉群机器人、飞书群机器人、Bark、WxPusher 等）无需修改，保持原有单向推送即可。

### 企业微信应用接入步骤

1. 在 `config.yml` 的 `push_channel` 中，为对应企业微信应用补充：
   - `callback_token`：企业微信后台「我的企业」→「接收消息」中配置的 Token
   - `encoding_aes_key`：同上，EncodingAESKey（43 字符）
   - `corp_id`、`corp_secret`、`agent_id`：与推送配置相同，用于异步回复（被动回复 5 秒超时，AI 通过 API 主动推送）
2. 在企业微信管理后台「应用管理」→ 选择应用 →「接收消息」中：
   - URL 填：`https://你的域名/api/webhooks/wecom`
   - Token、EncodingAESKey 与 config.yml 中保持一致
3. 保存后，成员在企业微信中向该应用发送文字即可与 AI 对话

### Telegram 接入步骤

1. 在 `config.yml` 中配置 `telegram_bot` 通道的 `api_token`、`chat_id`
2. 调用 Telegram API 设置 Webhook（将 `通道名` 替换为 config 中的 name，如「Telegram机器人」需 URL 编码）：
   ```
   https://api.telegram.org/bot<api_token>/setWebhook?url=https://你的域名/api/webhooks/telegram/通道名
   ```
3. 用户向该机器人发送消息即可与 AI 对话

## 会话管理

- **新建对话**：点击「新建」按钮创建新会话
- **切换会话**：在顶部会话列表中点击不同会话切换
- **删除会话**：点击会话旁的 × 按钮，确认后即删除

会话与消息会持久化到 `data/ai_assistant_conversations.json`，刷新或重启后仍可继续对话。

## 支持的问题类型

| 类型 | 示例 |
|------|------|
| 配置生成 | 「我想每天 8 点签 iKuuu，推送到企业微信」 |
| 日志诊断 | 「微博监控最近报错了吗」「有什么失败」 |
| 数据洞察 | 「最近谁开播了」「本周谁开播最频繁」「最近谁发博最多」 |
| 当前状态 | 「虎牙谁在直播」「B站和抖音最新状态」「谁正在直播」 |
| 可执行操作 | 「关闭抖音监控」「开启虎牙监控」「把微博关掉」— 识别后弹出确认弹窗，确认即可执行（修改 config 并热重载） |
| 配置列表增删 | 「删除虎牙主播100」「添加虎牙房间200」「移除B站用户xxx」「加入抖音yyy」— 识别后弹出确认弹窗，确认即可自动修改 config.yml 并热重载 |

## 配置说明

在 `config.yml` 中增加 `ai_assistant` 节点：

```yaml
ai_assistant:
  enable: true
  provider: deepseek  # openai | deepseek | qwen | zhipu | moonshot | ollama | openai_compatible
  api_base: ""        # 留空使用 provider 默认；ollama 为 http://localhost:11434/v1；openai_compatible 时必填
  api_key: ""         # 或设置环境变量 AI_ASSISTANT_API_KEY
  model: deepseek-chat
  embedding_model: text-embedding-3-small
  chroma_persist_dir: data/ai_assistant_chroma
  rag_index_refresh_interval_seconds: 1800  # 向量库更新间隔（秒），默认 30 分钟
  rate_limit_per_minute: 10
  max_history_rounds: 10
```

### 主流厂商 api_base 示例

| 厂商 | api_base |
|------|----------|
| OpenAI | https://api.openai.com/v1 |
| DeepSeek | https://api.deepseek.com |
| 通义千问 | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| 智谱 GLM | https://open.bigmodel.cn/api/paas/v4 |
| Moonshot | https://api.moonshot.cn/v1 |
| Ollama | http://localhost:11434/v1 |

## 安装依赖

```bash
uv sync --extra ai
```

需安装 `openai`、`httpx`、`chromadb`（可选，用于向量检索）。

**数据来源**：AI 检索时使用
- **文档**：`docs/*.md` 与 `README.md`，存入 Chroma 向量库，每 30 分钟自动重建（可通过 `rag_index_refresh_interval_seconds` 配置）
- **配置**：`config.yml.sample` 模板 + 实际 `config.yml`（敏感字段如 cookie、api_key 会自动脱敏）
- **日志**：`logs/main_*.log` 最近 500 行，支持中文关键词（开播、发博等）的智能匹配

## 配置建议的应用

当 AI 返回配置相关的 YAML 片段时，会显示「复制配置」按钮。复制后可在配置管理的 YAML 视图中粘贴并保存。
