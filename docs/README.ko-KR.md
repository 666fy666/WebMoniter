<div align="center">

# WebMoniter

**멀티 플랫폼 모니터링 · 자동 출석 체크 · 방송 알림 · 멀티 채널 알림**

<sub>모니터링 · 출석 체크 · 방송 알림 · 푸시 알림 · 예약 작업 · 설정 핫 리로드</sub>

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](../LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-Web%20UI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-multi--arch-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/r/fengyu666/webmoniter)
[![APScheduler](https://img.shields.io/badge/APScheduler-scheduler-blueviolet?style=flat-square)](https://apscheduler.readthedocs.io/)
[![uv](https://img.shields.io/badge/uv-package%20manager-DE5FE9?style=flat-square)](https://docs.astral.sh/uv/)
[![docs](https://img.shields.io/badge/docs-online-1997B5?style=flat-square&logo=readme&logoColor=white)](https://666fy666.github.io/WebMoniter/)
[![GitHub Stars](https://img.shields.io/github/stars/666fy666/WebMoniter?style=flat-square&logo=github)](https://github.com/666fy666/WebMoniter/stargazers)
[![Docker Pulls](https://img.shields.io/docker/pulls/fengyu666/webmoniter?style=flat-square&logo=docker)](https://hub.docker.com/r/fengyu666/webmoniter)
[![GitHub Release](https://img.shields.io/github/v/release/666fy666/WebMoniter?style=flat-square&logo=github&label=EXE)](https://github.com/666fy666/WebMoniter/releases/latest)

[中文](../README.md) · [English](README.en-US.md) · [Español](README.es-ES.md) · [日本語](README.ja-JP.md) · **한국어**

[문서 사이트](https://666fy666.github.io/WebMoniter/) ·
[설치](installation.md) ·
[설정](guides/config.md) ·
[API](API.md) ·
[2차 개발](SECONDARY_DEVELOPMENT.md) ·
[릴리스](https://github.com/666fy666/WebMoniter/releases/latest)

**코드 저장소**: [GitHub](https://github.com/666fy666/WebMoniter) · [GitCode](https://gitcode.com/qq_35720175/WebMoniter)

</div>

---

## 소개

WebMoniter는 Python, FastAPI, APScheduler 기반의 작업 시스템으로 다음 기능을 통합 관리합니다.

- Huya, Weibo, Bilibili, Douyin, Douyu, Xiaohongshu 플랫폼 모니터링.
- Weibo 쿠키 갱신, iKuuu, Tieba, Weibo Super Topic, Rainyun, Aliyun Drive, Freenom, 날씨 알림 등을 포함한 **30개의 예약 출석 체크 및 알림 작업**(`src/jobs/registry.py` 참고).
- WeCom, DingTalk, Feishu, Telegram, Bark, WxPusher, 이메일 등을 포함한 **18가지 알림 채널 유형**.
- 설정, 작업, 데이터, 로그, 비밀번호를 관리하는 반응형 Web UI. 내비게이션, 도구 모음, 대화상자와 컨트롤에는 Liquid Glass 스타일을 적용하며 데스크톱 사이드바, 모바일 하단 내비게이션, 키보드 조작 및 동작/투명도 감소 설정을 지원합니다.

설정 핫 리로드를 지원하며 `config.yml` 변경 사항은 일반적으로 약 5초 이내에 적용됩니다.

---

## 주요 기능

화면 및 기능에 대한 자세한 내용은 [문서 홈](index.md)과 [Web 관리 화면 안내](guides/web-ui.md)를 참고하세요.

<details>
<summary><strong>지원 플랫폼, 작업 및 알림 채널 보기</strong></summary>

### 지원 플랫폼

| 플랫폼 | `type` | 게시물 | 방송 시작/종료 |
|:--:|:--:|:--:|:--:|
| Huya | `huya` | 아니요 | 예 |
| Weibo | `weibo` | 예 | 아니요 |
| Bilibili | `bilibili` | 예 | 예 |
| Douyin | `douyin` | 아니요 | 예 |
| Douyu | `douyu` | 아니요 | 예 |
| Xiaohongshu | `xhs` | 예 | 아니요 |

### 예약 작업 일부

| 작업 | 설정 키 | 기본 시간 |
|:--:|:--:|:--:|
| 로그 정리 | `log_cleanup` | 02:10 |
| Weibo 쿠키 갱신 | `weibo` | 21:00 |
| iKuuu 출석 체크 | `checkin` | 08:00 |
| Rainyun 출석 체크 | `rainyun` | 08:30 |
| Tieba 출석 체크 | `tieba` | 08:10 |
| Weibo Super Topic | `weibo_chaohua` | 23:45 |
| Aliyun Drive | `aliyun` | 05:30 |
| 날씨 알림 | `weather` | 07:30 |

### 알림 채널 일부

| 채널 | `type` | 리치 콘텐츠 |
|:--:|:--:|:--:|
| WeCom 그룹 봇 | `wecom_bot` | 예 |
| DingTalk 봇 | `dingtalk_bot` | 예 |
| Feishu 봇 | `feishu_bot` | 아니요 |
| Telegram | `telegram_bot` | 예 |
| WxPusher | `wxpusher` | 예 |
| Bark | `bark` | 아니요 |
| PushPlus | `pushplus` | 예 |

</details>

---

## 빠른 시작

### Docker

경량 `latest` 이미지는 대부분의 모니터링 및 HTTP 출석 체크 작업에 적합합니다. `full` 이미지에는 브라우저와 관련 의존성이 추가되어 Weibo 쿠키 갱신, iKuuu, Rainyun처럼 Web 로그인이 필요한 작업에 사용할 수 있습니다.

**Docker Compose로 경량 이미지 시작(권장)**

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

`http://localhost:8866`에 접속하세요. 기본 계정은 `admin` / `123`입니다. 처음 로그인한 뒤 반드시 비밀번호를 변경하세요.

브라우저 기반 작업에는 전체 이미지를 사용합니다.

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
<summary><strong>단일 컨테이너 실행</strong></summary>

경량 이미지:

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

전체 이미지:

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

컨테이너 이름과 함께 `docker stop`, `docker start`, `docker restart`를 사용해 관리할 수 있습니다. 포트, 볼륨, 업데이트, 데이터 보존에 관한 내용은 [설치 및 실행](installation.md)과 [docker/README.md](../docker/README.md)를 참고하세요.

</details>

### 로컬 실행

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter

uv python install 3.11
uv venv --python 3.11
uv sync --locked --extra dev --extra rainyun
cp config/config.yml.sample config.yml
uv run python main.py
```

브라우저 기반 출석 체크가 필요하지 않다면 `uv sync --locked --extra dev`로 핵심 및 개발 의존성만 설치할 수 있습니다.

### Windows 패키지

[Releases](https://github.com/666fy666/WebMoniter/releases/latest)에서 `WebMoniter-vX.X.X-windows-x64.zip`을 다운로드하고 압축을 푼 뒤, `config.yml.sample`을 `config.yml`로 복사하고 `WebMoniter.exe`를 더블 클릭하세요.

### Qinglong 패널

Qinglong 사용자는 환경 변수로 설정한 뒤 `python -m src.ql <task_id>`로 예약 작업을 실행할 수 있습니다. 자세한 내용은 [Qinglong 호환 안내](QINGLONG.md)를 참고하세요.

---

## 설정

기본 설정 파일은 저장소 루트의 `config.yml`입니다. 처음 사용할 때 템플릿을 복사하세요.

```bash
cp config/config.yml.sample config.yml
```

- [설정 안내](guides/config.md)
- [모니터링 및 예약 작업](guides/tasks.md)
- [알림 채널](guides/push-channels.md)

---

## 문서 목록

| 항목 | 문서 |
|---|---|
| 설치 및 배포 | [installation.md](installation.md) |
| Web 관리 화면 | [guides/web-ui.md](guides/web-ui.md) |
| 작업 설정 | [guides/tasks.md](guides/tasks.md) |
| 모니터링 작업 | [guides/tasks/monitors.md](guides/tasks/monitors.md) |
| 출석 체크 작업 | [guides/tasks/checkin.md](guides/tasks/checkin.md) |
| 알림 채널 | [guides/push-channels.md](guides/push-channels.md) |
| REST API | [API.md](API.md) |
| 아키텍처 | [ARCHITECTURE.md](ARCHITECTURE.md) |
| 2차 개발 | [SECONDARY_DEVELOPMENT.md](SECONDARY_DEVELOPMENT.md) |
| 자주 묻는 질문 | [faq.md](faq.md) |

---

<details>
<summary><strong>개발</strong></summary>

```bash
uv sync --extra dev --extra rainyun
uv run ruff check .
uv run black --check .
uv run pytest -q
```

모니터링 또는 예약 작업을 추가하려면 [2차 개발 안내](SECONDARY_DEVELOPMENT.md)를 참고하세요. `src/tests/`의 테스트는 메타데이터, 레지스트리, enable 매핑의 일관성을 검증합니다. 전체 모듈 구조는 [아키텍처 문서](ARCHITECTURE.md)에 설명되어 있습니다.

</details>

---

## 감사의 말

일부 출석 체크 및 알림 아이디어는 다음 프로젝트를 참고했습니다.

- [aio-dynamic-push](https://github.com/nfe-w/aio-dynamic-push)
- [only_for_happly](https://github.com/wd210010/only_for_happly)
- [RainyunCheckIn](https://github.com/FalseHappiness/RainyunCheckIn)
- [Rainyun-Qiandao](https://github.com/Jielumoon/Rainyun-Qiandao)

## 라이선스

[MIT License](../LICENSE)

<div align="center">

**이 프로젝트가 도움이 되었다면 ⭐ Star를 눌러 주세요!**

Made with ❤️ by [FY](https://github.com/666fy666)

</div>
