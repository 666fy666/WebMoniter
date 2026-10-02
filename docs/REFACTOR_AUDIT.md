# 全栈重构审查与验收记录

日期：2026-10-02。范围：全新部署，保留 7 类监控、31 类任务（含维护与示例任务）、18 个推送适配器、MySQL 与青龙。实现与短时本地验证已完成；真实平台综合负载、arm64 实机、真实手机和 24 小时长测尚未完成，不能据此宣称全部验收通过。未修改真实服务器、未执行真实签到、未推送镜像。

## 审查证据与处理

| 优先级 | 原问题／证据 | 实施结果 |
|---|---|---|
| P0 | 普通 SHA-256 摘要 | Argon2id、失败关闭、登录限流、CSRF、会话轮换；按当前部署偏好默认 admin/123，环境覆盖可选 |
| P0 | 手动接口等待任务完成；手动与定时未共用并发限制 | `/api/v1` 提交返回 202；4 worker、100 队列、任务去重，SQLite 持久运行记录 |
| P0 | 浏览器/OCR 主进程驻留；默认线程池 32 | 账号级子进程按需导入，浏览器并发 1、180 秒尝试超时、进程组回收，线程池 4 |
| P1 | 两套 CSS 共 9,404 行；配置 JS 3,321 行 | 删除旧模板和叠加样式；Vue 路由组件、Pinia、类型化 API、统一材质与字段组件 |
| P1 | 配置明文读取、无版本保护 | 默认遮蔽、密钥保留标记、分区保存、冲突 409、显式 YAML 查看，不持久缓存凭据 |
| P1 | 列表/日志缺少上限，微博扫描正文排序 | 页大小 50/200，日志 1,000 行/256 KiB 游标，图片批量上限 200，微博时间入库索引 |
| P1 | 容器 root 与递归 chmod 777 | UID/GID 10001、必要目录检查、命名卷、init、健康检查与资源限制 |
| P1 | 模型和浏览器体积难区分 | 共享构建阶段、依赖裁剪与导入检查、模型保留校验、OCI 压缩/展开层报告 |
| P2 | 文档仍写旧 API、弱口令、旧 Dockerfile | 更新 API、架构、安装、服务器部署、开发与界面文档；翻译版标记更新状态 |

回归中实际发现并修复：配置加载忽略容器环境路径、模型文件非 root 不可读、Cookie 刷新开关和时间被错误遮蔽。裁剪数值库 ELF 调试符号曾破坏 NumPy/OpenBLAS 加载，已将 auditwheel `.libs`、NumPy、OpenCV、ONNX Runtime 排除在 strip 之外，并增加构建时导入检查。不是所有 `.so` 都可安全一刀切裁剪。

SQLite WAL、配置原子写入、压缩、缓存、OCR 单线程以及 MySQL 权威写入／镜像／outbox 回退顺序保留。媒体图片仍可被推送渠道读取，管理 API 统一鉴权；旧无界监控状态 API 不再挂载。

## 功能与回归

| 验证 | 结果／边界 |
|---|---|
| Python 全套 | 381 项通过；含注册完整性、配置映射、平台关键行为、推送、MySQL 回退、安全与执行服务 |
| 前端 | TypeScript、Prettier、Vitest 3 项、Vite 生产构建通过 |
| Playwright | 桌面／移动端 9 项通过；移动端 CDP 专用性能项按设计跳过 1 项 |
| 视觉 | 深色账户桌面／移动端截图基线比较；概览、任务、配置、日志保存截图人工检查 |
| 调度 | 手动/定时同任务合并、容量上限、终态、重启中断、不重放、最近任务记录 |
| 浏览器 | 模拟超时杀进程组、异常类型隔离、雨云超时重试；full 镜像本地浏览器与所有模型加载 |
| 配置 | 账号重排后密钥保留、清除、跨分区保留、版本冲突、嵌套敏感头遮蔽、开关与时间不遮蔽 |
| 日志 | 增量追加、半行等待、截断轮转、字节上限、保留活动文件的总量清理 |

外部平台副作用通过模拟测试验证；不保证外部平台当前在线、验证码识别率或真实账号成功率。青龙沿用原有单次 CLI，Web 统一队列限制不跨不同容器／青龙进程共享。

此前 aiosqlite 测试超时在独立内存查询中同样出现；在允许异步线程正常工作的执行环境中，完整测试约 2.5 秒完成。该现象不能归因于业务 SQLite 查询。

## 前端体验与性能

生产全部 JS/CSS gzip 合计约 **67.3 KiB**，包括所有懒加载页面，低于首屏 250 KiB 预算。使用系统字体、代码内 SVG 图标，无新增远程字体、分析服务或持续全屏渲染。CSS 高光、柔和粉紫材质与弹性过渡属于 Web 近似效果；表单和日志优先可读性。

本次冷加载 LCP **884 ms**，CLS **0.00965**。性能测试使用 Chromium、1440×1000、5 Mbps、100 ms 延迟、4 倍 CPU 降速，禁用浏览器缓存。LCP 与 CLS 数据保存在 `assets/validation/refactor-web-vitals.json`。这是本地测试后端上的单次实验室测量，不等同于真实手机 INP 或生产网络分位数。

| 桌面概览 | 移动端概览 |
|---|---|
| ![桌面概览](assets/screenshots/refactor-overview-desktop.png) | ![移动端概览](assets/screenshots/refactor-overview-mobile.png) |

[配置页](assets/screenshots/refactor-config-desktop.png) · [日志页](assets/screenshots/refactor-logs-desktop.png) · [深色账户](assets/screenshots/refactor-account-dark-desktop.png)

## 容器资源实测

同一 amd64 开发宿主机，容器限制 1.75 CPU、1,536 MiB RAM、256 MiB shm、256 PID，**禁用容器 Swap**。测试创建 50 条本地监控快照，3 个访问者循环请求任务、数据和日志；full 同时执行 5 轮串行浏览器与模型加载，浏览器访问本地 data URL。原始结果保存为 `assets/validation/refactor-slim-benchmark.json` 与 `refactor-full-benchmark.json`。


| 镜像 | 时长 | 请求数 | API P95 | 峰值 RAM | 启动就绪 | 浏览器／模型 |
|---|---|---|---|---|---|---|
| refactor-slim | 30 s | 684 | 43.2 ms | 167.9 MiB | 2.31 s | 不包含 |
| refactor-full | 60 s | 1342 | 64.7 ms | 531.5 MiB | 2.00 s | 通过 |

两种镜像请求错误均为 0，OOM 均为 false。

这是管理 API、静态数据和浏览器模型加载的合成负载，尚未模拟 50 个真实平台监控目标的持续抓取、真实验证码推理和网络波动。短测无 OOM 不能替代 24 小时长期稳定性；开发宿主机也不是目标 EPYC VPS。

## 镜像体积口径

比较本地 `validation-slim/full`（本轮前已有 amd64 基线镜像）与 `refactor-slim/full`。原始镜像 ID、逐层 digest、压缩字节和展开字节保存在 `assets/validation/refactor-image-sizes.json`。压缩体积为 OCI 分发层大小之和，展开体积为同一组层解压后的 tar 字节之和；不是 `docker image ls` 的共享层磁盘占用，也未伪装成远端镜像仓库实际传输流量。


| 镜像 | 优化前压缩层 | 优化后压缩层 | 变化 | 优化前展开层 | 优化后展开层 | 变化 |
|---|---|---|---|---|---|---|
| slim | 68.3 MiB | 66.6 MiB | -2.5% | 187.8 MiB | 191.8 MiB | +2.1% |
| full | 625.7 MiB | 590.2 MiB | -5.7% | 1392.5 MiB | 1299.1 MiB | -6.7% |

slim 展开体积略增，未达到展开体积下降；主要来自固定 bookworm 基础层与新增认证依赖，删除旧前端和文档后压缩分发体积仍略降。full 的主要层（Docker history 显示值）为 Python 依赖约 467 MB、浏览器/驱动约 422 MB、系统浏览器库约 244 MB、iKuuu 模型约 99.2 MB。ddddocr 自带模型位于 Python 依赖层，未删除或转移到卷。

运行层移除旧前端、文档截图、测试与构建工具；保留包元数据、许可证和全部推理模型。基础发行版从旧未固定 slim 变为固定 bookworm，因此总体变化同时包含基础层差异，不能把所有差值归因于应用代码。浏览器、OCR 和模型仍占 full 的主要体积。

## 待完成验收与复现

- 真实手机：指定机型/系统后测交互延迟、滚动帧率、软键盘和后台恢复。
- 目标服务器：50 个模拟持续抓取目标、5 个浏览器账号、3 个访问者的完整并发负载与网络扰动。
- 24 小时：运行 `scripts/container_benchmark.py --seconds 86400`，检查内存曲线、任务去重、子进程及停止行为；当前脚本长测每约 5 分钟重复浏览器加载，仍需补平台模拟流量。
- amd64/arm64：CI 已增加 QEMU、对应架构镜像启动与浏览器／模型冒烟；本轮未实际运行远端 CI 或 arm64 机器。
- Windows：发布流程已接入前端构建，尚未验证实际发行包。
- CI 发布前执行新增工作流，远程标签当前不能当作本次修改的交付镜像。

```bash
.venv/bin/python -m pytest -q
npm run format:check --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
npm run test:e2e --prefix frontend
.venv/bin/python scripts/container_benchmark.py --image webmoniter:refactor-full --seconds 60 --output /tmp/full.json
.venv/bin/python scripts/image_report.py webmoniter:validation-full webmoniter:refactor-full --output /tmp/sizes.json
```

参考依据：[Vue 性能建议](https://vuejs.org/guide/best-practices/performance)、[Apple Liquid Glass](https://developer.apple.com/videos/play/wwdc2025/219/)、[ColorOS](https://www.oppo.com/en/coloros16/)、[Uptime Kuma](https://github.com/louislam/uptime-kuma)、[Docker 构建最佳实践](https://docs.docker.com/build/building/best-practices/)、[Docker 资源限制](https://docs.docker.com/engine/containers/resource_constraints/)。

## 功能注册清单

| ID | 功能 | 类型 |
|---|---|---|
| `huya_monitor` | 虎牙直播监控 | monitor |
| `weibo_monitor` | 微博监控 | monitor |
| `bilibili_monitor` | 哔哩哔哩监控 | monitor |
| `douyin_monitor` | 抖音直播监控 | monitor |
| `kuaishou_monitor` | 快手直播监控 | monitor |
| `douyu_monitor` | 斗鱼直播监控 | monitor |
| `xhs_monitor` | 小红书动态监控 | monitor |
| `weibo_cookie_refresh` | 微博 Cookie 自动刷新 | task |
| `log_cleanup` | 日志清理 | task |
| `ikuuu_checkin` | iKuuu 签到 | task |
| `tieba_checkin` | 百度贴吧签到 | task |
| `weibo_chaohua_checkin` | 微博超话签到 | task |
| `rainyun_checkin` | 雨云签到 | task |
| `enshan_checkin` | 恩山论坛签到 | task |
| `fg_checkin` | 富贵论坛签到 | task |
| `aliyun_checkin` | 阿里云盘签到 | task |
| `smzdm_checkin` | 什么值得买签到 | task |
| `zdm_draw` | 值得买每日抽奖 | task |
| `tyyun_checkin` | 天翼云盘签到 | task |
| `miui_checkin` | 小米社区签到 | task |
| `iqiyi_checkin` | 爱奇艺签到 | task |
| `lenovo_checkin` | 联想乐豆签到 | task |
| `lbly_checkin` | 丽宝乐园签到 | task |
| `pinzan_checkin` | 品赞代理签到 | task |
| `dml_checkin` | 达美乐任务 | task |
| `xiaomao_checkin` | 小茅预约 | task |
| `ydwx_checkin` | 一点万象签到 | task |
| `xingkong_checkin` | 星空代理签到 | task |
| `freenom_checkin` | Freenom 免费域名续期 | task |
| `weather_push` | 天气每日推送 | task |
| `qtw_checkin` | 千图网签到 | task |
| `kuake_checkin` | 夸克网盘签到 | task |
| `kjwj_checkin` | 科技玩家签到 | task |
| `fr_checkin` | 帆软社区签到 | task |
| `nine_nine_nine_task` | 999 会员中心健康打卡 | task |
| `zgfc_draw` | 中国福彩抽奖活动 | task |
| `ssq_500w_notice` | 双色球开奖通知 | task |
| `demo_task` | 二次开发示例任务 | task |

推送适配器：`serverChan_turbo`、`serverChan_3`、`wecom_apps`、`wecom_bot`、`dingtalk_bot`、`feishu_apps`、`feishu_bot`、`telegram_bot`、`qq_bot`、`napcat_qq`、`bark`、`gotify`、`webhook`、`pushplus`、`email`、`wxpusher`、`demo`、`qlapi`。注册与配置映射有完整性断言，各平台业务仍由原模块实现。

## 安装入口简化验证（2026-10-02）

- Docker 入口统一为 `bash install.sh docker`；根目录 Compose 默认 full，并复用原有资源限制、项目名和三个命名卷。三个 Compose 配置解析结果已对比一致（slim 仅镜像不同）。
- 源码入口为 `bash install.sh source`；自动准备工具、依赖、前端及浏览器模型，首次配置与 Docker 共用初始化逻辑。保留 YAML 时间字符串的引号，避免后端按整数解析；现有配置不覆盖。
- 独立临时源码副本实跑 `--no-browser --prepare-only`，完成依赖安装、前端类型检查与生产构建；随后两次运行 `--no-browser`，健康检查、静态页面、默认登录和任务接口均通过，已有配置字节保持不变，复用前端产物。
- 安装测试覆盖并发配置创建、下载摘要失败、前端失败缓存、带空格路径、Docker 失败退出、浏览器归档安装及复用、full/HTTP 模式分支。浏览器下载与系统库安装使用模拟；本轮没有在空白 Ubuntu 上实装 apt 软件包，也未重新构建或发布镜像。此前容器体积与性能测量的版本及边界保持不变。

## 修改文件清单

完整新增、修改和删除路径见 [文件清单](assets/validation/refactor-changed-files.txt)。新前端位于 `frontend/`；原 `src/webUI/templates`、`static/js`、`static/css` 已移除，图标和图片资源保留。
