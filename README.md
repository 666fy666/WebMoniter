# Web监控系统

现代化的异步Web监控系统，支持虎牙直播和微博监控，并自动推送到企业微信。

## 特性

- ✅ 完全异步架构，高性能
- ✅ 企业微信推送频率限制保护
- ✅ 环境变量配置管理
- ✅ 使用uv进行依赖管理
- ✅ 类型提示和现代Python代码风格
- ✅ 推送队列机制，自动重试失败任务
- ✅ 并发处理多个监控目标

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

### 必需配置项

**企业微信配置:**
- `WECHAT_CORPID`: 企业ID
- `WECHAT_SECRET`: 应用密钥
- `WECHAT_AGENTID`: 应用ID
- `WECHAT_TOUSER`: 接收消息的用户ID（多个用户用`|`分隔，如：`user1|user2`）

**数据库配置:**
- `DB_HOST`: 数据库主机地址
- `DB_PORT`: 数据库端口（默认3306）
- `DB_USER`: 数据库用户名
- `DB_PASSWORD`: 数据库密码
- `DB_NAME`: 数据库名称

**微博配置:**
- `WEIBO_COOKIE`: 微博Cookie（从浏览器开发者工具中获取）
- `WEIBO_UIDS`: 要监控的微博用户UID列表（逗号分隔，如：`123456789,987654321`）

**虎牙配置:**
- `HUYA_USER_AGENT`: 浏览器User-Agent
- `HUYA_COOKIE`: 虎牙Cookie（可选，但建议配置）
- `HUYA_ROOMS`: 要监控的房间号列表（逗号分隔，如：`123456,789012`）

### 可选配置项

- `WEIBO_CONCURRENCY`: 微博监控并发数（默认3，建议2-5，避免触发限流）
- `HUYA_CONCURRENCY`: 虎牙监控并发数（默认7，建议5-10，相对宽松）
- `WECHAT_PUSHPLUS`: PushPlus推送Token（备用推送方式）
- `WECHAT_EMAIL`: 邮箱地址（备用推送方式）
- `CONFIG_JSON_URL`: 远程配置JSON URL（用于动态加载配置）

## 使用

### 运行虎牙监控

```bash
uv run python huya.py
```

### 运行微博监控

```bash
uv run python weibo.py
```

### 定时任务配置（Ubuntu Cron）

本项目提供了完整的cron定时任务配置方案，推荐使用自动安装脚本。

#### 方法一：使用自动安装脚本（推荐）

1. **运行安装脚本**:
```bash
cd /home/fengyu/WebMoniter
bash scripts/setup_cron.sh
```

脚本会自动：
- 检测项目路径
- 创建包装脚本（确保环境变量和路径正确）
- 配置cron定时任务
- 设置日志文件目录

2. **验证安装**:
```bash
# 查看crontab配置
crontab -l
```

应该看到类似以下内容：
```
# Web监控系统定时任务
# 虎牙直播监控 - 每2分钟执行一次
*/2 * * * * /home/fengyu/WebMoniter/scripts/run_huya.sh

# 微博监控 - 每5分钟执行一次
*/5 * * * * /home/fengyu/WebMoniter/scripts/run_weibo.sh

# 日志清理 - 每天凌晨2点执行，删除超过3天的日志文件
0 2 * * * /home/fengyu/WebMoniter/scripts/cleanup_logs.sh
```

```bash
# 检查cron服务状态
systemctl status cron

# 查看cron执行日志
grep CRON /var/log/syslog | tail -20

# 或者使用journalctl（systemd系统）
journalctl -u cron | tail -20
```

#### 方法二：手动配置

如果选择手动配置，请按以下步骤操作：

1. **创建包装脚本**（已提供在`scripts/`目录）:
   - `scripts/run_huya.sh` - 虎牙监控包装脚本
   - `scripts/run_weibo.sh` - 微博监控包装脚本

2. **确保脚本有执行权限**:
```bash
chmod +x scripts/run_huya.sh scripts/run_weibo.sh
```

3. **编辑crontab**:
```bash
crontab -e
```

4. **添加以下内容**（请将路径替换为实际项目路径）:
```bash
# Web监控系统定时任务
# 虎牙直播监控 - 每2分钟执行一次
*/2 * * * * /home/fengyu/WebMoniter/scripts/run_huya.sh

# 微博监控 - 每5分钟执行一次
*/5 * * * * /home/fengyu/WebMoniter/scripts/run_weibo.sh
```

#### Cron时间格式说明

```
* * * * * 命令
│ │ │ │ │
│ │ │ │ └─── 星期几 (0-7, 0和7都表示星期日)
│ │ │ └───── 月份 (1-12)
│ │ └─────── 日期 (1-31)
│ └───────── 小时 (0-23)
└─────────── 分钟 (0-59)
```

**常用示例**:
- `*/2 * * * *` - 每2分钟执行一次
- `*/5 * * * *` - 每5分钟执行一次
- `0 */1 * * *` - 每小时执行一次
- `0 9 * * *` - 每天上午9点执行一次

#### 日志管理

所有监控任务的日志都会自动保存到`logs/`目录：
- 虎牙监控日志: `logs/huya_YYYYMMDD.log`（按日期分割）
- 微博监控日志: `logs/weibo_YYYYMMDD.log`（按日期分割）
- 清理日志: `logs/cleanup.log`（记录日志清理操作）

**查看日志**:
```bash
# 查看今天的虎牙监控日志
tail -f logs/huya_$(date +%Y%m%d).log

# 查看今天的微博监控日志
tail -f logs/weibo_$(date +%Y%m%d).log

# 查看最近的错误日志
grep -i error logs/*.log | tail -20

# 查看日志清理记录
tail -f logs/cleanup.log
```

**自动日志清理**:
- 系统会自动删除超过3天的日志文件
- 清理任务每天凌晨2点自动执行
- 清理操作会记录到`logs/cleanup.log`文件中
- 如需手动清理，可执行：`bash scripts/cleanup_logs.sh`

**修改清理策略**：
如果需要修改清理天数，编辑`scripts/cleanup_logs.sh`文件，修改`-mtime +3`中的数字（3表示3天）。

#### 常见问题排查

##### 问题1：任务未执行

**检查步骤**：
1. 确认cron服务运行：`systemctl status cron`
2. 启动cron服务：`sudo systemctl start cron`
3. 查看cron日志：`grep CRON /var/log/syslog`
4. 检查crontab配置：`crontab -l`

##### 问题2：脚本执行失败

**常见错误：`uv: 未找到命令`**

这是cron环境变量问题，脚本已自动修复。如果仍出现此问题：

1. **检查uv安装位置**：
   ```bash
   which uv
   ```

2. **如果uv不在`/home/fengyu/.local/bin`**，需要修改脚本中的PATH设置：
   ```bash
   # 编辑脚本，修改PATH设置
   vim scripts/run_weibo.sh
   # 将 /home/fengyu/.local/bin 替换为你的uv实际路径
   ```

3. **手动执行脚本测试**：
   ```bash
   bash scripts/run_huya.sh
   bash scripts/run_weibo.sh
   ```

4. **其他检查步骤**：
   - 检查脚本权限：`ls -l scripts/*.sh`
   - 检查路径是否正确（使用绝对路径）
   - 查看日志文件中的错误信息
   - 确认`.env`文件存在且配置正确

##### 问题3：环境变量未加载

**解决方案**：
- 包装脚本会自动切换到项目目录
- `uv run`会自动加载`.env`文件
- 如果仍有问题，检查`.env`文件路径和格式

##### 问题4：权限问题

**解决方案**：
```bash
# 添加执行权限
chmod +x scripts/*.sh

# 确保日志目录可写
mkdir -p logs
chmod 755 logs
```

#### 手动配置（高级）

如果需要自定义执行时间，可以手动编辑crontab：

```bash
crontab -e
```

**Cron时间格式**：
```
分钟 小时 日期 月份 星期 命令
```

**常用时间示例**：
- `*/2 * * * *` - 每2分钟
- `*/5 * * * *` - 每5分钟
- `*/10 * * * *` - 每10分钟
- `0 */1 * * *` - 每小时
- `0 9 * * *` - 每天9点
- `0 9 * * 1` - 每周一9点

#### 卸载Cron任务

##### 方法1：编辑crontab删除
```bash
crontab -e
# 删除相关行后保存
```

##### 方法2：完全删除（谨慎）
```bash
crontab -r  # 删除所有crontab任务
```

#### Cron最佳实践

1. **定期检查日志**：确保监控任务正常运行
2. **监控磁盘空间**：日志文件会持续增长，系统已自动清理超过3天的日志
3. **备份配置**：定期备份`.env`和crontab配置
4. **测试脚本**：修改配置后先手动测试脚本是否正常
5. **查看清理记录**：定期查看`logs/cleanup.log`了解日志清理情况

## 功能实现详解

### 1. 微博监控功能

#### 核心功能
- **用户信息监控**: 监控指定微博用户的个人信息（用户名、认证信息、简介、粉丝数、微博数）
- **微博内容监控**: 检测用户最新发布的微博内容
- **变更检测**: 通过对比数据库中的历史数据，检测以下变化：
  - 新发布的微博（通过微博数增加判断）
  - 删除的微博（通过微博数减少判断）
  - 用户信息更新

#### 实现原理
1. **并发控制**: 使用`asyncio.Semaphore`控制同时处理的用户数量，默认并发数为3（可通过`WEIBO_CONCURRENCY`配置，建议2-5），避免触发微博API限流
2. **数据获取**: 并发请求两个API接口
   - 用户信息接口: `https://www.weibo.com/ajax/profile/info?uid={uid}`
   - 微博列表接口: `https://www.weibo.com/ajax/statuses/mymblog?uid={uid}&page=1&feature=0`
3. **内容解析**: 
   - 提取用户基本信息（UID、用户名、认证信息、简介、粉丝数、微博数）
   - 解析最新微博内容（跳过置顶微博，获取第一条非置顶微博）
   - 处理图片、链接等富媒体内容
4. **变更检测**: 
   - 对比当前微博数与历史记录
   - 计算差值判断新增或删除的微博数量
   - 对比微博文本内容（mid）判断是否有新微博
5. **数据存储**: 使用MySQL存储监控数据，支持新增和更新操作

#### 操作流程

```
开始监控
  ↓
加载数据库中的历史数据
  ↓
创建并发控制信号量（默认并发数：3）
  ↓
并发处理所有监控的UID（受信号量限制）
  ├─→ 获取用户信息和最新微博
  ├─→ 解析数据（用户信息 + 微博内容）
  ├─→ 与数据库历史数据对比
  │   ├─→ 新用户 → 插入数据库 → 发送推送
  │   ├─→ 有变化 → 更新数据库 → 发送推送
  │   └─→ 无变化 → 跳过
  └─→ 记录处理结果
  ↓
关闭资源（数据库连接、HTTP会话）
  ↓
结束
```

### 2. 虎牙直播监控功能

#### 核心功能
- **直播状态监控**: 实时检测指定房间的直播状态（开播/下播）
- **主播信息获取**: 获取主播昵称等基本信息
- **状态变更通知**: 当直播状态发生变化时自动推送通知

#### 实现原理
1. **并发控制**: 使用`asyncio.Semaphore`控制同时处理的房间数量，默认并发数为7（可通过`HUYA_CONCURRENCY`配置，建议5-10），相对宽松的并发设置
2. **页面抓取**: 访问虎牙移动端页面 `https://m.huya.com/{room_id}`
3. **数据提取**: 使用正则表达式从页面HTML中提取：
   - 主播信息: `"tProfileInfo":{...}`
   - 直播状态: `"eLiveStatus":2` (2表示正在直播，其他值表示未开播)
4. **状态转换**: 
   - `eLiveStatus == 2` → 存储为 `is_live = "1"` (开播)
   - 其他值 → 存储为 `is_live = "0"` (下播)
5. **变更检测**: 对比当前状态与数据库中的历史状态

#### 操作流程

```
开始监控
  ↓
加载数据库中的历史数据
  ↓
创建并发控制信号量（默认并发数：7）
  ↓
并发处理所有监控的房间号（受信号量限制）
  ├─→ 访问虎牙移动端页面
  ├─→ 使用正则表达式提取数据
  ├─→ 解析主播信息和直播状态
  ├─→ 与数据库历史数据对比
  │   ├─→ 新房间 → 插入数据库 → 发送推送
  │   ├─→ 状态变化 → 更新数据库 → 发送推送
  │   │   ├─→ 开播 → 推送开播通知
  │   │   └─→ 下播 → 推送下播通知
  │   └─→ 无变化 → 跳过
  └─→ 记录处理结果
  ↓
关闭资源（数据库连接、HTTP会话）
  ↓
结束
```

### 3. 企业微信推送功能

#### 核心功能
- **图文消息推送**: 支持发送包含标题、描述、图片、链接的图文消息
- **频率限制保护**: 自动实现企业微信API的频率限制
- **推送队列**: 当推送被频率限制阻止时，自动加入队列稍后发送
- **自动重试**: 推送失败时自动重试（最多3次）

#### 频率限制规则
- **每分钟限制**: 每个用户最多30次
- **每小时限制**: 每个用户最多1000次
- **每天限制**: 每个用户最多200次（可根据账号上限调整）

#### 实现原理
1. **Token管理**: 
   - 自动获取和刷新企业微信access_token
   - Token有效期7200秒，提前5分钟刷新
2. **频率限制器**:
   - 维护每个用户的时间戳记录（分钟/小时/天）
   - 自动清理过期记录
   - 发送前检查是否超过限制
3. **推送队列**:
   - 使用asyncio.Queue管理待发送任务
   - 后台异步处理队列中的任务
   - 失败任务自动重试（最多3次，间隔5秒）
4. **多用户支持**: 支持同时向多个用户推送（用`|`分隔）

#### 推送流程

```
发送推送请求
  ↓
检查频率限制（每个用户）
  ├─→ 超过限制 → 加入推送队列 → 返回
  └─→ 未超过限制 → 继续
  ↓
获取/刷新access_token
  ↓
构建推送消息（图文消息格式）
  ↓
发送HTTP POST请求到企业微信API
  ├─→ 成功 → 记录发送时间 → 返回结果
  └─→ 失败 → 抛出异常
       ├─→ 频率限制 → 加入队列
       └─→ 其他错误 → 记录日志
```

#### 队列处理流程

```
队列处理器启动（后台任务）
  ↓
循环处理队列
  ├─→ 从队列获取任务（超时2秒）
  ├─→ 尝试发送推送
  │   ├─→ 成功 → 标记完成
  │   └─→ 失败 → 增加重试次数
  │       ├─→ 未达最大重试次数 → 等待5秒 → 重新入队
  │       └─→ 已达最大重试次数 → 丢弃任务
  └─→ 继续处理下一个任务
```

### 4. 数据库操作

#### 核心功能
- **异步连接池**: 使用aiomysql实现异步MySQL连接池
- **连接管理**: 自动管理连接池的创建和关闭
- **事务支持**: 支持事务提交和回滚
- **上下文管理**: 支持async with语法

#### 实现原理
1. **连接池配置**:
   - 最小连接数: 1
   - 最大连接数: 10
   - 字符集: utf8mb4
   - 自动提交: 关闭（手动控制事务）
2. **操作封装**:
   - `execute_query`: 执行SELECT查询
   - `execute_update`: 执行UPDATE操作
   - `execute_insert`: 执行INSERT操作
   - `execute_delete`: 执行DELETE操作

## 数据模型

### 数据库表结构

#### 1. weibo表（微博监控数据）

| 字段名 | 类型 | 说明 | 约束 |
|--------|------|------|------|
| UID | VARCHAR | 微博用户UID | PRIMARY KEY |
| 用户名 | VARCHAR | 用户昵称 | NOT NULL |
| 认证信息 | VARCHAR | 认证信息（如：人气博主） | |
| 简介 | TEXT | 用户简介 | |
| 粉丝数 | VARCHAR | 粉丝数量（字符串格式，如：1.2万） | |
| 微博数 | VARCHAR | 微博总数 | |
| 文本 | TEXT | 最新微博内容 | |
| mid | VARCHAR | 最新微博的mid（用于生成链接） | |

**创建表SQL:**
```sql
CREATE TABLE IF NOT EXISTS `weibo` (
  `UID` VARCHAR(50) PRIMARY KEY COMMENT '微博用户UID',
  `用户名` VARCHAR(100) NOT NULL COMMENT '用户昵称',
  `认证信息` VARCHAR(200) DEFAULT '' COMMENT '认证信息',
  `简介` TEXT COMMENT '用户简介',
  `粉丝数` VARCHAR(50) DEFAULT '0' COMMENT '粉丝数量',
  `微博数` VARCHAR(50) DEFAULT '0' COMMENT '微博总数',
  `文本` TEXT COMMENT '最新微博内容',
  `mid` VARCHAR(50) DEFAULT '0' COMMENT '最新微博mid'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='微博监控数据表';
```

#### 2. huya表（虎牙直播监控数据）

| 字段名 | 类型 | 说明 | 约束 |
|--------|------|------|------|
| room | VARCHAR | 房间号 | PRIMARY KEY |
| name | VARCHAR | 主播昵称 | NOT NULL |
| is_live | VARCHAR(1) | 直播状态（"1"=开播，"0"=下播） | DEFAULT '0' |

**创建表SQL:**
```sql
CREATE TABLE IF NOT EXISTS `huya` (
  `room` VARCHAR(50) PRIMARY KEY COMMENT '房间号',
  `name` VARCHAR(100) NOT NULL COMMENT '主播昵称',
  `is_live` VARCHAR(1) DEFAULT '0' COMMENT '直播状态：1=开播，0=下播'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='虎牙直播监控数据表';
```

### 数据流转

#### 微博监控数据流

```
微博API
  ↓
解析JSON数据
  ↓
构建数据字典
  {
    "UID": "...",
    "用户名": "...",
    "认证信息": "...",
    "简介": "...",
    "粉丝数": "...",
    "微博数": "...",
    "文本": "...",
    "mid": "..."
  }
  ↓
对比数据库历史数据
  ↓
决定操作（INSERT/UPDATE/跳过）
  ↓
更新数据库
  ↓
触发推送（如有变化）
```

#### 虎牙监控数据流

```
虎牙页面HTML
  ↓
正则表达式提取
  ↓
解析JSON数据
  ↓
构建数据字典
  {
    "room": "...",
    "name": "...",
    "is_live": "1" or "0"
  }
  ↓
对比数据库历史数据
  ↓
决定操作（INSERT/UPDATE/跳过）
  ↓
更新数据库
  ↓
触发推送（如状态变化）
```

## 企业微信推送频率限制

系统自动实现了企业微信推送的频率限制：
- **每分钟限制**: 每个用户最多30次
- **每小时限制**: 每个用户最多1000次
- **每天限制**: 每个用户最多200次（可根据账号上限调整）

### 限制机制

1. **自动检测**: 每次发送前自动检查是否超过限制
2. **队列缓冲**: 超过限制的推送自动加入队列，稍后发送
3. **自动重试**: 队列中的任务失败后自动重试（最多3次）
4. **日志记录**: 所有被限制的推送都会记录日志

### 调整限制

如需调整限制值，编辑 `src/push.py` 中的 `RateLimiter` 类：

```python
self.MINUTE_LIMIT = 30   # 修改分钟限制
self.HOUR_LIMIT = 1000   # 修改小时限制
self.DAY_LIMIT = 200     # 修改天限制
```

## 项目结构

```
.
├── huya.py                # 虎牙监控入口（包含完整实现）
├── weibo.py               # 微博监控入口（包含完整实现）
├── src/
│   ├── __init__.py        # 包初始化文件
│   ├── config.py          # 配置管理（环境变量、Pydantic验证）
│   ├── database.py        # 异步数据库操作（连接池、CRUD）
│   └── push.py            # 企业微信推送（频率限制、队列）
├── scripts/               # Cron定时任务脚本目录
│   ├── run_huya.sh        # 虎牙监控包装脚本
│   ├── run_weibo.sh       # 微博监控包装脚本
│   ├── setup_cron.sh      # Cron任务自动安装脚本
│   └── cleanup_logs.sh    # 日志清理脚本
├── logs/                  # 日志文件目录（自动创建）
├── pyproject.toml         # 项目配置和依赖管理
├── uv.lock                # 依赖锁定文件（必须提交到git）
└── .env.example           # 环境变量模板
```

## 脚本说明

`scripts/` 目录包含用于cron定时任务的包装脚本和安装脚本。

### 脚本文件说明

#### `run_huya.sh`
虎牙监控的包装脚本，用于cron定时任务执行。
- 自动切换到项目目录
- 自动创建日志目录
- 设置PATH环境变量，确保能找到`uv`命令
- 使用`uv run`执行，确保环境变量正确加载
- 日志输出到`logs/huya_YYYYMMDD.log`
- 检查`uv`命令是否可用，失败时记录错误

#### `run_weibo.sh`
微博监控的包装脚本，用于cron定时任务执行。
- 自动切换到项目目录
- 自动创建日志目录
- 设置PATH环境变量，确保能找到`uv`命令
- 使用`uv run`执行，确保环境变量正确加载
- 日志输出到`logs/weibo_YYYYMMDD.log`
- 检查`uv`命令是否可用，失败时记录错误

#### `setup_cron.sh`
Cron定时任务自动安装脚本。
- 自动检测项目路径
- 为所有脚本添加执行权限
- 配置cron定时任务（虎牙每2分钟，微博每5分钟，日志清理每天凌晨2点）
- 备份现有crontab配置
- 避免重复添加任务
- 显示安装结果和验证方法

#### `cleanup_logs.sh`
日志清理脚本，用于自动删除旧日志文件。
- 自动删除超过3天的日志文件
- 记录清理操作到`logs/cleanup.log`
- 自动清理cleanup.log本身（超过30天）
- 统计删除的文件数量

### 脚本使用方法

#### 安装cron任务
```bash
bash scripts/setup_cron.sh
```

#### 手动执行测试
```bash
# 测试虎牙监控脚本
bash scripts/run_huya.sh

# 测试微博监控脚本
bash scripts/run_weibo.sh

# 手动执行日志清理
bash scripts/cleanup_logs.sh
```

#### 查看日志
```bash
# 查看今天的虎牙监控日志
tail -f logs/huya_$(date +%Y%m%d).log

# 查看今天的微博监控日志
tail -f logs/weibo_$(date +%Y%m%d).log

# 查看日志清理记录
tail -f logs/cleanup.log
```

### 脚本注意事项

1. **环境变量**：确保`.env`文件存在于项目根目录
2. **uv安装**：确保已安装`uv`并配置好Python环境
3. **路径设置**：脚本使用绝对路径，确保cron执行时路径正确
4. **日志管理**：日志文件按日期分割，方便管理和查看
5. **自动清理**：日志清理任务会自动配置，每天凌晨2点执行，删除超过3天的日志文件
6. **PATH问题**：如果`uv`不在`/home/fengyu/.local/bin`，需要修改脚本中的PATH设置

## 技术栈

- **Python 3.10+**: 使用现代Python特性（类型提示、async/await）
- **aiohttp**: 异步HTTP客户端，用于API请求和页面抓取
- **aiomysql**: 异步MySQL客户端，实现数据库连接池
- **pydantic**: 数据验证和配置管理
- **uv**: 快速的Python包管理器和项目管理工具

## 注意事项

1. **数据库表结构**: 确保数据库表结构正确（参考上面的SQL语句）
2. **企业微信配置**: 企业微信配置需要正确，否则推送会失败
   - 确保corpid、secret、agentid正确
   - 确保touser中的用户ID存在且有权限接收消息
3. **Cookie管理**: 
   - 微博Cookie可能会过期，需要定期更新（建议每月检查一次）
   - 虎牙Cookie也可能需要更新（建议每季度检查一次）
4. **网络环境**: 确保服务器能够访问：
   - 微博API: `https://www.weibo.com`
   - 虎牙网站: `https://m.huya.com`
   - 企业微信API: `https://qyapi.weixin.qq.com`
   - 一言API: `https://v1.hitokoto.cn`（虎牙推送时获取语录）
5. **性能优化**: 
   - 系统使用异步并发处理，可以同时监控多个目标
   - 通过信号量（Semaphore）控制并发数，避免触发API限流
   - 微博监控默认并发数为3（建议2-5），虎牙监控默认并发数为7（建议5-10）
   - 可根据实际情况在`.env`文件中调整`WEIBO_CONCURRENCY`和`HUYA_CONCURRENCY`配置
   - 数据库使用连接池，避免频繁创建连接
   - HTTP请求使用连接复用，提高性能
6. **错误处理**: 
   - 所有异常都会被捕获并记录日志
   - 推送失败会自动重试
   - 数据库操作失败会自动回滚

## 故障排查

### 推送失败

1. **检查企业微信配置**: 确认corpid、secret、agentid正确
2. **检查Token**: 查看日志中是否有token获取失败的错误
3. **检查频率限制**: 查看日志中是否有频率限制的提示
4. **检查网络**: 确认服务器能访问企业微信API

### 监控数据获取失败

1. **检查Cookie**: 确认Cookie是否过期（尝试在浏览器中访问对应网站）
2. **检查网络**: 确认服务器能访问目标网站
3. **检查UID/房间号**: 确认配置的UID或房间号是否正确
4. **查看日志**: 查看具体的错误信息

### 数据库连接失败

1. **检查配置**: 确认数据库配置（host、port、user、password、db）正确
2. **检查网络**: 确认服务器能访问数据库
3. **检查权限**: 确认数据库用户有足够的权限（SELECT、INSERT、UPDATE）
4. **检查表结构**: 确认表结构是否正确（参考上面的SQL语句）

## 开发指南

### 添加新的监控源

1. 在`src/config.py`中添加新的配置类
2. 创建新的监控脚本（参考`weibo.py`或`huya.py`）
3. 实现监控逻辑（数据获取、解析、对比、推送）
4. 在数据库中创建对应的表

### 扩展推送方式

1. 在`src/push.py`中添加新的推送方法
2. 在配置中添加对应的配置项
3. 在监控脚本中调用新的推送方法

## 许可证

本项目采用 MIT 许可证。
