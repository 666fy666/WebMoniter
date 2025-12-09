# Web监控系统

现代化的异步Web监控系统，支持虎牙直播和微博监控，并自动推送到企业微信。

## 特性

- ✅ 完全异步架构，高性能
- ✅ 企业微信推送频率限制保护
- ✅ 环境变量配置管理
- ✅ 使用uv进行依赖管理
- ✅ 类型提示和现代Python代码风格

## 安装

1. 安装uv（如果还没有）:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. 安装依赖:
```bash
uv sync
```

## 配置

1. 复制环境变量模板:
```bash
cp .env.example .env
```

2. 编辑`.env`文件，填入你的配置信息:
- 企业微信配置（corpid, secret, agentid等）
- 数据库配置（host, user, password等）
- 微博Cookie和UID列表
- 虎牙Cookie和房间号列表

## 使用

运行虎牙监控:
```bash
uv run python huya.py
```

运行微博监控:
```bash
uv run python weibo.py
```

## 企业微信推送频率限制

系统自动实现了企业微信推送的频率限制：
- 每分钟每个用户最多30次
- 每小时每个用户最多1000次
- 每天每个用户最多200次（可根据账号上限调整）

超过限制的推送会被自动阻止并记录日志。

## 项目结构

```
.
├── huya.py                # 虎牙监控入口（包含完整实现）
├── weibo.py               # 微博监控入口（包含完整实现）
├── src/
│   ├── config.py          # 配置管理
│   ├── database.py        # 异步数据库操作
│   └── push.py            # 企业微信推送（带频率限制）
├── pyproject.toml         # 项目配置
└── .env.example           # 环境变量模板
```

## 注意事项

1. 确保数据库表结构正确（huya表和weibo表）
2. 企业微信配置需要正确，否则推送会失败
3. 微博Cookie可能会过期，需要定期更新
4. 虎牙Cookie也可能需要更新

