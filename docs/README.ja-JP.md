<div align="center">

# WebMoniter

**マルチプラットフォーム監視 · 自動チェックイン · 配信通知 · マルチチャネル通知**

<sub>監視 · チェックイン · 配信通知 · プッシュ通知 · 定期タスク · 設定のホットリロード</sub>

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

[中文](../README.md) · [English](README.en-US.md) · [Español](README.es-ES.md) · **日本語** · [한국어](README.ko-KR.md)

[ドキュメント](https://666fy666.github.io/WebMoniter/) ·
[インストール](installation.md) ·
[設定](guides/config.md) ·
[API](API.md) ·
[二次開発](SECONDARY_DEVELOPMENT.md) ·
[リリース](https://github.com/666fy666/WebMoniter/releases/latest)

**コードリポジトリ**：[GitHub](https://github.com/666fy666/WebMoniter) · [GitCode](https://gitcode.com/qq_35720175/WebMoniter)

</div>

---

## 概要

WebMoniter は Python、FastAPI、APScheduler をベースにしたタスクシステムです。次の機能を一元管理できます。

- Huya、Weibo、Bilibili、Douyin、Douyu、Xiaohongshu のプラットフォーム監視。
- Weibo Cookie 更新、iKuuu、Tieba、Weibo Super Topic、Rainyun、Aliyun Drive、Freenom、天気通知など、**30 種類の定期チェックイン／通知タスク**（`src/jobs/registry.py` を参照）。
- WeCom、DingTalk、Feishu、Telegram、Bark、WxPusher、メールなど、**18 種類の通知チャネル**。
- 設定編集、タスク管理、データ表示、ログ閲覧、パスワード管理を行う Web 管理画面。

設定はホットリロードに対応しており、`config.yml` の変更は通常約 5 秒以内に反映されます。

---

## 主な機能

画面と機能の詳細は[ドキュメントトップ](index.md)および [Web 管理画面ガイド](guides/web-ui.md)を参照してください。

<details>
<summary><strong>対応プラットフォーム、タスク、通知チャネルを表示</strong></summary>

### 対応プラットフォーム

| プラットフォーム | `type` | 投稿 | 配信開始／終了 |
|:--:|:--:|:--:|:--:|
| Huya | `huya` | いいえ | はい |
| Weibo | `weibo` | はい | いいえ |
| Bilibili | `bilibili` | はい | はい |
| Douyin | `douyin` | いいえ | はい |
| Douyu | `douyu` | いいえ | はい |
| Xiaohongshu | `xhs` | はい | いいえ |

### 定期タスク（一部）

| タスク | 設定キー | デフォルト時刻 |
|:--:|:--:|:--:|
| ログ削除 | `log_cleanup` | 02:10 |
| Weibo Cookie 更新 | `weibo` | 21:00 |
| iKuuu チェックイン | `checkin` | 08:00 |
| Rainyun チェックイン | `rainyun` | 08:30 |
| Tieba チェックイン | `tieba` | 08:10 |
| Weibo Super Topic | `weibo_chaohua` | 23:45 |
| Aliyun Drive | `aliyun` | 05:30 |
| 天気通知 | `weather` | 07:30 |

### 通知チャネル（一部）

| チャネル | `type` | リッチコンテンツ |
|:--:|:--:|:--:|
| WeCom グループ Bot | `wecom_bot` | はい |
| DingTalk Bot | `dingtalk_bot` | はい |
| Feishu Bot | `feishu_bot` | いいえ |
| Telegram | `telegram_bot` | はい |
| WxPusher | `wxpusher` | はい |
| Bark | `bark` | いいえ |
| PushPlus | `pushplus` | はい |

</details>

---

## クイックスタート

### Docker

軽量版の `latest` イメージは、多くの監視タスクと HTTP チェックインに適しています。`full` イメージにはブラウザと関連依存関係が追加されており、Weibo Cookie 更新、iKuuu、Rainyun など Web ログインが必要なタスクに使用します。

**Docker Compose で軽量版を起動（推奨）**

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

`http://localhost:8866` を開きます。初期アカウントは `admin` / `123` です。初回ログイン後に必ずパスワードを変更してください。

ブラウザを使用するタスクでは完全版を起動します。

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
<summary><strong>単一コンテナで起動</strong></summary>

軽量版：

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

完全版：

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

コンテナ名を指定して `docker stop`、`docker start`、`docker restart` で管理できます。ポート、ボリューム、更新、データ保持については[インストールと実行](installation.md)および [docker/README.md](../docker/README.md)を参照してください。

</details>

### ローカル実行

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter

uv python install 3.11
uv venv --python 3.11
uv sync --locked --extra dev --extra rainyun
cp config/config.yml.sample config.yml
uv run python main.py
```

ブラウザを使用するチェックインが不要な場合は、`uv sync --locked --extra dev` でコア依存関係と開発用依存関係のみをインストールできます。

### Windows パッケージ

[Releases](https://github.com/666fy666/WebMoniter/releases/latest) から `WebMoniter-vX.X.X-windows-x64.zip` をダウンロードして展開し、`config.yml.sample` を `config.yml` としてコピーしてから `WebMoniter.exe` をダブルクリックします。

### Qinglong パネル

Qinglong では環境変数で設定し、`python -m src.ql <task_id>` で定期タスクを実行できます。詳細は [Qinglong 互換ガイド](QINGLONG.md)を参照してください。

---

## 設定

メインの設定ファイルはリポジトリ直下の `config.yml` です。初回はテンプレートから作成します。

```bash
cp config/config.yml.sample config.yml
```

- [設定ガイド](guides/config.md)
- [監視タスクと定期タスク](guides/tasks.md)
- [通知チャネル](guides/push-channels.md)

---

## ドキュメント一覧

| 項目 | ドキュメント |
|---|---|
| インストール | [installation.md](installation.md) |
| Web 管理画面 | [guides/web-ui.md](guides/web-ui.md) |
| タスク設定 | [guides/tasks.md](guides/tasks.md) |
| 監視タスク | [guides/tasks/monitors.md](guides/tasks/monitors.md) |
| チェックインタスク | [guides/tasks/checkin.md](guides/tasks/checkin.md) |
| 通知チャネル | [guides/push-channels.md](guides/push-channels.md) |
| REST API | [API.md](API.md) |
| アーキテクチャ | [ARCHITECTURE.md](ARCHITECTURE.md) |
| 二次開発 | [SECONDARY_DEVELOPMENT.md](SECONDARY_DEVELOPMENT.md) |
| よくある質問 | [faq.md](faq.md) |

---

<details>
<summary><strong>開発</strong></summary>

```bash
uv sync --extra dev --extra rainyun
uv run ruff check .
uv run black --check .
uv run pytest -q
```

監視または定期タスクを追加する場合は[二次開発ガイド](SECONDARY_DEVELOPMENT.md)を参照してください。`src/tests/` のテストはメタデータ、レジストリ、enable マッピングの整合性を検証します。モジュール構成の詳細は[アーキテクチャ](ARCHITECTURE.md)にあります。

</details>

---

## 謝辞

チェックインおよび通知の一部は、次のプロジェクトを参考にしています。

- [aio-dynamic-push](https://github.com/nfe-w/aio-dynamic-push)
- [only_for_happly](https://github.com/wd210010/only_for_happly)
- [RainyunCheckIn](https://github.com/FalseHappiness/RainyunCheckIn)
- [Rainyun-Qiandao](https://github.com/Jielumoon/Rainyun-Qiandao)

## ライセンス

[MIT License](../LICENSE)

<div align="center">

**このプロジェクトが役に立ったら、⭐ Star をお願いします！**

Made with ❤️ by [FY](https://github.com/666fy666)

</div>
