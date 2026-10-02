> 아래 배포 및 유지보수 명령은 현재 Compose 구성을 따릅니다. 백업, HTTPS 및 복구는 [배포 안내](DEPLOYMENT.md)를 참고하세요.

<div align="center">

# WebMoniter

**멀티 플랫폼 모니터링 · 자동 출석 체크 · 방송 알림 · 멀티 채널 알림**

<sub>모니터링 · 출석 체크 · 방송 알림 · 푸시 알림 · 예약 작업 · 설정 핫 리로드</sub>

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](https://github.com/666fy666/WebMoniter/blob/main/LICENSE)
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
- Weibo 쿠키 갱신, iKuuu, Tieba, Weibo Super Topic, Rainyun, Aliyun Drive, Freenom, 날씨 알림 등을 포함한 **30개의 예약 출석 체크 및 알림 작업**(추가로 `demo_task` 예제; 목록은 `src/jobs/metadata.py`의 `TASK_SPECS`).
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
| 콰이쇼우 (실환경 검증 필요) | `kuaishou` | 아니요 | 예 |
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

기본 **full** 이미지에는 브라우저, 드라이버와 OCR이 포함됩니다. `latest`는 이 의존성이 없는 경량 이미지입니다. Weibo Cookie 갱신, iKuuu, Rainyun 브라우저 작업에는 full을 사용하세요. 서비스를 실행할 컴퓨터나 서버에서 다음을 실행합니다.

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh docker
```

Ubuntu 22.04/24.04/26.04에 Docker Engine과 Compose가 없으면 스크립트가 설치합니다(root 또는 sudo 필요). full을 내려받아 백그라운드로 시작합니다. 다른 운영체제에서는 Docker와 Compose를 먼저 설치하세요. 이미 설치되어 있다면 스크립트 대신 `docker compose up -d --pull always --wait --wait-timeout 180`을 실행해도 됩니다.

로컬에서는 **http://127.0.0.1:8866**, 원격에서는 `http://서버IP:8866`을 엽니다. 현재 매핑은 `0.0.0.0:8866:8866`입니다. 방화벽과 보안 그룹에서 필요한 접속 출처의 TCP 8866을 허용하고 외부 공개 전에 기본 비밀번호를 변경하세요. SSH나 호스트의 리버스 프록시만 사용하려면 매핑을 `127.0.0.1:8866:8866`으로 바꾸고 Compose `up`을 다시 실행하세요. SSH 터널은 자신의 컴퓨터에서 접속 대상을 바꿔 아래 명령을 실행하고 연결을 유지한 채 로컬 주소를 열면 됩니다.

```bash
ssh -N -L 8866:127.0.0.1:8866 user@server
```

**`admin` / `123`**으로 로그인하고 비밀번호를 변경한 다음 알림 채널, 계정, 대상을 설정하고 필요한 작업을 활성화하세요. 업무 작업은 처음에는 비활성화됩니다. 실행 결과는 로그에서 확인하며 설정 변경은 보통 약 5초 안에 적용됩니다. 기존 계정의 비밀번호는 유지됩니다.

#### 업데이트, 중지 및 삭제

유지보수 명령은 원래 저장소 루트에서 실행하세요. 사용자 지정 `-f`, `-p`, `--env-file` 및 추가 구성 파일은 계속 동일하게 사용하고, Docker 권한이 필요하면 `sudo`를 붙이세요. 먼저 [설정과 데이터를 백업](DEPLOYMENT.md#backup-restore)하고 각 명령이 성공한 뒤 다음 명령을 실행합니다.

```bash
git pull --ff-only
docker compose up -d --pull always --wait --wait-timeout 180
docker compose ps
docker compose logs --tail=100 web-monitor
```

`git pull`은 저장소 파일만 갱신합니다. `pull`은 이미지만 다운로드하고 `restart`는 기존 컨테이너 이미지로 재시작합니다. 공개된 새 이미지는 `up --pull always`로 적용합니다. `WEBMONITER_IMAGE`로 버전이나 digest를 고정했다면 먼저 바꾸세요. 아직 공개되지 않은 변경은 [로컬 빌드](https://github.com/666fy666/WebMoniter/blob/main/docker/README.md#local-build) 후 `up --pull never`로 실행합니다.

| 목적 | 명령 | 데이터 |
|---|---|---|
| 상태 확인 | `docker compose ps` | 변경 없음 |
| 로그 추적 | `docker compose logs --tail=100 -f web-monitor` | Ctrl+C는 로그 보기만 종료 |
| 서비스와 작업 중지 | `docker compose stop` | 컨테이너와 데이터 유지 |
| 중지된 컨테이너 재개 | `docker compose start` | 기존 데이터 유지 |
| 현재 컨테이너 재시작 | `docker compose restart` | 이미지를 업데이트하지 않음 |
| 컨테이너와 네트워크 삭제 | `docker compose down` | 명명된 볼륨 유지 |
| down 이후 다시 시작 | `docker compose up -d --wait --wait-timeout 180` | 기존 볼륨 재사용 |

**완전 삭제: 설정, 계정, Cookie, 실행 기록과 로그를 영구 삭제합니다. 먼저 백업하세요. 되돌릴 수 없습니다.**

```bash
docker compose down --volumes
```

기본 볼륨은 `webmoniter_config`(`/app/config`), `webmoniter_data`(`/app/data`), `webmoniter_logs`(`/app/logs`)입니다. Docker는 저장소 루트의 `config.yml`이나 `./data`를 사용하지 않습니다. 업데이트는 볼륨을 보존하지만 `down --volumes`는 삭제합니다. 이전 bind mount 데이터는 자동 이전되지 않습니다.

컨테이너를 삭제한 후 필요 없는 이미지는 `docker image rm fengyu666/webmoniter:full`로 삭제할 수 있습니다(실제 태그로 변경). 소스, `.env`, 호스트 백업, 마운트 디렉터리와 Docker 자체는 남으므로 필요 없을 때 별도로 정리하세요. 이 프로젝트를 삭제하려고 전역 prune을 실행하지 마세요.

### 로컬 실행 (Linux)

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh source
```

설치 스크립트는 Python 3.11, uv, Node 24, 프론트엔드, 브라우저/드라이버와 모델을 준비하고 설정을 자동 생성한 뒤 포그라운드에서 실행합니다. HTTP 작업만 필요하면 `bash install.sh source --no-browser`를 사용하세요. Ctrl+C로 중지합니다. 업데이트하려면 중지하고 백업한 뒤 `git pull --ff-only`를 실행하고 설치 스크립트를 다시 실행하세요. 정리와 삭제는 [소스 배포 유지보수](installation.md#source-maintenance)를 참고하세요.

### Windows 패키지

[Releases](https://github.com/666fy666/WebMoniter/releases/latest)에서 `WebMoniter-vX.X.X-windows-x64.zip`을 다운로드하고 압축을 푼 뒤, `config.yml.sample`을 `config.yml`로 복사하고 `WebMoniter.exe`를 더블 클릭하세요.

### Qinglong 패널

Qinglong 사용자는 환경 변수로 설정한 뒤 `python -m src.ql <task_id>`로 예약 작업을 실행할 수 있습니다. 자세한 내용은 [Qinglong 호환 안내](QINGLONG.md)를 참고하세요.

---

## 설정

소스 설치는 저장소 루트의 `config.yml`을, Docker는 설정 볼륨 안의 `/app/config/config.yml`을 자동 생성합니다. 기존 설정은 보존됩니다. Web 설정 화면에서 수정하고 업데이트할 때 샘플로 덮어쓰지 마세요.

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

환경 설정과 검증 명령은 [개발 안내](SECONDARY_DEVELOPMENT.md), 모듈 구성과 데이터 흐름은 [아키텍처](ARCHITECTURE.md)를 참고하세요.

</details>

---

## 감사의 말

일부 출석 체크 및 알림 아이디어는 다음 프로젝트를 참고했습니다.

- [aio-dynamic-push](https://github.com/nfe-w/aio-dynamic-push)
- [only_for_happly](https://github.com/wd210010/only_for_happly)
- [RainyunCheckIn](https://github.com/FalseHappiness/RainyunCheckIn)
- [Rainyun-Qiandao](https://github.com/Jielumoon/Rainyun-Qiandao)

## 라이선스

[MIT License](https://github.com/666fy666/WebMoniter/blob/main/LICENSE)

<div align="center">

**이 프로젝트가 도움이 되었다면 ⭐ Star를 눌러 주세요!**

Made with ❤️ by [FY](https://github.com/666fy666)

</div>
