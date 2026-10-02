> Los comandos de despliegue y mantenimiento siguen la estructura actual de Compose. Consulte la [guía de despliegue](DEPLOYMENT.md) para copias de seguridad, HTTPS y recuperación.

<div align="center">

# WebMoniter

**Monitoreo Multiplataforma · Registro de Asistencia (Check-in) · Notificaciones de Transmisión · Notificaciones Multicanal**

<sub>Monitoreo · Registro · Avisos de Vivo · Notificaciones · Tareas Programadas · Recarga Dinámica de Configuración</sub>

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](https://github.com/666fy666/WebMoniter/blob/main/LICENSE)
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

[中文](../README.md) · [English](README.en-US.md) · **Español** · [日本語](README.ja-JP.md) · [한국어](README.ko-KR.md)

[Sitio de Documentación](https://666fy666.github.io/WebMoniter/) ·
[Instalación](installation.md) ·
[Configuración](guides/config.md) ·
[API](API.md) ·
[Desarrollo Secundario](SECONDARY_DEVELOPMENT.md) ·
[Releases](https://github.com/666fy666/WebMoniter/releases/latest)

**Repositorios de código**: [GitHub](https://github.com/666fy666/WebMoniter) · [GitCode](https://gitcode.com/qq_35720175/WebMoniter)

</div>

---

## Introducción

WebMoniter es un sistema de tareas basado en Python, FastAPI y APScheduler, diseñado para la gestión unificada de:

- Monitoreo de plataformas: Huya, Weibo, Bilibili, Douyin, Douyu, Xiaohongshu.
- Tareas programadas: **30 tareas** de registro (check-in) y recordatorios, incluyendo actualización de cookies de Weibo, iKuuu, Tieba, Super Topic de Weibo, Rainyun, Aliyun Drive, Freenom, notificaciones meteorológicas, etc. (más el ejemplo `demo_task`; ver `TASK_SPECS` en `src/jobs/metadata.py`).
- Notificaciones multicanal: **18 tipos** de canales como WeChat Work, DingTalk, Feishu, Telegram, Bark, WxPusher, Email, etc.
- Gestión Web responsive para configuración, tareas, datos, logs y contraseñas. La navegación, barras de herramientas, diálogos y controles usan un estilo Liquid Glass, con barra lateral en escritorio, navegación inferior en móvil y alternativas accesibles para movimiento y transparencia.

La configuración admite recarga en caliente; los cambios en `config.yml` suelen surtir efecto en aproximadamente 5 segundos.

---

## Vista General de Funciones

Para más detalles sobre la interfaz y las funciones, consulte la [Página Principal de Documentación](index.md) y la [Interfaz de Gestión Web](guides/web-ui.md).

<details>
<summary><strong>Expandir más detalles del proyecto</strong></summary>

### Plataformas Soportadas

| Plataforma | type | Dinámicas | Inicio/Fin de Vivo |
|:--:|:--:|:--:|:--:|
| Huya | `huya` | No | Sí |
| Weibo | `weibo` | Sí | No |
| Bilibili | `bilibili` | Sí | Sí |
| Douyin | `douyin` | No | Sí |
| Kuaishou (pendiente de validación real) | `kuaishou` | No | Sí |
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

La imagen predeterminada **full** incluye navegador, controlador y OCR. `latest` es la versión ligera sin estas dependencias. Las tareas de navegador de Weibo, iKuuu y Rainyun necesitan full. Ejecute en la máquina donde alojará el servicio:

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh docker
```

Si faltan Docker Engine y Compose, el script los instala en Ubuntu 22.04/24.04/26.04 (requiere root o sudo), descarga full y lo inicia en segundo plano. En otros sistemas, instale Docker y Compose primero. Si ya dispone de Compose, puede sustituir el script por `docker compose up -d --pull always --wait --wait-timeout 180`.

Abra **http://127.0.0.1:8866** localmente o `http://IP_DEL_SERVIDOR:8866` de forma remota. El mapeo actual es `0.0.0.0:8866:8866`; permita TCP 8866 desde los clientes previstos en el cortafuegos y el grupo de seguridad, y cambie la contraseña antes de exponer el servicio. Para usar solo SSH o un proxy en el host, cambie el mapeo a `127.0.0.1:8866:8866` y vuelva a ejecutar Compose `up`. Para el túnel SSH, ejecute lo siguiente en su ordenador, sustituya el destino y mantenga la conexión abierta; después abra la dirección local:

```bash
ssh -N -L 8866:127.0.0.1:8866 user@server
```

Inicie sesión con **`admin` / `123`**, cambie la contraseña y configure los canales, cuentas y objetivos antes de activar las tareas necesarias. Las tareas de negocio están desactivadas inicialmente. Revise los resultados en los registros; los cambios de configuración suelen aplicarse en unos 5 segundos. Las cuentas existentes conservan su contraseña.

#### Actualizar, detener y eliminar

Ejecute el mantenimiento desde la raíz original del repositorio. Conserve los mismos parámetros `-f`, `-p`, `--env-file` y archivos de personalización; añada `sudo` si necesita permisos de Docker. Primero [haga una copia de seguridad](DEPLOYMENT.md#backup-restore) y ejecute cada comando solo si el anterior termina correctamente:

```bash
git pull --ff-only
docker compose up -d --pull always --wait --wait-timeout 180
docker compose ps
docker compose logs --tail=100 web-monitor
```

`git pull` actualiza el repositorio, no la imagen. `pull` solo descarga y `restart` conserva la imagen anterior. `up --pull always` aplica una imagen publicada. Si `WEBMONITER_IMAGE` fija una versión o digest, modifíquelo primero. Los cambios aún no publicados requieren una [compilación local](https://github.com/666fy666/WebMoniter/blob/main/docker/README.md#local-build) y después `up --pull never`.

| Objetivo | Comando | Datos |
|---|---|---|
| Ver estado | `docker compose ps` | Sin cambios |
| Seguir registros | `docker compose logs --tail=100 -f web-monitor` | Ctrl+C solo cierra la vista de registros |
| Detener servicio y tareas | `docker compose stop` | Conserva contenedor y datos |
| Reanudar contenedor detenido | `docker compose start` | Conserva los datos |
| Reiniciar el contenedor actual | `docker compose restart` | No actualiza la imagen |
| Eliminar contenedores y red | `docker compose down` | Conserva los volúmenes |
| Reanudar después de down | `docker compose up -d --wait --wait-timeout 180` | Reutiliza los volúmenes |

**Desinstalación permanente: elimina configuración, cuentas, cookies, historial y registros. Haga una copia antes; no se puede deshacer:**

```bash
docker compose down --volumes
```

Los volúmenes predeterminados son `webmoniter_config` (`/app/config`), `webmoniter_data` (`/app/data`) y `webmoniter_logs` (`/app/logs`). Docker no utiliza `config.yml` ni `./data` de la raíz del repositorio. Las actualizaciones conservan estos volúmenes; `down --volumes` los elimina. Los montajes antiguos no se migran automáticamente.

Tras eliminar los contenedores, puede ejecutar `docker image rm fengyu666/webmoniter:full` para eliminar la imagen sin uso (sustituya la etiqueta si corresponde). El código, `.env`, las copias, los directorios montados y Docker permanecen; elimínelos por separado si ya no los necesita. No utilice una limpieza global para desinstalar este proyecto.

### Ejecución Local (Linux)

```bash
git clone https://github.com/666fy666/WebMoniter.git
cd WebMoniter
bash install.sh source
```

El instalador prepara Python 3.11, uv, Node 24, el frontend, el navegador/controlador y los modelos, y después ejecuta el servicio en primer plano. Crea la configuración automáticamente. Use `bash install.sh source --no-browser` para tareas solo HTTP. Detenga con Ctrl+C; para actualizar, detenga y haga una copia, ejecute `git pull --ff-only` y vuelva a ejecutar el instalador. Consulte el [mantenimiento desde código fuente](installation.md#source-maintenance) para limpiar o eliminar la instalación.

### Paquete "Un Click" para Windows

Descargue `WebMoniter-vX.X.X-windows-x64.zip` desde [Releases](https://github.com/666fy666/WebMoniter/releases/latest), descomprima, copie `config.yml.sample` como `config.yml` y ejecute `WebMoniter.exe` con doble clic.

### Panel Qinglong

Los usuarios de Qinglong pueden configurar a través de variables de entorno y ejecutar tareas programadas usando `python -m src.ql <task_id>`. Para más detalles, vea la [Guía de compatibilidad con Panel Qinglong](QINGLONG.md).

---

## Configuración

La instalación desde código crea `config.yml` en la raíz. Docker crea `/app/config/config.yml` en su volumen de configuración. Se conserva la configuración existente; edítela en la interfaz Web. No la sobrescriba con la plantilla al actualizar.

- [Explicación de la Configuración](guides/config.md)
- [Monitoreo y Tareas Programadas](guides/tasks.md)
- [Canales de Notificación](guides/push-channels.md)

---

## Accesos a Funciones

| Función | Documentación |
|---|---|
| Instalación y Despliegue | [installation.md](installation.md) |
| Interfaz de Gestión Web | [guides/web-ui.md](guides/web-ui.md) |
| Configuración de Tareas | [guides/tasks.md](guides/tasks.md) |
| Tareas de Monitoreo | [guides/tasks/monitors.md](guides/tasks/monitors.md) |
| Tareas de Registro | [guides/tasks/checkin.md](guides/tasks/checkin.md) |
| Canales de Notificación | [guides/push-channels.md](guides/push-channels.md) |
| REST API | [API.md](API.md) |
| Descripción de Arquitectura | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Desarrollo Secundario | [SECONDARY_DEVELOPMENT.md](SECONDARY_DEVELOPMENT.md) |
| Preguntas Frecuentes | [faq.md](faq.md) |

---

<details>
<summary><strong>Notas de Desarrollo</strong></summary>

El entorno y los comandos de validación se mantienen en la [guía de desarrollo](SECONDARY_DEVELOPMENT.md). Consulte [Arquitectura](ARCHITECTURE.md) para los módulos y el flujo de datos.

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

## Licencia

[MIT License](https://github.com/666fy666/WebMoniter/blob/main/LICENSE)

<div align="center">

**¡Si este proyecto te ha sido útil, por favor danos una ⭐ Star!**

Hecho con ❤️ por [FY](https://github.com/666fy666)

</div>
