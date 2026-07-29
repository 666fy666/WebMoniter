<div align="center">

# WebMoniter

**Monitoreo Multiplataforma · Registro de Asistencia (Check-in) · Notificaciones de Transmisión · Notificaciones Multicanal**

<sub>Monitoreo · Registro · Avisos de Vivo · Notificaciones · Tareas Programadas · Recarga Dinámica de Configuración</sub>

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-Web%20UI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-multi--arch-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/r/fengyu666/webmoniter)
[![APScheduler](https://img.shields.io/badge/APScheduler-scheduler-blueviolet?style=flat-square)](https://apscheduler.readthedocs.io/)
[![uv](https://img.shields.io/badge/uv-package%20manager-DE5FE9?style=flat-square)](https://docs.astral.sh/uv/)
[![docs](https://img.shields.io/badge/docs-online-1997B5?style=flat-square&logo=readme&logoColor=white)](https://666fy666.github.io/WebMoniter/)
[![GitHub Stars](https://img.shields.io/github/stars/666fy666/WebMoniter?style=flat-square&logo=github)](https://github.com/666fy666/WebMoniter/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/666fy666/WebMoniter?style=flat-square&logo=github)](https://github.com/666fy666/WebMoniter/forks)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/666fy666/WebMoniter?style=flat-square&logo=github)](https://github.com/666fy666/WebMoniter/commits/main)
[![Docker Pulls](https://img.shields.io/docker/pulls/fengyu666/webmoniter?style=flat-square&logo=docker)](https://hub.docker.com/r/fengyu666/webmoniter)
[![Docker Image Version](https://img.shields.io/docker/v/fengyu666/webmoniter/latest?style=flat-square&logo=docker&label=latest)](https://hub.docker.com/r/fengyu666/webmoniter/tags)
[![Docker Image Size (latest)](https://img.shields.io/docker/image-size/fengyu666/webmoniter/latest?style=flat-square&logo=docker&label=latest%20size)](https://hub.docker.com/r/fengyu666/webmoniter/tags)
[![Docker Image Size (full)](https://img.shields.io/docker/image-size/fengyu666/webmoniter/full?style=flat-square&logo=docker&label=full%20size)](https://hub.docker.com/r/fengyu666/webmoniter/tags)
[![GitHub Release](https://img.shields.io/github/v/release/666fy666/WebMoniter?style=flat-square&logo=github&label=EXE)](https://github.com/666fy666/WebMoniter/releases/latest)

[Sitio de Documentación](https://666fy666.github.io/WebMoniter/) ·
[Instalación](docs/installation.md) ·
[Configuración](docs/guides/config.md) ·
[API](docs/API.md) ·
[Desarrollo Secundario](docs/SECONDARY_DEVELOPMENT.md) ·
[Releases](https://github.com/666fy666/WebMoniter/releases/latest)

**Repositorios de código**: [GitHub](https://github.com/666fy666/WebMoniter) · [GitCode](https://gitcode.com/qq_35720175/WebMoniter)

</div>

---

## Introducción

WebMoniter es un sistema de tareas basado en Python, FastAPI y APScheduler, diseñado para la gestión unificada de:

- Monitoreo de plataformas: Huya, Weibo, Bilibili, Douyin, Douyu, Xiaohongshu.
- Tareas programadas: **30 tareas** de registro (check-in) y recordatorios, incluyendo actualización de cookies de Weibo, iKuuu, Tieba, Super Topic de Weibo, Rainyun, Aliyun Drive, Freenom, notificaciones meteorológicas, etc. (ver `src/jobs/registry.py`).
- Notificaciones multicanal: **18 tipos** de canales como WeChat Work, DingTalk, Feishu, Telegram, Bark, WxPusher, Email, etc.
- Gestión Web: Edición de configuración, gestión de tareas, visualización de datos, visualización de logs y gestión de contraseñas.

La configuración admite recarga en caliente; los cambios en `config.yml` suelen surtir efecto en aproximadamente 5 segundos.

---

## Vista General de Funciones

Para más detalles sobre la interfaz y las funciones, consulte la [Página Principal de Documentación](docs/index.md) y la [Interfaz de Gestión Web](docs/guides/web-ui.md).

<details>
<summary><strong>Expandir más detalles del proyecto</strong></summary>

### Plataformas Soportadas

| Plataforma | type | Dinámicas | Inicio/Fin de Vivo |
|:--:|:--:|:--:|:--:|
| Huya | `huya` | No | Sí |
| Weibo | `weibo` | Sí | No |
| Bilibili | `bilibili` | Sí | Sí |
| Douyin | `douyin` | No | Sí |
| Douyu | `douyu` | No | Sí |
| Xiaohongshu | `xhs` | Sí | No |

### Selección de Tareas Programadas

| Tarea | Nodo de Configuración | Hora Predeterminada |
|:--:|:--:|:--:|
| Limpieza de Logs | `log_cleanup` | 02:10 |
| Actualización Cookie Weibo | `weibo` | 21:00 |
| Registro iKuuu | `checkin` | 08:00 |
| Registro Rainyun | `rainyun` | 08:30 |
| Registro Tieba | `tieba` | 08:10 |
| Weibo Super Topic | `weibo_chaohua` | 23:45 |
| Aliyun Drive | `aliyun` | 05:30 |
| Notificación Clima | `weather` | 07:30 |

### Selección de Canales de Notificación

| Canal | type | Imagen/Texto |
|:--:|:--:|:--:|
| Robot de grupo WeChat Work | `wecom_bot` | Sí |
| Robot DingTalk | `dingtalk_bot` | Sí |
| Robot Feishu | `feishu_bot` | No |
| Telegram | `telegram_bot` | Sí |
| WxPusher | `wxpusher` | Sí |
| Bark | `bark` | No |
| PushPlus | `pushplus` | Sí |

</details>

---

## Inicio Rápido

### Docker

La imagen ligera `latest` es adecuada para la mayoría de las tareas de monitoreo y registros HTTP. La imagen completa `full` incluye adicionalmente el navegador y las dependencias de registro vía navegador, necesarias para tareas que requieren inicio de sesión web como la actualización de cookies de Weibo, iKuuu, Rainyun, etc. En amd64, la imagen `full` utiliza Google Chrome Stable + chromedriver de la misma versión.

**Arranque con Docker Compose Imagen Ligera (Recomendado)**

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
cp config/config.yml.sample config.yml

# Imagen ligera: Iniciar
docker compose -f docker/docker-compose.yml pull
docker compose -f docker/docker-compose.yml up -d

# Imagen ligera: Ver logs, detener, iniciar, reiniciar, eliminar contenedores/redes
docker compose -f docker/docker-compose.yml logs -f
docker compose -f docker/docker-compose.yml stop
docker compose -f docker/docker-compose.yml start
docker compose -f docker/docker-compose.yml restart
docker compose -f docker/docker-compose.yml down
```

Acceda a `http://localhost:8866`, cuenta predeterminada `admin` / `123`. Por favor, cambie la contraseña tras el primer inicio de sesión.

Para tareas de navegador como actualización de cookies de Weibo, iKuuu, Rainyun, etc., utilice la imagen completa:

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
<summary><strong>Contenedor Único · Imagen Ligera</strong></summary>

```bash
docker pull fengyu666/webmoniter:latest
docker run -d --name webmoniter --restart unless-stopped \
  -p 8866:8866 --shm-size=128m \
  -e TZ=Asia/Shanghai \
  -v "$(pwd)/config.yml:/app/config.yml" \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/logs:/app/logs" \
  fengyu666/webmoniter:latest

docker stop webmoniter
docker start webmoniter
docker restart webmoniter
# Eliminar contenedor; si está corriendo use docker rm -f webmoniter
docker rm webmoniter
docker image rm fengyu666/webmoniter:latest
```

</details>

<details>
<summary><strong>Contenedor Único · Imagen Completa</strong></summary>

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

docker stop webmoniter-full
docker start webmoniter-full
docker restart webmoniter-full
# Eliminar contenedor; si está corriendo use docker rm -f webmoniter-full
docker rm webmoniter-full
docker image rm fengyu666/webmoniter:full
```

En Windows PowerShell, si encuentra problemas con la ruta de montaje, cambie `$(pwd)` por la ruta absoluta del directorio actual. Para más detalles sobre puertos, montajes, actualizaciones y retención de datos, consulte [Instalación y Ejecución](docs/installation.md) y [docker/README.md](docker/README.md).

</details>

### Ejecución Local

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter

uv python install 3.11
uv venv --python 3.11
uv sync --locked --extra dev --extra rainyun
cp config/config.yml.sample config.yml
uv run python main.py
```

Si no utiliza el registro mediante navegador, puede instalar solo las dependencias principales y de desarrollo:

```bash
uv sync --locked --extra dev
```

### Paquete "Un Click" para Windows

Descargue `WebMoniter-vX.X.X-windows-x64.zip` desde [Releases](https://github.com/666fy666/WebMoniter/releases/latest), descomprima, copie `config.yml.sample` como `config.yml` y ejecute `WebMoniter.exe` con doble clic.

### Panel Qinglong

Los usuarios de Qinglong pueden configurar a través de variables de entorno y ejecutar tareas programadas usando `python -m src.ql <task_id>`. Para más detalles, vea la [Guía de compatibilidad con Panel Qinglong](docs/QINGLONG.md).

---

## Configuración

El archivo de configuración central es `config.yml` en la raíz del repositorio. Para el primer uso, copie la plantilla:

```bash
cp config/config.yml.sample config.yml
```

Para más información sobre los elementos de configuración, consulte:

- [Explicación de la Configuración](docs/guides/config.md)
- [Monitoreo y Tareas Programadas](docs/guides/tasks.md)
- [Canales de Notificación](docs/guides/push-channels.md)

---

## Accesos a Funciones

| Función | Documentación |
|---|---|
| Instalación y Despliegue | [docs/installation.md](docs/installation.md) |
| Interfaz de Gestión Web | [docs/guides/web-ui.md](docs/guides/web-ui.md) |
| Configuración de Tareas | [docs/guides/tasks.md](docs/guides/tasks.md) |
| Tareas de Monitoreo | [docs/guides/tasks/monitors.md](docs/guides/tasks/monitors.md) |
| Tareas de Registro | [docs/guides/tasks/checkin.md](docs/guides/tasks/checkin.md) |
| Canales de Notificación | [docs/guides/push-channels.md](docs/guides/push-channels.md) |
| REST API | [docs/API.md](docs/API.md) |
| Descripción de Arquitectura | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Desarrollo Secundario | [docs/SECONDARY_DEVELOPMENT.md](docs/SECONDARY_DEVELOPMENT.md) |
| Preguntas Frecuentes | [docs/faq.md](docs/faq.md) |

---

<details>
<summary><strong>Notas de Desarrollo</strong></summary>

```bash
uv sync --extra dev --extra rainyun
uv run ruff check .
uv run black --check .
uv run pytest -q
```

Para agregar nuevos monitoreos o tareas programadas, consulte la [Guía de Desarrollo Secundario](docs/SECONDARY_DEVELOPMENT.md). En `src/tests/` hay pruebas de consistencia para metadata, registro y mapeo de habilitación; `uv run pytest` fallará si falta alguna configuración. Para una descripción completa de la arquitectura, vea [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). El proyecto utiliza actualmente una estructura modular:

| Módulo | Responsabilidad |
|------|------|
| `main.py` | Punto de entrada: Web, Programador, Recarga dinámica, Cierre elegante |
| `src/core/` | Tiempo de ejecución (`runtime.py` watchdog de salida 12s), Rutas (`paths.py`), Versión, Herramientas HTTP |
| `src/settings/` | Modelos de configuración (`config.py`), Mapeo YAML (`loader_specs.py`), Recarga dinámica (`watcher.py`), Sincronización DB (`db_sync.py`) |
| `src/jobs/` | Metadatos de tareas (`metadata.py`), Programación (`scheduler.py`), Registro (`registry.py`), Mapeo de habilitación (`enable_fields.py`), Resultados de tarea (`task_outcome.py`), Ciclo de vida (`lifecycle.py`), Logs (`log_manager.py`), Registro de ejecución (`tracker.py`) |
| `src/storage/` | SQLite (`database.py`), Caché de Cookies (`cookie_cache.py`) |
| `src/monitors/` | Monitoreo de 6 plataformas (disparado por intervalo, lista generada por `metadata.MONITOR_SPECS`) |
| `src/tasks/` | 30 tareas de registro/programadas (disparado por Cron, incluye subpaquete `rainyun/`, lista generada por `metadata.TASK_SPECS`) |
| `src/push_channel/` | 18 tipos de notificaciones (WeChat Work, DingTalk, Telegram, etc., incluye `demo`, `qlapi`) |
| `src/web/` | Aplicación FastAPI (`app.py`), Rutas (`routers/`), Auxiliares de autenticación/config/datos, `templating.py`, `static_files.py` |
| `src/webUI/` | Recursos estáticos frontend y plantillas Jinja2 |
| `src/ql/` | CLI de Qinglong (`python -m src.ql <task_id>`, compatibilidad de variables de entorno en `compat.py`) |
| `src/tests/` | Pruebas unitarias y smoke tests con pytest |

</details>

---

## Agradecimientos

Algunas ideas de registro y notificaciones se basaron en los siguientes proyectos:

- [aio-dynamic-push](https://github.com/nfe-w/aio-dynamic-push)
- [only_for_happly](https://github.com/wd210010/only_for_happly)
- [RainyunCheckIn](https://github.com/FalseHappiness/RainyunCheckIn)
- [Rainyun-Qiandao](https://github.com/Jielumoon/Rainyun-Qiandao)

---

## Contributors

<a href="https://github.com/666fy666/WebMoniter/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=666fy666/WebMoniter" alt="Contributors" />
</a>

---

## Star History

<a href="https://www.star-history.com/?type=date&repos=666fy666%2FWebMoniter">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=666fy666/WebMoniter&type=date&theme=dark&legend=top-left&sealed_token=_5ZVFJzKqU7_wg-KVdKrKUkkMj35yaXuBxHrWm8162OiC9NNzbOAIQ9OG5radniZEsxW86qcYUpzuN3zAYsQWUZNOf_6VzxJGqjIUtAI-nSadvI5xEdSqgSTqkiN5N3Ui5oGw_BXQQ8mCT32TQXY1uzJLz_c3Pyq7we_jYGxNcscsxqhsAYBGcMAji0V" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=666fy666/WebMoniter&type=date&legend=top-left&sealed_token=_5ZVFJzKqU7_wg-KVdKrKUkkMj35yaXuBxHrWm8162OiC9NNzbOAIQ9OG5radniZEsxW86qcYUpzuN3zAYsQWUZNOf_6VzxJGqjIUtAI-nSadvI5xEdSqgSTqkiN5N3Ui5oGw_BXQQ8mCT32TQXY1uzJLz_c3Pyq7we_jYGxNcscsxqhsAYBGcMAji0V" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=666fy666/WebMoniter&type=date&legend=top-left&sealed_token=_5ZVFJzKqU7_wg-KVdKrKUkkMj35yaXuBxHrWm8162OiC9NNzbOAIQ9OG5radniZEsxW86qcYUpzuN3zAYsQWUZNOf_6VzxJGqjIUtAI-nSadvI5xEdSqgSTqkiN5N3Ui5oGw_BXQQ8mCT32TQXY1uzJLz_c3Pyq7we_jYGxNcscsxqhsAYBGcMAji0V" />
 </picture>
</a>

---

## Licencia

[MIT License](LICENSE)

<div align="center">

**¡Si este proyecto te ha sido útil, por favor danos una ⭐ Star!**

Hecho con ❤️ por [FY](https://github.com/666fy666)

</div>
