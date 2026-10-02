# Docker

下载源码后在根目录运行 `bash install.sh docker`，自动准备 Docker、拉取 full 镜像并启动。已有 Compose 时直接运行 `docker compose up -d --pull always --wait`。默认账号 `admin / 123`，无需预设密码。

需要构建当前未发布源码时，共用一个多阶段 Dockerfile：

```bash
docker build --target slim -f docker/Dockerfile -t webmoniter:local-slim .
docker build --target full -f docker/Dockerfile -t webmoniter:local-full .
```

完整的 Ubuntu 24.04 部署、密码初始化、资源限制、目录权限、HTTPS、备份恢复和版本回退见 [部署指南](../docs/DEPLOYMENT.md)。镜像测量和验收边界见 [审查报告](../docs/REFACTOR_AUDIT.md)。当前源码修改尚未发布到远程镜像标签。
