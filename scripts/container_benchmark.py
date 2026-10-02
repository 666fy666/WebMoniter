"""Disposable, local-only container benchmark; never uses production volumes.

Run on a Docker host: python scripts/container_benchmark.py --image IMAGE --seconds 60
For a soak test use --seconds 86400. Browser work loads the shipped models and visits
a data URL; it does not assert real platform login/recognition success.
"""

import argparse
import concurrent.futures
import http.cookiejar
import json
import os
import secrets
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


def browser_load():
    import ddddocr
    import onnxruntime as ort
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service

    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    for _ in range(5):
        sessions = [
            ort.InferenceSession(
                str(path), sess_options=options, providers=["CPUExecutionProvider"]
            )
            for path in Path("/app/models/ikuuu").glob("*.onnx")
        ]
        ocr = ddddocr.DdddOcr(ocr=True, show_ad=False)
        detector = ddddocr.DdddOcr(det=True, show_ad=False)
        browser_options = webdriver.ChromeOptions()
        browser_options.binary_location = os.environ["CHROME_BIN"]
        for flag in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"):
            browser_options.add_argument(flag)
        driver = webdriver.Chrome(
            service=Service(os.environ["CHROMEDRIVER_PATH"]), options=browser_options
        )
        try:
            driver.get("data:text/html,<title>Local benchmark</title><p>WebMoniter</p>")
            assert driver.title == "Local benchmark"
            time.sleep(0.2)
        finally:
            driver.quit()
        del sessions, ocr, detector
    print("browser-model-smoke-ok")


def command(*args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs).stdout.strip()


def run(image: str, seconds: int, output: Path, *, smoke_only: bool = False):
    container = "webmoniter-bench-" + secrets.token_hex(4)
    environment = {**os.environ, "WEBMONITER_ADMIN_PASSWORD": secrets.token_urlsafe(24)}
    image_size = int(command("docker", "image", "inspect", image, "--format", "{{.Size}}"))
    command(
        "docker",
        "run",
        "-d",
        "--name",
        container,
        "--init",
        "--memory",
        "1536m",
        "--memory-swap",
        "1536m",
        "--cpus",
        "1.75",
        "--pids-limit",
        "256",
        "--shm-size",
        "256m",
        "-p",
        "127.0.0.1::8866",
        "--env",
        "WEBMONITER_ADMIN_PASSWORD",
        "--mount",
        f"type=bind,src={Path(__file__).resolve()},dst=/tmp/benchmark.py,readonly",
        image,
        env=environment,
    )
    latencies, errors = [], []
    browser = None
    started = time.monotonic()
    try:
        port = json.loads(
            command("docker", "inspect", container, "--format", "{{json .NetworkSettings.Ports}}")
        )["8866/tcp"][0]["HostPort"]
        base = f"http://127.0.0.1:{port}"
        while True:
            try:
                urllib.request.urlopen(base + "/health/ready", timeout=2).close()
                break
            except (OSError, urllib.error.URLError):
                if time.monotonic() - started > 60:
                    raise RuntimeError("Container did not become ready") from None
                time.sleep(0.5)
        startup = time.monotonic() - started
        command(
            "docker",
            "exec",
            container,
            "python",
            "-c",
            "import sqlite3; c=sqlite3.connect('/app/data/data.db'); "
            "c.executemany('INSERT OR REPLACE INTO weibo(UID,用户名,文本,published_at) VALUES(?,?,?,?)',"
            "[(str(i),'Local fixture '+str(i),'Local benchmark',i) for i in range(50)]); c.commit()",
        )
        has_browser = (
            command(
                "docker",
                "exec",
                container,
                "sh",
                "-c",
                "if test -x /usr/bin/chromium; then echo yes; fi",
            )
            == "yes"
        )
        if has_browser:
            browser = subprocess.Popen(
                [
                    "docker",
                    "exec",
                    container,
                    "python",
                    "/tmp/benchmark.py",
                    "--browser-load",
                    "--seconds",
                    str(seconds),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        deadline = time.monotonic() + seconds

        def visitor():
            client = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
            )
            session = json.load(client.open(base + "/api/v1/session"))
            response = client.open(
                urllib.request.Request(
                    base + "/api/v1/login",
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "X-CSRF-Token": session["csrf_token"],
                    },
                    data=json.dumps(
                        {"username": "admin", "password": environment["WEBMONITER_ADMIN_PASSWORD"]}
                    ).encode(),
                )
            )
            json.load(response)
            paths = ["/api/v1/tasks", "/api/v1/data/weibo?page_size=50", "/api/v1/logs"]
            index = 0
            while time.monotonic() < deadline:
                start = time.perf_counter()
                try:
                    with client.open(base + paths[index % len(paths)], timeout=5) as response:
                        json.load(response)
                    latencies.append((time.perf_counter() - start) * 1000)
                except Exception as exc:
                    errors.append(type(exc).__name__)
                index += 1
                time.sleep(0.1)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(visitor) for _ in range(3)]
            for future in futures:
                future.result()
        browser_ok = None
        if browser:
            stdout, _ = browser.communicate(timeout=180)
            browser_ok = browser.returncode == 0 and "browser-model-smoke-ok" in stdout
        peak = int(command("docker", "exec", container, "cat", "/sys/fs/cgroup/memory.peak"))
        state = json.loads(command("docker", "inspect", container, "--format", "{{json .State}}"))
        ordered = sorted(latencies)
        result = {
            "image": image,
            "image_inspect_size_bytes": image_size,
            "duration_seconds": seconds,
            "visitors": 3,
            "local_monitor_snapshots": 50,
            "requests": len(latencies),
            "api_p95_ms": ordered[int((len(ordered) - 1) * 0.95)] if ordered else None,
            "memory_peak_bytes": peak,
            "startup_seconds": startup,
            "browser_model_smoke": browser_ok,
            "errors": errors[:20],
            "oom_killed": state["OOMKilled"],
            "limits": {"memory_mib": 1536, "cpu": 1.75, "swap": False},
            "scope": "Local fixtures; five serial browser/model sessions; no external platform requests",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        if (
            errors
            or not ordered
            or (not smoke_only and result["api_p95_ms"] > 500)
            or (not smoke_only and peak > 1.4 * 1024**3)
            or state["OOMKilled"]
            or browser_ok is False
        ):
            raise SystemExit(1)
    finally:
        if browser and browser.poll() is None:
            browser.terminate()
        subprocess.run(
            ["docker", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="webmoniter:refactor-full")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--output", type=Path, default=Path("/tmp/webmoniter-benchmark.json"))
    parser.add_argument("--browser-load", action="store_true")
    parser.add_argument(
        "--smoke-only",
        action="store_true",
        help="CI/QEMU: validate behavior without performance thresholds",
    )
    args = parser.parse_args()
    if args.browser_load:
        deadline = time.monotonic() + args.seconds
        while True:
            browser_load()
            if args.seconds < 3600 or time.monotonic() + 300 >= deadline:
                break
            time.sleep(300)
    else:
        run(args.image, args.seconds, args.output, smoke_only=args.smoke_only)
