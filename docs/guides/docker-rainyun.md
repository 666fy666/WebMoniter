# Docker 下使用雨云签到（挂载宿主机 Chromium）

镜像**不内置** Chromium，以减小镜像体积。使用**雨云签到**时，需在**宿主机**安装 Chromium 与 chromedriver，再通过 Docker 卷挂载进容器。

---

## 1. 宿主机安装 Chromium

容器内已包含 Chromium 运行所需的库（如 libnss3、libgbm、libx11 等），只需在宿主机安装**可执行文件**并挂载进容器。

### Debian / Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y chromium chromium-driver
```

安装后一般为：

- Chromium：`/usr/bin/chromium` 或 `/usr/bin/chromium-browser`
- chromedriver：`/usr/bin/chromedriver`

若包名不同，可尝试：

```bash
sudo apt-get install -y chromium-browser chromium-chromedriver
```

安装完成后确认路径：

```bash
which chromium    # 或 which chromium-browser
which chromedriver
```

### 其他 Linux 发行版

- **Fedora / RHEL**：`sudo dnf install chromium chromedriver`，路径多为 `/usr/bin/chromium`、`/usr/bin/chromedriver`
- **Arch**：`sudo pacman -S chromium chromium-driver`
- 若宿主机与镜像基础（Debian）不同，建议与容器同架构（如均为 amd64），且尽量使用同系发行版，以减少依赖库差异导致的兼容问题

---

## 2. 在 docker-compose 中挂载浏览器

在 `docker-compose.yml` 中为服务增加**卷挂载**和**环境变量**，使容器内使用宿主机上的 Chromium。

### 挂载卷

将宿主机上的 Chromium 与 chromedriver **挂载到容器内相同路径**（只读即可）：

```yaml
volumes:
  - ./config.yml:/app/config.yml
  - ./data:/app/data
  - ./logs:/app/logs
  # 雨云签到：挂载宿主机 Chromium（宿主机需先安装）
  - /usr/bin/chromium:/usr/bin/chromium:ro
  - /usr/bin/chromedriver:/usr/bin/chromedriver:ro
```

若宿主机上可执行文件路径不同，按实际路径修改，例如：

- Chromium 为 `/usr/bin/chromium-browser` 时：
  ```yaml
  - /usr/bin/chromium-browser:/usr/bin/chromium:ro
  ```
- chromedriver 在 `/usr/lib/chromium/chromedriver` 时：
  ```yaml
  - /usr/lib/chromium/chromedriver:/usr/bin/chromedriver:ro
  ```

### 环境变量

容器内通过环境变量指定要使用的浏览器路径，需与**容器内**路径一致（即上面挂载的**右侧**路径）：

```yaml
environment:
  - CHROME_BIN=/usr/bin/chromium
  - CHROMEDRIVER_PATH=/usr/bin/chromedriver
```

若你挂载到了其他容器内路径，这里也要一起改，例如：

```yaml
  - CHROME_BIN=/usr/bin/chromium-browser
  - CHROMEDRIVER_PATH=/usr/bin/chromedriver
```

项目已内置从环境变量读取 `CHROME_BIN`、`CHROMEDRIVER_PATH`，无需在 `config.yml` 里再配 `chrome_bin` / `chromedriver_path`（除非你要覆盖环境变量）。

---

## 3. 不需要雨云签到时

若**不启用**雨云签到（`config.yml` 中 `rainyun.enable: false` 或不配置雨云），可注释掉上述两行卷挂载，避免宿主机未安装 Chromium 时挂载失败或报错：

```yaml
volumes:
  - ./config.yml:/app/config.yml
  - ./data:/app/data
  - ./logs:/app/logs
  # - /usr/bin/chromium:/usr/bin/chromium:ro
  # - /usr/bin/chromedriver:/usr/bin/chromedriver:ro
```

同时可注释环境变量（可选）：

```yaml
  # - CHROME_BIN=/usr/bin/chromium
  # - CHROMEDRIVER_PATH=/usr/bin/chromedriver
```

---

## 4. 配置雨云签到

在 `config.yml` 中启用雨云并填写账号：

```yaml
rainyun:
  enable: true
  accounts:
    - username: 你的雨云账号
      password: 你的雨云密码
      api_key:   # 可选，用于服务器续费
  time: "08:30"
  push_channels: []
```

保存后配置会热重载，无需重启容器。

---

## 5. 故障排查

| 现象 | 可能原因 | 处理建议 |
|:-----|:--------|:--------|
| 容器启动报错或卷挂载失败 | 宿主机没有 Chromium/chromedriver 或路径不对 | 在宿主机执行 `which chromium chromedriver` 确认路径，或在 compose 中注释掉这两行卷（见上文） |
| 雨云任务报错“找不到 Chrome” | 环境变量与挂载路径不一致 | 确认 `CHROME_BIN`、`CHROMEDRIVER_PATH` 与卷挂载的**容器内**路径一致 |
| 容器内 Chromium 启动失败（如缺库） | 宿主机与镜像发行版/架构差异大 | 建议宿主机使用 Debian/Ubuntu（与镜像一致），或换用与镜像同系的发行版 |
| 权限错误 | 宿主机二进制权限或 SELinux | 宿主机上 `chmod +x /usr/bin/chromium /usr/bin/chromedriver`；SELinux 下可尝试 `:z` 或 `:ro,z`（按你环境调整） |

进入容器排查时可执行：

```bash
docker exec -it webmoniter sh
ls -la /usr/bin/chromium /usr/bin/chromedriver   # 确认挂载存在
echo $CHROME_BIN $CHROMEDRIVER_PATH              # 确认环境变量
```

---

## 6. 小结

1. **宿主机**安装 Chromium 与 chromedriver（如 `apt install chromium chromium-driver`）。
2. 在 **docker-compose** 中挂载两个可执行文件到容器（如 `/usr/bin/chromium`、`/usr/bin/chromedriver`），并设置 `CHROME_BIN`、`CHROMEDRIVER_PATH`。
3. 不使用雨云签到时，注释掉上述挂载与相关环境变量即可。

更多雨云配置说明见 [雨云签到（定时任务）](tasks/checkin.md#雨云签到)，常见问题见 [FAQ：Docker 下雨云签到](../faq.md)。
