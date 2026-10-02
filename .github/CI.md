# GitHub Actions 耗时优化

## 质量检查

- 后端 Ruff／pytest 与前端检查／浏览器回归分为两个 job 并行执行。
- PR 和主分支提交仅修改 `docs/**`、Markdown 或 LICENSE 时跳过重型检查；保留 `checks` 汇总状态，供分支保护使用。任意代码变更仍执行完整检查；标签发布和手动 Docker 发布始终完整验证。
- 连续提交取消同一 PR/分支的过时检查；发布任务不在执行中取消。
- uv 与 npm 缓存下载内容，安装仍遵循锁文件。前端 `dist` 使用包含整个前端目录的精确缓存键，只在输入完全一致时复用；格式检查、单元测试和浏览器回归仍执行。
- 后端保留 `dev`、`rainyun` 依赖，避免浏览器签到测试静默跳过；前端测试服务器仅安装基础依赖。
- 前端只有一个 job，依赖安装、格式检查、单测、构建各执行一次。Playwright 单 worker 串行运行桌面关键回归与四项移动端冒烟，共用临时测试服务器；用例基于当前值修改配置，避免不同视口依赖固定初值。平板、极窄屏、像素比对和弱网性能交给 [人工自测](../docs/guides/web-ui.md#manual-checks)。

## Docker 发布

四个任务分别在原生 AMD64/ARM64 runner 构建 slim/full，无需 QEMU。构建与质量检查同时开始，每个镜像在本机构建后按 digest 拉取，验证架构、Chromium 有无以及应用/浏览器冒烟测试。拉取失败才进行有上限的重试。

全部检查成功后，发布任务将两个架构的 digest 合并为多架构 manifest，保留原有版本号、主/次版本号、`latest`、`full` 标签规则，并验证标签包含两种架构。验证前只上传内容寻址镜像与构建缓存，不更新上述发行标签。

缓存保存在同一个 Docker Hub 仓库的四个 `buildcache-{slim,full}-{amd64,arm64}` 标签中，彼此隔离，可跨版本标签复用。首次运行需要建立缓存；删除这些缓存标签只影响速度。GitHub Actions 原生缓存受 Git ref 作用域限制，不适合作为不同版本标签之间的唯一 Docker 缓存。

Dockerfile 将业务代码复制与浏览器系统依赖安装分层；模型下载仅依赖标准库及下载脚本，不再因 Python 依赖变化而重新下载。

## Windows 与文档

Windows 打包使用 uv 和 npm 缓存，基础依赖按 `uv.lock` 安装；ZIP 上传关闭重复压缩。文档工具依赖从 `pyproject.toml` 读取，使用锁文件导出的版本约束，仅安装文档依赖。`uv.lock` 变更也触发文档部署。

## 验证与耗时对比

本地检查命令统一见 [开发指南](../docs/SECONDARY_DEVELOPMENT.md#development-checks)。工作流改动另运行 `actionlint`（若已安装）与 `.venv/bin/python -m pytest -q src/tests/test_ci_workflows.py`，后者验证汇总门禁和发布摘要保护。

首次和第二次发布分别观察冷缓存、热缓存耗时。对比 Actions 中的总墙钟时间及每个 job 的依赖安装、构建、冒烟步骤，避免将 runner 排队时间误认为构建时间。新的发布关键路径约为 `max(质量检查, 最慢的原生构建与冒烟测试) + manifest 发布`；实际降幅需以远程运行结果确认。

历史记录（本轮未重新查询远程 Actions）：此前的[质量检查](https://github.com/666fy666/WebMoniter/actions/runs/36994382651)总计约 158 秒，其中浏览器回归 70 秒。当天的 [Docker 发布](https://github.com/666fy666/WebMoniter/actions/runs/36992704267)中 full 构建 630 秒、slim 构建 297 秒，ARM 验证失败在 QEMU 初始化；前一天最近一次[成功发布](https://github.com/666fy666/WebMoniter/actions/runs/36847305461)总计约 459 秒。失败运行不作为成功发布提速比例的分母。

分架构构建与缓存配置参考 [Docker 多架构 CI](https://docs.docker.com/build/ci/github-actions/multi-platform/)、[Registry cache](https://docs.docker.com/build/cache/backends/registry/)；runner 标签参考 [GitHub 官方列表](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)。
