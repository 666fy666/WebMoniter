"""Prepare a Linux source checkout and run it without manual environment setup."""

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
NODE_VERSION = "24.14.0"
CHROME_VERSION = "150.0.7871.100"


def run(args, *, capture=False):
    return subprocess.run(args, cwd=ROOT, check=True, text=True, capture_output=capture)


def download(url: str, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for attempt in range(3):
        try:
            with urlopen(url, timeout=60) as response, destination.open("wb") as target:
                shutil.copyfileobj(response, target, length=1024 * 1024)
            return
        except OSError as exc:
            last_error = exc
            destination.unlink(missing_ok=True)
            if attempt < 2:
                time.sleep(2**attempt)
    raise RuntimeError(f"下载失败：{url}，重试运行安装命令可继续") from last_error


def ensure_node(runtime: Path):
    local = runtime / f"node-v{NODE_VERSION}-{platform.system().lower()}-{platform.machine()}"
    if (local / "bin/node").is_file():
        os.environ["PATH"] = f"{local / 'bin'}{os.pathsep}{os.environ['PATH']}"
    if shutil.which("node") and shutil.which("npm"):
        try:
            major = int(
                run(
                    ["node", "-p", 'process.versions.node.split(".")[0]'], capture=True
                ).stdout.strip()
            )
            if major >= 24:
                return
        except (ValueError, subprocess.CalledProcessError):
            pass
    arch = {"x86_64": "x64", "aarch64": "arm64"}.get(platform.machine())
    if platform.system() != "Linux" or not arch:
        raise RuntimeError("自动安装 Node 支持 Linux x64/arm64；请安装 Node 24 与 npm 后重试")
    archive_name = f"node-v{NODE_VERSION}-linux-{arch}.tar.xz"
    base = f"https://nodejs.org/dist/v{NODE_VERSION}/"
    with tempfile.TemporaryDirectory(dir=runtime, prefix="node-") as directory:
        staging = Path(directory)
        archive, sums = staging / archive_name, staging / "SHASUMS256.txt"
        download(base + archive_name, archive)
        download(base + "SHASUMS256.txt", sums)
        checksums = {
            name: digest
            for digest, name in (line.split() for line in sums.read_text().splitlines())
        }
        with archive.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != checksums.get(archive_name):
            raise RuntimeError("Node 下载校验失败，请重新运行安装命令")
        with tarfile.open(archive) as bundle:
            bundle.extractall(staging, filter="data")
        if local.exists():
            shutil.rmtree(local)
        (staging / archive_name.removesuffix(".tar.xz")).rename(local)
    os.environ["PATH"] = f"{local / 'bin'}{os.pathsep}{os.environ['PATH']}"


def frontend_fingerprint(root: Path) -> str:
    frontend = root / "frontend"
    inputs = [
        frontend / name
        for name in (
            "package.json",
            "package-lock.json",
            "index.html",
            "vite.config.ts",
            "tsconfig.json",
        )
    ]
    inputs += [
        p
        for directory in ("src", "scripts")
        for p in (frontend / directory).rglob("*")
        if p.is_file()
    ]
    digest = hashlib.sha256()
    for path in sorted(inputs):
        digest.update(str(path.relative_to(frontend)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def build_frontend(runtime: Path):
    stamp = runtime / "frontend.sha256"
    fingerprint = frontend_fingerprint(ROOT)
    if (
        (ROOT / "frontend/dist/index.html").is_file()
        and stamp.is_file()
        and stamp.read_text() == fingerprint
    ):
        print("前端没有变化，复用已构建文件", flush=True)
        return
    ensure_node(runtime)
    run(["npm", "ci", "--prefix", "frontend"])
    run(["npm", "run", "build", "--prefix", "frontend"])
    stamp.write_text(fingerprint)


def install_browser_libraries(chrome: Path):
    result = subprocess.run(["ldd", str(chrome)], capture_output=True, text=True, check=False)
    if result.returncode == 0 and "not found" not in result.stdout:
        return
    release = platform.freedesktop_os_release()
    if release.get("ID") not in {"ubuntu", "debian"}:
        raise RuntimeError("Chrome 系统库不完整，请安装系统浏览器依赖后重新运行")
    root_command = [] if os.geteuid() == 0 else ["sudo"]
    run([*root_command, "apt-get", "update"])
    packages = [
        "libnss3",
        "libnspr4",
        "libdrm2",
        "libxkbcommon0",
        "libxcomposite1",
        "libxdamage1",
        "libxfixes3",
        "libxrandr2",
        "libgbm1",
        "libpango-1.0-0",
        "libcairo2",
        "libgl1",
        "fonts-liberation",
    ]
    for name in ("libglib2.0-0", "libatk1.0-0", "libatk-bridge2.0-0", "libcups2", "libasound2"):
        available = subprocess.run(
            ["apt-cache", "show", name + "t64"], capture_output=True, text=True, check=False
        )
        packages.append(
            name + "t64" if available.returncode == 0 and available.stdout.strip() else name
        )
    run([*root_command, "apt-get", "install", "-y", "--no-install-recommends", *packages])


def prepare_browser(runtime: Path):
    chrome = os.environ.get("CHROME_BIN")
    driver = os.environ.get("CHROMEDRIVER_PATH")
    if chrome or driver:
        if not (chrome and driver and os.access(chrome, os.X_OK) and os.access(driver, os.X_OK)):
            raise RuntimeError("自定义浏览器需要同时提供可执行的 CHROME_BIN 与 CHROMEDRIVER_PATH")
        return
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError(
            "自动准备浏览器支持 Linux x64；其他架构请设置浏览器/驱动路径，或用 --no-browser 启动 HTTP 任务"
        )
    directory = runtime / f"chrome-{CHROME_VERSION}"
    chrome_path = directory / "chrome-linux64/chrome"
    driver_path = directory / "chromedriver-linux64/chromedriver"
    if not chrome_path.is_file() or not driver_path.is_file():
        with tempfile.TemporaryDirectory(dir=runtime, prefix="chrome-") as temporary:
            staging = Path(temporary)
            for name in ("chrome", "chromedriver"):
                archive = staging / f"{name}.zip"
                download(
                    f"https://storage.googleapis.com/chrome-for-testing-public/{CHROME_VERSION}/linux64/{name}-linux64.zip",
                    archive,
                )
                with zipfile.ZipFile(archive) as bundle:
                    for member in bundle.infolist():
                        target = (staging / member.filename).resolve()
                        if not target.is_relative_to(staging.resolve()):
                            raise RuntimeError("浏览器归档包含非法路径")
                    bundle.extractall(staging)
                archive.unlink()
            for binary in (
                "chrome-linux64/chrome",
                "chrome-linux64/chrome_crashpad_handler",
                "chromedriver-linux64/chromedriver",
            ):
                (staging / binary).chmod(0o755)
            if directory.exists():
                shutil.rmtree(directory)
            staging.rename(directory)
    install_browser_libraries(chrome_path)
    os.environ.update(CHROME_BIN=str(chrome_path), CHROMEDRIVER_PATH=str(driver_path))
    chrome_version = run([str(chrome_path), "--version"], capture=True).stdout
    driver_version = run([str(driver_path), "--version"], capture=True).stdout
    if CHROME_VERSION not in chrome_version or CHROME_VERSION not in driver_version:
        raise RuntimeError("浏览器与驱动版本校验失败")


def prepare_source(*, browser=True):
    os.chdir(ROOT)
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("请通过 bash install.sh source 启动以自动安装 uv")
    print("准备 Python 3.11 和项目依赖…", flush=True)
    run([uv, "sync", "--frozen", "--python", "3.11", "--extra", "dev", "--extra", "rainyun"])
    python = ROOT / ".venv/bin/python"
    run([str(python), "-m", "src.settings.initialize"])
    print("检查前端产物…", flush=True)
    build_frontend(runtime)
    if browser:
        print("准备浏览器和本地模型，首次下载可能需要数分钟…", flush=True)
        prepare_browser(runtime)
        run([str(python), "src/tasks/ikuuu_models.py"])
    # The uv wrapper's environment must not override this checkout's own environment.
    os.environ["VIRTUAL_ENV"] = str(ROOT / ".venv")
    os.environ["PATH"] = f"{ROOT / '.venv/bin'}{os.pathsep}{os.environ['PATH']}"
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(key, "1")
    return python


def main():
    parser = argparse.ArgumentParser(description="一键准备并启动 WebMoniter 源码")
    parser.add_argument("--prepare-only", action="store_true", help="完成安装后退出")
    parser.add_argument(
        "--no-browser", action="store_true", help="跳过浏览器和模型安装，仅运行 HTTP 任务"
    )
    args = parser.parse_args()
    try:
        python = prepare_source(browser=not args.no_browser)
        if args.prepare_only:
            suffix = " --no-browser" if args.no_browser else ""
            print(f"源码环境准备完成；启动：bash install.sh source{suffix}", flush=True)
            return
        print(
            f"启动 WebMoniter：http://localhost:{os.environ.get('PORT', '8866')}（默认账号 admin / 123）",
            flush=True,
        )
        os.execv(str(python), [str(python), str(ROOT / "main.py")])
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"安装未完成：{exc}\n修复后重新运行相同命令，已有配置和数据会保留。", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
