# AI 助手

AI 助手通过 RAG（检索增强生成）+ LLM 为 WebMoniter 提供智能对话能力，支持配置生成、日志诊断、数据洞察与当前状态查询。

## 入口

在**配置管理**、**任务管理**、**数据展示**页面底部有悬浮「问 AI」按钮，点击后弹出对话窗口。

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
  api_base: ""        # 留空使用 provider 默认；ollama 为 http://localhost:11434/v1
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
