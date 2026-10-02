> 以下の導入・保守コマンドは現在の Compose 構成に対応しています。バックアップ、HTTPS、復元は[デプロイガイド](DEPLOYMENT.md)を参照してください。

<div align="center">

# WebMoniter

**マルチプラットフォーム監視 · 自動チェックイン · 配信通知 · マルチチャネル通知**

<sub>監視 · チェックイン · 配信通知 · プッシュ通知 · 定期タスク · 設定のホットリロード</sub>

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
- Weibo Cookie 更新、iKuuu、Tieba、Weibo Super Topic、Rainyun、Aliyun Drive、Freenom、天気通知など、**30 種類の定期チェックイン／通知タスク**（加えて `demo_task` サンプル；一覧は `src/jobs/metadata.py` の `TASK_SPECS`）。
- WeCom、DingTalk、Feishu、Telegram、Bark、WxPusher、メールなど、**18 種類の通知チャネル**。
- 設定、タスク、データ、ログ、パスワードを管理するレスポンシブ Web UI。ナビゲーション、ツールバー、ダイアログ、操作部品には Liquid Glass スタイルを採用し、デスクトップのサイドバー、モバイルの下部ナビゲーション、キーボード操作、動き／透明度を抑える設定に対応します。

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
| 快手（実環境での検証待ち） | `kuaishou` | いいえ | はい |
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

既定の **full** イメージにはブラウザ、ドライバ、OCR が含まれます。`latest` はこれらを含まない軽量版です。Weibo Cookie 更新、iKuuu、Rainyun のブラウザタスクには full を使用してください。サービスを動かすマシンで実行します。

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh docker
```

Ubuntu 22.04/24.04/26.04 で Docker Engine と Compose が未導入の場合、スクリプトがインストールします（root または sudo が必要）。full を取得してバックグラウンドで起動します。他の OS では先に Docker と Compose を準備してください。導入済みならスクリプトの代わりに `docker compose up -d --pull always --wait --wait-timeout 180` を実行できます。

ローカルでは **http://127.0.0.1:8866**、リモートでは `http://サーバーIP:8866` を開きます。現在のマッピングは `0.0.0.0:8866:8866` です。ファイアウォールとセキュリティグループで必要な接続元からの TCP 8866 を許可し、外部公開前に初期パスワードを変更してください。SSH またはホストのリバースプロキシのみを使う場合は `127.0.0.1:8866:8866` に変更し、Compose `up` を再実行します。SSH トンネルは手元のパソコンで接続先を書き換えて以下を実行し、接続を維持したままローカル URL を開きます。

```bash
ssh -N -L 8866:127.0.0.1:8866 user@server
```

**`admin` / `123`** でログインしてパスワードを変更し、通知先、アカウント、監視対象を設定して必要なタスクを有効にしてください。業務タスクは初期状態では無効です。実行結果はログで確認でき、設定変更は通常約 5 秒で反映されます。既存アカウントのパスワードは維持されます。

#### 更新・停止・削除

保守コマンドは元のリポジトリ直下で実行します。独自の `-f`、`-p`、`--env-file`、上書きファイルを使っている場合は同じ指定を維持し、権限が必要なら `sudo` を付けてください。まず[バックアップ](DEPLOYMENT.md#backup-restore)を取り、各コマンドの成功を確認してから次へ進みます。

```bash
git pull --ff-only
docker compose up -d --pull always --wait --wait-timeout 180
docker compose ps
docker compose logs --tail=100 web-monitor
```

`git pull` はリポジトリのみを更新します。`pull` はイメージの取得のみ、`restart` は元のイメージの再起動です。公開済みイメージの適用には `up --pull always` を使います。`WEBMONITER_IMAGE` でバージョンや digest を固定している場合は先に変更してください。未公開の変更は[ローカルビルド](https://github.com/666fy666/WebMoniter/blob/main/docker/README.md#local-build)後に `up --pull never` で起動します。

| 目的 | コマンド | データ |
|---|---|---|
| 状態確認 | `docker compose ps` | 変更なし |
| ログを追跡 | `docker compose logs --tail=100 -f web-monitor` | Ctrl+C はログ表示だけを終了 |
| サービスとタスクを停止 | `docker compose stop` | コンテナとデータを保持 |
| 停止したコンテナを再開 | `docker compose start` | 元のデータを保持 |
| 現在のコンテナを再起動 | `docker compose restart` | イメージは更新しない |
| コンテナとネットワークを削除 | `docker compose down` | 名前付きボリュームを保持 |
| down 後に再開 | `docker compose up -d --wait --wait-timeout 180` | 元のボリュームを再利用 |

**完全削除：設定、アカウント、Cookie、履歴、ログを削除します。事前にバックアップしてください。元に戻せません。**

```bash
docker compose down --volumes
```

既定のボリュームは `webmoniter_config`（`/app/config`）、`webmoniter_data`（`/app/data`）、`webmoniter_logs`（`/app/logs`）です。Docker はリポジトリ直下の `config.yml` や `./data` を使いません。更新では保持されますが、`down --volumes` はこれらを削除します。旧 bind mount のデータは自動移行されません。

コンテナ削除後、不要なイメージは `docker image rm fengyu666/webmoniter:full` で削除できます（利用中のタグに置換）。ソース、`.env`、バックアップ、ホストのマウント先、Docker 自体は残るため、不要なら個別に削除してください。このプロジェクトの削除に全体の prune は使わないでください。

### ローカル実行（Linux）

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh source
```

スクリプトが Python 3.11、uv、Node 24、フロントエンド、ブラウザとドライバ、モデルを準備し、設定を自動生成してフォアグラウンドで起動します。HTTP タスクのみなら `bash install.sh source --no-browser` を使えます。Ctrl+C で停止します。更新時は停止とバックアップ後に `git pull --ff-only` を実行し、再びインストーラを実行します。環境の整理と削除は[ソース版の保守](installation.md#source-maintenance)を参照してください。

### Windows パッケージ

[Releases](https://github.com/666fy666/WebMoniter/releases/latest) から `WebMoniter-vX.X.X-windows-x64.zip` をダウンロードして展開し、`config.yml.sample` を `config.yml` としてコピーしてから `WebMoniter.exe` をダブルクリックします。

### Qinglong パネル

Qinglong では環境変数で設定し、`python -m src.ql <task_id>` で定期タスクを実行できます。詳細は [Qinglong 互換ガイド](QINGLONG.md)を参照してください。

---

## 設定

ソース版はリポジトリ直下の `config.yml`、Docker 版は設定ボリューム内の `/app/config/config.yml` を自動生成します。既存設定は保持されます。Web 設定画面で編集し、更新時にサンプルで上書きしないでください。

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

環境構築と検証コマンドは[開発ガイド](SECONDARY_DEVELOPMENT.md)、モジュール構成とデータフローは[アーキテクチャ](ARCHITECTURE.md)を参照してください。

</details>

---

## 謝辞

チェックインおよび通知の一部は、次のプロジェクトを参考にしています。

- [aio-dynamic-push](https://github.com/nfe-w/aio-dynamic-push)
- [only_for_happly](https://github.com/wd210010/only_for_happly)
- [RainyunCheckIn](https://github.com/FalseHappiness/RainyunCheckIn)
- [Rainyun-Qiandao](https://github.com/Jielumoon/Rainyun-Qiandao)

## ライセンス

[MIT License](https://github.com/666fy666/WebMoniter/blob/main/LICENSE)

<div align="center">

**このプロジェクトが役に立ったら、⭐ Star をお願いします！**

Made with ❤️ by [FY](https://github.com/666fy666)

</div>
