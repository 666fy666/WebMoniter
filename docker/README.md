# Docker

下载源码后在根目录运行 `bash install.sh docker`，自动准备 Docker、拉取 full 镜像并启动。已有 Compose 时直接运行 `docker compose up -d --pull always --wait`。默认账号 `admin / 123`，无需预设密码。

需要构建当前未发布源码时，共用一个多阶段 Dockerfile：

```bash
docker build --target slim -f docker/Dockerfile -t webmoniter:local-slim .
docker build --target full -f docker/Dockerfile -t webmoniter:local-full .
```

## GitHub Actions 发布与服务器更新

`Build and Push Docker Image` 工作流在推送 `v*` 标签或手动触发时构建镜像，普通分支推送只运行质量检查，不会发布镜像。代码合并后，在 GitHub 的 **Actions → Build and Push Docker Image → Run workflow** 选择对应分支，等待完整工作流成功。仓库需要配置 `DOCKER_USERNAME` 和 `DOCKER_PASSWORD` Actions secrets。

镜像 `fengyu666/webmoniter:full` 是包含浏览器与识别依赖的完整版；`fengyu666/webmoniter:latest` 是精简版。使用 `docker/docker-compose.full.yml` 的服务器，在项目根目录运行：

```bash
# 拉取镜像、更新容器，并等待健康检查通过
docker compose -f docker/docker-compose.full.yml up -d --pull always --no-build --wait web-monitor

# 检查运行状态与最近日志
docker compose -f docker/docker-compose.full.yml ps
docker compose -f docker/docker-compose.full.yml logs --tail=100 web-monitor
```

若已进入项目的 `docker` 目录，将命令中的文件路径改为 `docker-compose.full.yml`。更新时沿用原部署的工作目录、`-p`、`--env-file` 和其他 Compose 覆盖文件参数，确保仍使用相同配置与数据卷。`WEBMONITER_IMAGE` 环境变量会覆盖默认镜像地址；若固定了版本标签，需要先改成要部署的新标签。

`up --pull always` 会拉取镜像，并在镜像变化时重建容器，保留挂载卷。单独执行 `docker pull` 只下载镜像，`restart` 也不会切换容器镜像。无需先执行 `down`，不要用会删除数据卷的 `down -v`。详见 [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/) 与 [pull](https://docs.docker.com/reference/cli/docker/compose/pull/)。

完整的 Ubuntu 24.04 部署、密码初始化、资源限制、目录权限、HTTPS、备份恢复和版本回退见 [部署指南](../docs/DEPLOYMENT.md)。镜像测量和验收边界见 [审查报告](../docs/REFACTOR_AUDIT.md)。当前源码修改尚未发布到远程镜像标签。
