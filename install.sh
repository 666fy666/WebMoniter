#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"
mode="${1:-docker}"
if [ "$#" -gt 0 ]; then shift; fi
case "$mode" in
  -h|--help|help)
    cat <<'HELP'
用法：
  bash install.sh docker                 拉取 full 镜像并后台启动（默认）
  bash install.sh source                 自动准备源码环境并前台启动
  bash install.sh source --prepare-only  只安装，不启动
  bash install.sh source --no-browser    仅准备 HTTP 任务，跳过浏览器与模型下载
再次执行相同命令可更新依赖／镜像，已有配置和数据保留。
HELP
    exit 0 ;;
  docker|source) ;;
  *) echo "不支持的模式：$mode；运行 bash install.sh --help" >&2; exit 2 ;;
esac
as_root() {
  if [ "$EUID" -eq 0 ]; then "$@"; else sudo "$@"; fi
}
ensure_curl() {
  if command -v curl >/dev/null; then return; fi
  if ! command -v apt-get >/dev/null; then
    echo '请安装 curl 后重新运行。' >&2; exit 1
  fi
  as_root apt-get update
  as_root apt-get install -y ca-certificates curl
}
if [ "$mode" = source ]; then
  mkdir -p .runtime/bin
  export PATH="$project_dir/.runtime/bin:$PATH"
  if ! command -v uv >/dev/null; then
    ensure_curl
    uv_installer="$(mktemp)"
    trap 'rm -f "$uv_installer"' EXIT
    curl --fail --location --retry 3 --connect-timeout 20 \
      https://astral.sh/uv/0.11.26/install.sh -o "$uv_installer"
    UV_INSTALL_DIR="$project_dir/.runtime/bin" UV_NO_MODIFY_PATH=1 sh "$uv_installer"
    rm -f "$uv_installer"
    trap - EXIT
  fi
  exec uv run --no-project --python 3.11 scripts/bootstrap_source.py "$@"
fi
if [ "$#" -ne 0 ]; then
  echo 'Docker 模式不接受额外参数；镜像可用 WEBMONITER_IMAGE 指定。' >&2; exit 2
fi
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  # Bootstrap a clean Ubuntu host from Docker's official apt repository.
  . /etc/os-release
  if [ "${ID:-}" != ubuntu ] || [[ "${VERSION_ID:-}" != @(22.04|24.04|26.04) ]]; then
    echo '自动安装 Docker 支持 Ubuntu 22.04/24.04/26.04；其他系统请先安装 Docker Compose。' >&2
    exit 1
  fi
  for package in docker.io podman-docker containerd runc docker-compose-v2; do
    if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -qx 'install ok installed'; then
      echo "发现已有 $package，请补齐其 Compose 插件或先处理与 Docker CE 的包冲突。" >&2
      exit 1
    fi
  done
  ensure_curl
  as_root install -m 0755 -d /etc/apt/keyrings
  if [ ! -f /etc/apt/sources.list.d/docker.sources ] && [ ! -f /etc/apt/sources.list.d/docker.list ]; then
    as_root curl -fsSL --retry 3 https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    as_root chmod a+r /etc/apt/keyrings/docker.asc
    as_root tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  fi
  as_root apt-get update
  as_root apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  as_root systemctl enable --now docker
fi
docker_command=(docker)
if ! docker info >/dev/null 2>&1; then
  if [ "$EUID" -ne 0 ]; then
    docker_command=(sudo --preserve-env=WEBMONITER_IMAGE,WEBMONITER_ADMIN_USERNAME,WEBMONITER_ADMIN_PASSWORD,WEBMONITER_SECURE_COOKIE,WEBMONITER_KUAISHOU_COOKIE docker)
  fi
  if ! "${docker_command[@]}" info >/dev/null 2>&1; then
    echo 'Docker 服务不可用，请启动 Docker 后重试。' >&2; exit 1
  fi
fi
"${docker_command[@]}" compose -f "$project_dir/compose.yaml" up -d --pull always --wait --wait-timeout 180
printf '\n已启动：http://127.0.0.1:8866（默认账号 admin / 123）\n远程访问可使用已有 HTTPS 入口或 SSH 本地端口转发。\n'
