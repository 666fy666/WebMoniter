> Deployment and maintenance commands below follow the current Compose layout. See the [deployment guide](DEPLOYMENT.md) for backups, HTTPS and recovery.

<div align="center">

# WebMoniter

**Multi-platform Monitoring · Automated Check-ins · Live Alerts · Multi-channel Notifications**

<sub>Monitoring · Check-ins · Live Alerts · Push Notifications · Scheduled Tasks · Hot Configuration Reload</sub>

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](https://github.com/666fy666/WebMoniter/blob/main/LICENSE)
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
| Kuaishou (live validation pending) | `kuaishou` | No | Yes |
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

The default **full** image includes the browser, driver and OCR. `latest` is the slim image without those dependencies. Weibo cookie refresh, iKuuu and Rainyun browser tasks require full. Run the following on the deployment machine:

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh docker
```

The script installs Docker Engine and Compose on Ubuntu 22.04/24.04/26.04 when missing (root or sudo required), pulls full, and starts it in the background. On other systems, install Docker and Compose first. With Compose already installed, you can replace the script with `docker compose up -d --pull always --wait --wait-timeout 180`.

Open **http://127.0.0.1:8866** locally or `http://SERVER_IP:8866` remotely. The current mapping is `0.0.0.0:8866:8866`; allow TCP 8866 from the intended clients in the firewall and cloud security group, and change the default password before exposing the service. For SSH or a host reverse proxy only, change the mapping to `127.0.0.1:8866:8866` and rerun Compose `up`. To use an SSH tunnel, run this on your own computer, replace the destination, keep the connection open, then open the local browser address:

```bash
ssh -N -L 8866:127.0.0.1:8866 user@server
```

Log in with **`admin` / `123`**, change the password, then configure notification channels, accounts and targets and enable the tasks you need. Business tasks start disabled. Check task results in the logs; configuration changes usually apply within about 5 seconds. Existing accounts keep their current password.

#### Update, stop and remove

Run all maintenance commands from the original repository root. Reuse the same `-f`, `-p`, `--env-file` and override files if customized; add `sudo` if Docker permissions require it. [Back up configuration and data](DEPLOYMENT.md#backup-restore) first, then run each command only after the previous one succeeds:

```bash
git pull --ff-only
docker compose up -d --pull always --wait --wait-timeout 180
docker compose ps
docker compose logs --tail=100 web-monitor
```

`git pull` updates repository files, not the image. `pull` only downloads; `restart` keeps the old container image. `up --pull always` applies a published image update. If `WEBMONITER_IMAGE` pins a version or digest, change it first. Unpublished source changes require a [local build](https://github.com/666fy666/WebMoniter/blob/main/docker/README.md#local-build), followed by `up --pull never`.

| Purpose | Command | Data |
|---|---|---|
| View status | `docker compose ps` | Unchanged |
| Follow logs | `docker compose logs --tail=100 -f web-monitor` | Ctrl+C only exits the log viewer |
| Stop service and tasks | `docker compose stop` | Container and data retained |
| Resume stopped container | `docker compose start` | Original data retained |
| Restart current container | `docker compose restart` | Does not update the image |
| Remove containers and network | `docker compose down` | Named volumes retained |
| Resume after down | `docker compose up -d --wait --wait-timeout 180` | Reuses named volumes |

**Permanent uninstall, including all configuration, accounts, cookies, history and logs. Back up first; this cannot be undone:**

```bash
docker compose down --volumes
```

Default volumes are `webmoniter_config` (`/app/config`), `webmoniter_data` (`/app/data`) and `webmoniter_logs` (`/app/logs`). Docker does not use the repository root `config.yml` or `./data`. Updates preserve these volumes; `down --volumes` deletes them. Old bind mounts are not migrated automatically.

After removing containers, optionally run `docker image rm fengyu666/webmoniter:full` to remove the unused image (substitute your actual tag). Source files, `.env`, host backups, bind mounts and Docker itself remain; clean those separately if no longer needed. Do not use global pruning to uninstall this project.

### Local Installation (Linux)

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh source
```

The installer prepares Python 3.11, uv, Node 24, frontend assets, the browser/driver and models, then runs in the foreground. Configuration is created automatically. Use `bash install.sh source --no-browser` for HTTP-only tasks. Stop with Ctrl+C; to update, stop and back up first, run `git pull --ff-only`, then rerun the installer. See [source maintenance](installation.md#source-maintenance) for cleanup and removal.

### Windows Package

Download `WebMoniter-vX.X.X-windows-x64.zip` from [Releases](https://github.com/666fy666/WebMoniter/releases/latest), extract it, copy `config.yml.sample` to `config.yml`, and double-click `WebMoniter.exe`.

### Qinglong Panel

Qinglong users can configure tasks with environment variables and run them with `python -m src.ql <task_id>`. See the [Qinglong compatibility guide](QINGLONG.md).

---

## Configuration

The source installer creates `config.yml` at the repository root. Docker creates `/app/config/config.yml` in its configuration volume. Existing configuration is preserved; edit it through the Web configuration page. Do not overwrite it with the sample during updates.

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

Environment setup and all validation commands are maintained in the [development guide](SECONDARY_DEVELOPMENT.md). Module boundaries and data flow are described in [Architecture](ARCHITECTURE.md).

</details>

---

## Acknowledgements

Some check-in and notification ideas were inspired by:

- [aio-dynamic-push](https://github.com/nfe-w/aio-dynamic-push)
- [only_for_happly](https://github.com/wd210010/only_for_happly)
- [RainyunCheckIn](https://github.com/FalseHappiness/RainyunCheckIn)
- [Rainyun-Qiandao](https://github.com/Jielumoon/Rainyun-Qiandao)

## License

[MIT License](https://github.com/666fy666/WebMoniter/blob/main/LICENSE)

<div align="center">

**If this project helps you, please give it a ⭐ Star!**

Made with ❤️ by [FY](https://github.com/666fy666)

</div>
