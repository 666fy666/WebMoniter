<div align="center">

# WebMoniter

**Multi-platform Monitoring · Automated Check-ins · Live Alerts · Multi-channel Notifications**

<sub>Monitoring · Check-ins · Live Alerts · Push Notifications · Scheduled Tasks · Hot Configuration Reload</sub>

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](../LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-Web%20UI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-multi--arch-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/r/fengyu666/webmoniter)
[![APScheduler](https://img.shields.io/badge/APScheduler-scheduler-blueviolet?style=flat-square)](https://apscheduler.readthedocs.io/)
[![uv](https://img.shields.io/badge/uv-package%20manager-DE5FE9?style=flat-square)](https://docs.astral.sh/uv/)
[![docs](https://img.shields.io/badge/docs-online-1997B5?style=flat-square&logo=readme&logoColor=white)](https://666fy666.github.io/WebMoniter/)
[![GitHub Stars](https://img.shields.io/github/stars/666fy666/WebMoniter?style=flat-square&logo=github)](https://github.com/666fy666/WebMoniter/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/666fy666/WebMoniter?style=flat-square&logo=github)](https://github.com/666fy666/WebMoniter/forks)
[![Docker Pulls](https://img.shields.io/docker/pulls/fengyu666/webmoniter?style=flat-square&logo=docker)](https://hub.docker.com/r/fengyu666/webmoniter)
[![GitHub Release](https://img.shields.io/github/v/release/666fy666/WebMoniter?style=flat-square&logo=github&label=EXE)](https://github.com/666fy666/WebMoniter/releases/latest)

[中文](../README.md) · **English** · [Español](README.es-ES.md) · [日本語](README.ja-JP.md) · [한국어](README.ko-KR.md)

[Documentation](https://666fy666.github.io/WebMoniter/) ·
[Installation](installation.md) ·
[Configuration](guides/config.md) ·
[API](API.md) ·
[Secondary Development](SECONDARY_DEVELOPMENT.md) ·
[Releases](https://github.com/666fy666/WebMoniter/releases/latest)

**Repositories**: [GitHub](https://github.com/666fy666/WebMoniter) · [GitCode](https://gitcode.com/qq_35720175/WebMoniter)

</div>

---

## Introduction

WebMoniter is a task system built with Python, FastAPI, and APScheduler. It provides unified management for:

- Platform monitoring for Huya, Weibo, Bilibili, Douyin, Douyu, and Xiaohongshu.
- **30 scheduled check-in and reminder tasks**, including Weibo cookie refresh, iKuuu, Tieba, Weibo Super Topic, Rainyun, Aliyun Drive, Freenom, and weather notifications (plus a `demo_task` example; see `TASK_SPECS` in `src/jobs/metadata.py`).
- **18 notification channel types**, including WeCom, DingTalk, Feishu, Telegram, Bark, WxPusher, and email.
- A responsive Web UI for configuration, tasks, data, logs, and passwords. Its navigation, toolbars, dialogs, and controls use a Liquid Glass style, with desktop side navigation, mobile bottom navigation, keyboard interaction, and accessible motion/transparency fallbacks.

Configuration supports hot reload. Changes to `config.yml` usually take effect within about five seconds.

---

## Features

See the [documentation home](index.md) and [Web management UI guide](guides/web-ui.md) for interface details.

<details>
<summary><strong>Show supported platforms, tasks, and channels</strong></summary>

### Supported Platforms

| Platform | `type` | Posts | Live status |
|:--:|:--:|:--:|:--:|
| Huya | `huya` | No | Yes |
| Weibo | `weibo` | Yes | No |
| Bilibili | `bilibili` | Yes | Yes |
| Douyin | `douyin` | No | Yes |
| Douyu | `douyu` | No | Yes |
| Xiaohongshu | `xhs` | Yes | No |

### Selected Scheduled Tasks

| Task | Configuration key | Default time |
|:--:|:--:|:--:|
| Log cleanup | `log_cleanup` | 02:10 |
| Weibo cookie refresh | `weibo` | 21:00 |
| iKuuu check-in | `checkin` | 08:00 |
| Rainyun check-in | `rainyun` | 08:30 |
| Tieba check-in | `tieba` | 08:10 |
| Weibo Super Topic | `weibo_chaohua` | 23:45 |
| Aliyun Drive | `aliyun` | 05:30 |
| Weather notification | `weather` | 07:30 |

### Selected Notification Channels

| Channel | `type` | Rich content |
|:--:|:--:|:--:|
| WeCom group bot | `wecom_bot` | Yes |
| DingTalk bot | `dingtalk_bot` | Yes |
| Feishu bot | `feishu_bot` | No |
| Telegram | `telegram_bot` | Yes |
| WxPusher | `wxpusher` | Yes |
| Bark | `bark` | No |
| PushPlus | `pushplus` | Yes |

</details>

---

## Quick Start

### Docker

The lightweight `latest` image is suitable for most monitoring and HTTP check-in tasks. The `full` image additionally includes a browser and browser check-in dependencies for tasks such as Weibo cookie refresh, iKuuu, and Rainyun.

**Start the lightweight image with Docker Compose (recommended)**

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
cp config/config.yml.sample config.yml

docker compose -f docker/docker-compose.yml pull
docker compose -f docker/docker-compose.yml up -d

docker compose -f docker/docker-compose.yml logs -f
docker compose -f docker/docker-compose.yml stop
docker compose -f docker/docker-compose.yml start
docker compose -f docker/docker-compose.yml restart
docker compose -f docker/docker-compose.yml down
```

Open `http://localhost:8866`. The default credentials are `admin` / `123`; change the password after your first login.

Use the full image for browser-based tasks:

```bash
docker compose -f docker/docker-compose.full.yml pull
docker compose -f docker/docker-compose.full.yml up -d

docker compose -f docker/docker-compose.full.yml logs -f
docker compose -f docker/docker-compose.full.yml stop
docker compose -f docker/docker-compose.full.yml start
docker compose -f docker/docker-compose.full.yml restart
docker compose -f docker/docker-compose.full.yml down
```

<details>
<summary><strong>Single-container commands</strong></summary>

Lightweight image:

```bash
docker pull fengyu666/webmoniter:latest
docker run -d --name webmoniter --restart unless-stopped \
  -p 8866:8866 --shm-size=128m \
  -e TZ=Asia/Shanghai \
  -v "$(pwd)/config.yml:/app/config.yml" \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/logs:/app/logs" \
  fengyu666/webmoniter:latest
```

Full image:

```bash
docker pull fengyu666/webmoniter:full
docker run -d --name webmoniter-full --restart unless-stopped \
  -p 8866:8866 --shm-size=256m \
  -e TZ=Asia/Shanghai \
  -e CHROME_BIN=/usr/bin/chromium \
  -e CHROMEDRIVER_PATH=/usr/bin/chromedriver \
  -v "$(pwd)/config.yml:/app/config.yml" \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/logs:/app/logs" \
  fengyu666/webmoniter:full
```

Use `docker stop`, `docker start`, or `docker restart` with the container name to manage it. See [Installation and Operation](installation.md) and [docker/README.md](../docker/README.md) for port, volume, update, and data retention details.

</details>

### Local Installation

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter

uv python install 3.11
uv venv --python 3.11
uv sync --locked --extra dev --extra rainyun
cp config/config.yml.sample config.yml
uv run python main.py
```

If you do not need browser-based check-ins, install only the core and development dependencies with `uv sync --locked --extra dev`.

### Windows Package

Download `WebMoniter-vX.X.X-windows-x64.zip` from [Releases](https://github.com/666fy666/WebMoniter/releases/latest), extract it, copy `config.yml.sample` to `config.yml`, and double-click `WebMoniter.exe`.

### Qinglong Panel

Qinglong users can configure tasks with environment variables and run them with `python -m src.ql <task_id>`. See the [Qinglong compatibility guide](QINGLONG.md).

---

## Configuration

The main configuration file is `config.yml` in the repository root. Create it from the template:

```bash
cp config/config.yml.sample config.yml
```

Related documentation:

- [Configuration](guides/config.md)
- [Monitoring and scheduled tasks](guides/tasks.md)
- [Notification channels](guides/push-channels.md)

---

## Documentation Map

| Topic | Document |
|---|---|
| Installation | [installation.md](installation.md) |
| Web management UI | [guides/web-ui.md](guides/web-ui.md) |
| Task configuration | [guides/tasks.md](guides/tasks.md) |
| Monitoring tasks | [guides/tasks/monitors.md](guides/tasks/monitors.md) |
| Check-in tasks | [guides/tasks/checkin.md](guides/tasks/checkin.md) |
| Notification channels | [guides/push-channels.md](guides/push-channels.md) |
| REST API | [API.md](API.md) |
| Architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Secondary development | [SECONDARY_DEVELOPMENT.md](SECONDARY_DEVELOPMENT.md) |
| FAQ | [faq.md](faq.md) |

---

<details>
<summary><strong>Development</strong></summary>

```bash
uv sync --extra dev --extra rainyun
uv run ruff check .
uv run black --check .
uv run pytest -q
```

See the [secondary development guide](SECONDARY_DEVELOPMENT.md) when adding monitors or scheduled tasks. Consistency tests under `src/tests/` verify metadata, registries, and enable mappings. See [Architecture](ARCHITECTURE.md) for the complete module layout.

</details>

---

## Acknowledgements

Some check-in and notification ideas were inspired by:

- [aio-dynamic-push](https://github.com/nfe-w/aio-dynamic-push)
- [only_for_happly](https://github.com/wd210010/only_for_happly)
- [RainyunCheckIn](https://github.com/FalseHappiness/RainyunCheckIn)
- [Rainyun-Qiandao](https://github.com/Jielumoon/Rainyun-Qiandao)

## License

[MIT License](../LICENSE)

<div align="center">

**If this project helps you, please give it a ⭐ Star!**

Made with ❤️ by [FY](https://github.com/666fy666)

</div>
